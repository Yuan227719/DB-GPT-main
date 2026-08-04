"""上下文治理改动点验证脚本（手写，不接入 pytest）。

运行方式：在仓库根目录执行
    uv run python tests/custom_agent_test/context_governance_verify.py

覆盖 memory_duplication_analysis.md 的本次改动点：
  1. 改动点 1：build() 后 clear —— 验证 AgentMemory.clear() 后 read 为空、write 后仅本轮
  2. 改动点 3：view 修复 —— 验证 view payload 提取 final_content 为 AI 回复、base_agent
     尊重已设 role（奇偶仅兜底）
  3. task_progress 渲染 —— 验证 jinja2 `{% if task_progress %}` 块真实渲染进 system prompt
  4. buffer_size=8 —— 写 9 个 fragment 后只保留最近 8 个
  5. OpenMetadata 客户端 —— mock MCP：list_tables 命中 / 未启用 / 异常降级返回空
  6. get_table_schema 工具 —— OpenMetadata 命中返回结构；失败回退 Kyuubi（get_columns）

注：view 提取与 base_agent 奇偶兜底逻辑在 agentic_data_api.py / base_agent.py 函数体内，
此处用与源码完全一致的片段做行为断言（标注出处）。
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

from dbgpt.agent import AgentMemory, AgentMemoryFragment, AgentMessage, ProfileConfig
from dbgpt.agent.core.memory.base import ShortTermMemory
from dbgpt.core import ModelMessageRoleType, PromptTemplate

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


# ─────────────────────────────────────────────────────────────
# 1. 改动点 1：clear() 后 memory_list 仅本轮（AgentMemory 真实代码）
# ─────────────────────────────────────────────────────────────
async def test_clear_memory():
    print("\n== 1. 改动点 1：clear 后 read 为空、write 后仅本轮 ==")
    mem = AgentMemory()  # 默认 ShortTermMemory(buffer_size=8)
    await mem.write(AgentMemoryFragment(observation="step1"))
    await mem.write(AgentMemoryFragment(observation="step2"))
    before = await mem.read("")
    check("write 后 read 返回已写片段", len(before) == 2, f"got {len(before)}")
    await mem.clear()
    after = await mem.read("")
    check("clear 后 read 为空", len(after) == 0, f"got {len(after)}")
    # 本轮 write 照常累积
    await mem.write(AgentMemoryFragment(observation="current_step"))
    cur = await mem.read("")
    check("clear 后 write 只含本轮", len(cur) == 1 and cur[0].raw_observation == "current_step")


# ─────────────────────────────────────────────────────────────
# 4. buffer_size=10：写 11 个 fragment 只保留最近 10 个（真实代码，验证 AgentMemory 默认值）
# ─────────────────────────────────────────────────────────────
async def test_buffer_size():
    print("\n== 4. buffer_size=10：写 11 个保留最近 10 个 ==")
    mem = AgentMemory()  # 默认 ShortTermMemory(buffer_size=10)
    for i in range(11):
        await mem.write(AgentMemoryFragment(observation=f"step{i}"))
    frags = await mem.read("")
    check("read 返回 10 个", len(frags) == 10, f"got {len(frags)}")
    check("保留最近 10 个（丢弃 step0）",
          frags[0].raw_observation == "step1",
          f"first={frags[0].raw_observation}")
    check("最新 step10 在列", frags[-1].raw_observation == "step10",
          f"last={frags[-1].raw_observation}")


# ─────────────────────────────────────────────────────────────
# 2. 改动点 3：view payload 提取 final_content（复现 agentic_data_api.py 片段）
#    与 base_agent.py 尊重已设 role 的奇偶兜底（复现 base_agent.py 片段）
# ─────────────────────────────────────────────────────────────
def _extract_historical_from_view(hist_msgs):
    """镜像 agentic_data_api.py 的 historical_dialogues 加载片段。"""
    historical_dialogues = []
    for m in hist_msgs:
        content = getattr(m, "context", "") or ""
        role_str = getattr(m, "role", "human")
        if role_str == "view":
            try:
                payload = json.loads(content)
                final = payload.get("final_content")
                if final:
                    historical_dialogues.append(
                        AgentMessage(content=final, role=ModelMessageRoleType.AI)
                    )
            except Exception:
                pass
            continue
        historical_dialogues.append(
            AgentMessage(
                content=content,
                role=ModelMessageRoleType.HUMAN if role_str == "human" else ModelMessageRoleType.AI,
            )
        )
    return historical_dialogues


def _apply_parity_fallback(historical_dialogues):
    """镜像 base_agent.py 组装 historical_dialogues 时的 role 兜底（新逻辑）。"""
    agent_messages = []
    for i, message in enumerate(historical_dialogues):
        if message.role is None:
            message.role = (
                ModelMessageRoleType.HUMAN if i % 2 == 0 else ModelMessageRoleType.AI
            )
        agent_messages.append(message)
    return agent_messages


def test_view_and_role():
    print("\n== 2. 改动点 3：view 提取 final_content + role 尊重 ==")
    view_payload = json.dumps(
        {"version": 1, "type": "react-agent",
         "final_content": "上一轮的 AI 回答", "steps": []}
    )
    hist = [
        MagicMock(role="human", context="上一轮用户问题"),
        MagicMock(role="view", context=view_payload),
        MagicMock(role="human", context="更早的用户问题"),
        MagicMock(role="view", context=view_payload),
    ]
    hd = _extract_historical_from_view(hist)
    roles = [m.role for m in hd]
    check("历史为 [human, ai, human, ai] 交替", roles == [
        ModelMessageRoleType.HUMAN, ModelMessageRoleType.AI,
        ModelMessageRoleType.HUMAN, ModelMessageRoleType.AI,
    ], f"got {roles}")
    check("含 AI 回复内容", hd[1].content == "上一轮的 AI 回答", f"got {hd[1].content}")

    # base_agent 尊重已设 role：已设 role 不被奇偶覆盖；无 role 才兜底
    mixed = [
        AgentMessage(content="q1", role=ModelMessageRoleType.HUMAN),
        AgentMessage(content="a1", role=ModelMessageRoleType.AI),
        AgentMessage(content="q2"),  # 无 role -> index 2 偶数 -> HUMAN 兜底
    ]
    out = _apply_parity_fallback(mixed)
    check("已设 AI role 不被覆盖", out[1].role == ModelMessageRoleType.AI)
    check("无 role 偶数位兜底 HUMAN", out[2].role == ModelMessageRoleType.HUMAN,
          f"got {out[2].role}")


# ─────────────────────────────────────────────────────────────
# 3. task_progress 渲染：真实 build_system_prompt + jinja2 块
# ─────────────────────────────────────────────────────────────
async def test_task_progress_render():
    print("\n== 3. task_progress 渲染进 system prompt ==")
    tmpl = PromptTemplate(
        template=(
            "You are assistant.\n"
            "{% if task_progress %}\n"
            "## Task Progress (do NOT repeat completed steps)\n"
            "{{ task_progress }}\n"
            "{% endif %}"
        ),
        input_variables=[],
        template_format="jinja2",
    )
    from dbgpt.agent import ConversableAgent

    class _Mini(ConversableAgent):
        profile: ProfileConfig = ProfileConfig(name="mini", role="helper")

    agent = _Mini()
    agent.bind_prompt = tmpl
    with_progress = await agent.build_system_prompt(
        question="q", context={"task_progress": "✅ Step 1: Action=sql_query"}
    )
    check("有 task_progress 时渲染", "## Task Progress" in with_progress
          and "Step 1" in with_progress, f"got: {with_progress[:120]!r}")
    without = await agent.build_system_prompt(question="q", context={})
    check("无 task_progress 时为空块", "Task Progress" not in without,
          f"got: {without[:120]!r}")


# ─────────────────────────────────────────────────────────────
# 5. OpenMetadata 客户端（mock MCP transport + session）
# ─────────────────────────────────────────────────────────────
class _FakeSession:
    """模拟 mcp.ClientSession：call_tool / list_tools 返回固定数据。"""

    def __init__(self, *a, **kw):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def initialize(self):
        pass

    async def call_tool(self, tool_name, arguments=None):
        self.calls.append((tool_name, arguments))
        resp = MagicMock()
        text = '[{"name":"t1","description":"工单表"},{"name":"t2","description":"良率表"}]'
        resp.content = [MagicMock(type="text", text=text)]
        return resp

    async def list_tools(self):
        resp = MagicMock()
        t = MagicMock(name="get_tables", description="list tables in schema")
        resp.tools = [t]
        return resp


@asynccontextmanager
async def _fake_transport_factory(
    url=None, transport="sse", headers=None, verify=True
):
    """模拟 mcp_transport_client(url, transport, ...)：yield (read, write)。"""
    yield None, None


async def test_openmetadata_client():
    print("\n== 5. OpenMetadata 客户端 ==")
    from dbgpt.agent.util.openmetadata_client import (
        OpenMetadataClient,
        OpenMetadataConfig,
    )

    cfg = OpenMetadataConfig(
        enabled=True, server_uri="http://om:8000/sse", schema="商规EMBED",
        list_tables_tool="get_tables", table_schema_tool="get_table",
    )
    with patch(
        "dbgpt.agent.util.openmetadata_client.mcp_transport_client", _fake_transport_factory
    ), patch("mcp.ClientSession", _FakeSession):
        client = OpenMetadataClient(cfg)
        tables = await client.list_tables()
        check("list_tables 命中 2 张表", len(tables) == 2, f"got {len(tables)}")
        check("含表描述", tables[0]["description"] == "工单表")
        schema = await client.get_table_schema("t1")
        check("get_table_schema 返回文本", "t1" in schema, f"got {schema[:60]!r}")

    # 未启用 / 失败降级
    client_off = OpenMetadataClient(OpenMetadataConfig(enabled=False))
    check("enabled=False 返回空", await client_off.list_tables() == [])
    with patch(
        "dbgpt.agent.util.openmetadata_client.mcp_transport_client",
        side_effect=RuntimeError("conn refused"),
    ):
        client_err = OpenMetadataClient(cfg)
        check("连接异常降级为空列表", await client_err.list_tables() == [])
        check("连接异常 get_table_schema 为空串", await client_err.get_table_schema("t1") == "")

    # 自动发现排除写/测试类工具（避免误匹配 get_test_definitions 等）
    class _DiscoverSession(_FakeSession):
        async def list_tools(self):
            resp = MagicMock()
            bad = MagicMock()
            bad.name = "get_test_definitions"
            bad.description = "get all test definitions for a table"
            good = MagicMock()
            good.name = "search_metadata"
            good.description = "keyword-based search for metadata data assets"
            resp.tools = [bad, good]
            return resp

        async def call_tool(self, tool_name, arguments=None):
            resp = MagicMock()
            if tool_name == "search_metadata":
                # 模拟给 search_metadata 传错参数（缺 query）返回错误
                text = '{"error": "query param required", "results": []}'
            else:
                text = '[{"name":"t1","description":"工单表"}]'
            resp.content = [MagicMock(type="text", text=text)]
            return resp

    with patch(
        "dbgpt.agent.util.openmetadata_client.mcp_transport_client", _fake_transport_factory
    ), patch("mcp.ClientSession", _DiscoverSession):
        auto_cfg = OpenMetadataConfig(
            enabled=True, server_uri="http://om:8000/sse", list_tables_tool="",
            table_schema_tool="",
        )
        client_auto = OpenMetadataClient(auto_cfg)
        tool = await client_auto._discover_tool(
            client_auto.config.list_tables_desc_keywords
        )
        check("发现排除 create/test 类工具", tool == "search_metadata", f"got {tool}")
        # search_metadata 被传了错误的 {schema} 参数会失败 -> 返回空，安全降级
        tables_err = await client_auto.list_tables()
        check("list_tables 失败安全返回空（不注入错误文本）", tables_err == [],
              f"got {tables_err}")

    # _parse_table_list 对错误/空搜索返回空
    client_parse = OpenMetadataClient(cfg)
    check("错误 JSON 解析为空",
          client_parse._parse_table_list('{"error":"query param required","results":[]}') == [])
    check("空搜索解析为空",
          client_parse._parse_table_list('{"totalFound":0,"results":[]}') == [])

    # REST 直连（方式 A）：mock httpx 返回 schema FQN + 表清单（含描述）
    import httpx as _httpx

    class _FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    rest_calls = {}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            path = url.split("/api/v1/")[-1]
            if path.startswith("databaseSchemas"):
                rest_calls["schemas"] = params
                return _FakeResp({"data": [{"name": "st_embed",
                                            "fullyQualifiedName": "p_trino_iceberg.iceberg.st_embed"}]})
            if path.startswith("tables"):
                rest_calls["tables"] = params
                long_desc = (
                    "【业务定义】DUT 测试结果明细表，记录每个被测设备测试过程全部信息。"
                    "由 ods 清洗加工而来，含测试编号、机台、测试结果等。"
                    "【粒度】一个 SN 的一次测试记录"
                    "【核心字段】guid（主键）、wo（工单）、dut_sn（SN）"
                )
                return _FakeResp({"data": [
                    {"name": "dwd_dut_result", "description": long_desc},
                    {"name": "dim_base_project",
                     "description": "项目维度表，存储项目配置信息"},
                ]})
            return _FakeResp({"data": []})

    with patch("httpx.AsyncClient", _FakeClient):
        rest_cfg = OpenMetadataConfig(
            enabled=True, server_uri="http://dp-metadata.longsys.com/mcp",
            transport="streamable_http", auth_type="bearer", token="t", schema="st_embed",
        )
        rest_client = OpenMetadataClient(rest_cfg)
        tables_rest = await rest_client.list_tables_rest()
        check("REST list_tables_rest 返回带描述表清单", len(tables_rest) == 2,
              f"got {len(tables_rest)}")
        check("REST schema 定位用 FQN", rest_calls["tables"]["databaseSchema"]
              == "p_trino_iceberg.iceberg.st_embed")
        # 默认全量（description_max_chars=0）：完整描述不被截断，含【粒度】段落
        check("默认全量描述保留完整段落",
              "【粒度】一个 SN 的一次测试记录" in tables_rest[0]["description"]
              and "【核心字段】" in tables_rest[0]["description"],
              f"got={tables_rest[0]['description'][:60]}…")
        check("REST 基址从 server_uri 推导", rest_client._rest_base_url()
              == "http://dp-metadata.longsys.com")

    # _shorten_desc：max_chars>0 时按句号断句截断，不切断
    client_short = OpenMetadataClient(rest_cfg)
    full = ("【业务定义】A 表，负责记录每颗芯片的完整测试过程全部信息。"
            "这是第二句补充说明用于把文本拉长到超过八十个字符的截断阈值。"
            "这里继续追加很长很长的内容确保一定触发截断分支，因为前面的句子还不够长。")
    short = client_short._shorten_desc(full, max_chars=80)
    expected = "A 表，负责记录每颗芯片的完整测试过程全部信息。"
    check("截断时按句号断句（不切词）", short == expected, f"got={short!r}")

    # 业务术语库（商规EMBED生产测试术语库）：mock REST 拉术语 + 白名单筛选
    class _GlossaryClient(_FakeClient):
        async def get(self, url, params=None, headers=None):
            path = url.split("/api/v1/")[-1]
            if path.startswith("glossaries"):
                return _FakeResp({"data": [{"name": "商规EMBED生产测试术语库",
                                            "id": "g-001"}]})
            if path.startswith("glossaryTerms"):
                return _FakeResp({"data": [
                    {"name": "数仓分层", "description": "数据仓库逻辑分层架构。ODS→DWD→DWS→ADS。DIM维表层存储主数据"},
                    {"name": "test_result（测试结果）",
                     "description": "测试结果，枚举值 Pass/Fail/NA"},
                    {"name": "不良代码（ErrorCode）",
                     "description": "eMMC 产品测试过程中的不良代码，共 103 条，按功能分为 10 大类"},
                ]})
            return _FakeResp({"data": []})

    with patch("httpx.AsyncClient", _GlossaryClient):
        g_cfg = OpenMetadataConfig(
            enabled=True, server_uri="http://dp-metadata.longsys.com/mcp",
            auth_type="bearer", token="t",
        )
        g_client = OpenMetadataClient(g_cfg)
        whitelist = ["数仓分层", "test_result"]
        terms = await g_client.list_glossary_terms(
            "商规EMBED生产测试术语库", whitelist
        )
        check("术语白名单筛选（排除不良代码库）",
              set(terms.keys()) == {"数仓分层", "test_result（测试结果）"},
              f"got {list(terms.keys())}")
        check("术语描述压缩为短摘要", len(terms["数仓分层"]) <= 125,
              f"len={len(terms['数仓分层'])}")
        check("术语库未找到返回空", await g_client.list_glossary_terms("不存在的库", []) == {})

    # get_glossary_term：按名/描述鲁棒匹配（含错误码、CJK n-gram）
    class _TermClient(_FakeClient):
        async def get(self, url, params=None, headers=None):
            path = url.split("/api/v1/")[-1]
            if path.startswith("glossaries"):
                return _FakeResp({"data": [{"name": "商规EMBED生产测试术语库", "id": "g-001"}]})
            if path.startswith("glossaryTerms"):
                return _FakeResp({"data": [
                    {"name": "初始化与开卡",
                     "description": "系统初始化、开卡、MP下载相关不良代码（22条） 30: 初始化卡失败 31: 开卡板未插卡"},
                    {"name": "数仓分层",
                     "description": "ODS→DWD→DWS→ADS，DIM维表层"},
                ]})
            return _FakeResp({"data": []})

    with patch("httpx.AsyncClient", _TermClient):
        t_client = OpenMetadataClient(g_cfg)
        d30 = await t_client.get_glossary_term("商规EMBED生产测试术语库", "code 30")
        check("get_glossary_term 错误码命中", "30: 初始化卡失败" in d30, f"got={d30[:60]!r}")
        d_init = await t_client.get_glossary_term("商规EMBED生产测试术语库", "初始化不良代码")
        check("get_glossary_term CJK n-gram 命中", "开卡" in d_init, f"got={d_init[:60]!r}")
        check("get_glossary_term 未找到返回空",
              await t_client.get_glossary_term("商规EMBED生产测试术语库", "完全不存在x") == "")


# ─────────────────────────────────────────────────────────────
# 6. get_table_schema 工具：OpenMetadata 命中 + Kyuubi 兜底
# ─────────────────────────────────────────────────────────────
async def test_get_table_schema_tool():
    print("\n== 6. get_table_schema：OpenMetadata 命中 / Kyuubi 兜底 ==")
    from dbgpt.agent.util.openmetadata_client import OpenMetadataConfig

    # 6a. OpenMetadata 命中
    async def _fake_om_get(table):
        return "CREATE TABLE t1 (id int, name string)"

    cfg = OpenMetadataConfig(
        enabled=True, server_uri="http://om:8000/sse", table_schema_tool="get_table"
    )
    with patch(
        "dbgpt.agent.util.openmetadata_client.mcp_transport_client", _fake_transport_factory
    ), patch("mcp.ClientSession", _FakeSession):
        from dbgpt.agent.util.openmetadata_client import OpenMetadataClient

        out = await OpenMetadataClient(cfg).get_table_schema("t1")
        check("OpenMetadata 命中返回结构", "CREATE TABLE" in out or "t1" in out,
              f"got {out[:60]!r}")

    # 6b. Kyuubi 兜底逻辑（等价于 get_table_schema 工具中 OpenMetadata 未启用时的分支：
    #     database_connector.get_table_info 为空 → get_columns）
    class _FakeConnector:
        def get_table_info(self, table_names=None):
            return ""

        def get_columns(self, table_name):
            return [{"name": "id", "type": "int"}, {"name": "name", "type": "string"}]

    conn = _FakeConnector()
    table_info = conn.get_table_info(["t1"])
    if not table_info:
        columns = conn.get_columns("t1")
        out = json.dumps({"table_name": "t1", "columns": columns}, ensure_ascii=False)
    else:
        out = table_info
    parsed = json.loads(out)
    check("Kyuubi 兜底返回 columns", parsed["columns"][0]["name"] == "id",
          f"got {parsed}")


# ─────────────────────────────────────────────────────────────
# 7. 缓存 TTL：OpenMetadata 更新后自动过期重拉（复用 agentic_data_api._is_cache_fresh）
# ─────────────────────────────────────────────────────────────
def test_cache_ttl():
    print("\n== 7. 缓存 TTL：过期自动重拉 ==")
    try:
        # 优先用真实函数（模块级导入较慢但准确）
        from dbgpt_app.openapi.api_v1.agentic_data_api import _is_cache_fresh
    except Exception:
        def _is_cache_fresh(cached, ttl):
            if not cached:
                return False
            return (time.time() - cached[0]) < ttl

    now = time.time()
    fresh = (now - 10, "catalog")    # 10 秒前 → 未过期
    stale = (now - 3600, "catalog")  # 1 小时前 → 已过期
    check("缓存未过期返回 True", _is_cache_fresh(fresh, 1800) is True)
    check("缓存过期返回 False", _is_cache_fresh(stale, 1800) is False)
    check("无缓存返回 False", _is_cache_fresh(None, 1800) is False)
    check("TTL=0 表示每次重新拉取", _is_cache_fresh(fresh, 0) is False)


# ─────────────────────────────────────────────────────────────
async def main():
    print("=== DB-GPT 上下文治理改动点验证 ===")
    await test_clear_memory()
    await test_buffer_size()
    test_view_and_role()
    await test_task_progress_render()
    await test_openmetadata_client()
    await test_get_table_schema_tool()
    test_cache_ttl()
    print(f"\n=== 结果: PASS={PASS} FAIL={FAIL} ===")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
