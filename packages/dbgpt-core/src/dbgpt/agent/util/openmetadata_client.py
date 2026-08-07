"""OpenMetadata MCP client for fetching database table metadata.

通过 MCP 直连 OpenMetadata 数据目录，提供两个能力：
- ``list_tables``：拉取某 schema 下「表名 + 描述」紧凑清单（注入 system prompt 用）
- ``get_table_schema``：按需拉取指定表的完整结构（列名/类型/描述）

实现复用了 ``dbgpt.agent.util.mcp_utils.mcp_transport_client`` + ``mcp.ClientSession``
的调用模式（对齐 ``resource/tool/pack.py`` 的 ``MCPToolPack``）。

设计约束（见 memory_duplication_analysis.md §6.5）：
- **可配置**：OpenMetadata MCP 暴露的工具名仓库里未知，因此 ``OpenMetadataConfig``
  里工具名可为空；为空时自动从 ``list_tools()`` 按描述关键字匹配。
- **失败降级**：所有调用 try/except 包裹，失败/未配置返回空，绝不抛出阻塞主流程。
- 完全信任 OpenMetadata 为表/列结构、类型、描述的权威来源；Kyuubi 只负责数据查询。
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .mcp_utils import mcp_transport_client

logger = logging.getLogger(__name__)


@dataclass
class OpenMetadataConfig:
    """OpenMetadata MCP 连接与工具配置。

    工具名未知时留空，运行时会自动从 ``list_tools()`` 按描述关键字匹配；
    联调时填写确切工具名可跳过自动发现。
    """

    enabled: bool = False
    server_uri: str = ""
    transport: str = "sse"  # sse | streamable_http
    auth_type: str = "none"  # none | bearer | token
    token: str = ""
    header_name: str = "Authorization"
    # 预构建好的 HTTP 头（含已解密的 token）。若提供，优先使用；否则由 token 构建。
    headers: Optional[Dict[str, str]] = None
    schema: str = ""  # 要拉取元数据的 schema（如 "商规EMBED"）
    list_tables_tool: str = ""  # MCP 工具名；空则自动发现
    table_schema_tool: str = ""
    list_tables_arg: str = "schema"  # 工具入参名
    table_schema_arg: str = "table_name"
    # 当 table_schema_tool == "get_entity_details" 时，用此模板拼 fqn（schema.table）
    table_schema_fqn_template: str = "{schema}.{table}"
    # OpenMetadata REST API 基址（如 http://dp-metadata.longsys.com）。
    # 为空时自动从 server_uri 推导（去掉尾部路径如 /mcp）。
    rest_base_url: str = ""
    # 表/术语描述最大字符数；0 表示不截断（全量保留完整描述，含【粒度】【指标】等段落）
    description_max_chars: int = 0
    # 元数据缓存 TTL（秒）：OpenMetadata 更新后最长 TTL 内重新拉取，默认 30 分钟
    cache_ttl_seconds: int = 1800
    # 自动发现时的描述关键字（优先级从高到低）
    list_tables_desc_keywords: List[str] = field(
        default_factory=lambda: ["list", "search", "get_entity", "metadata", "table"]
    )
    table_schema_desc_keywords: List[str] = field(
        default_factory=lambda: ["get_entity", "column", "schema", "detail", "table"]
    )
    # 排除关键字：写操作 / 测试 / 治理类工具绝不是"读表清单"工具，避免误匹配
    discover_exclude_keywords: List[str] = field(
        default_factory=lambda: [
            "create", "patch", "update", "delete", "test", "definition",
            "lineage", "metric", "tag", "classification", "domain",
            "glossary", "data_product", "case", "root_cause",
        ]
    )


class OpenMetadataClient:
    """MCP 直连 OpenMetadata 的元数据客户端。"""

    def __init__(self, config: Optional[OpenMetadataConfig] = None):
        self.config = config or OpenMetadataConfig()

    @property
    def is_enabled(self) -> bool:
        """是否已启用（配置开启且给了 server_uri）。"""
        return self.config.enabled and bool(self.config.server_uri)

    def _build_headers(self) -> Dict[str, str]:
        """构造 HTTP 头：优先用配置里预构建的 headers，否则按 auth_type/token 构建。"""
        if self.config.headers:
            return self.config.headers
        if not self.config.token:
            return {}
        header_name = self.config.header_name or "Authorization"
        if self.config.auth_type == "bearer":
            return {header_name: f"Bearer {self.config.token}"}
        return {header_name: self.config.token}

    async def list_tables(self) -> List[Dict[str, str]]:
        """返回 schema 下表清单：[{"name": ..., "description": ...}]。

        失败/未启用/无法解析时返回空列表，不抛异常。
        """
        if not self.is_enabled:
            return []
        try:
            tool_name = self.config.list_tables_tool
            if not tool_name:
                tool_name = await self._discover_tool(
                    self.config.list_tables_desc_keywords
                )
            if not tool_name:
                logger.warning("OpenMetadata list_tables: no tool matched")
                return []
            arguments: Dict[str, Any] = {}
            if self.config.schema:
                arguments[self.config.list_tables_arg] = self.config.schema
            text = await self._call_tool(tool_name, arguments)
            return self._parse_table_list(text)
        except Exception as e:
            logger.warning(f"OpenMetadata list_tables failed: {e}")
            return []

    def _rest_base_url(self) -> str:
        """OpenMetadata REST 基址：优先配置；否则从 server_uri 推导（去掉尾部路径）。"""
        if self.config.rest_base_url:
            return self.config.rest_base_url.rstrip("/")
        parsed = urlparse(self.config.server_uri)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def list_tables_rest(self) -> List[Dict[str, str]]:
        """通过 OpenMetadata REST API 拉取某 schema 下表清单（含描述）。

        相比 MCP（该 server 无干净的 list-tables 工具），REST 直连更确定：
          1. GET /api/v1/databaseSchemas?name=<schema> 定位 schema FQN
          2. GET /api/v1/tables?databaseSchema=<fqn>&fields=name,description 拉表清单
        失败/未启用返回空列表，不抛异常。
        """
        if not self.is_enabled:
            return []
        base = self._rest_base_url()
        schema = self.config.schema or ""
        if not base or not schema:
            return []
        headers = {"Accept": "application/json", **self._build_headers()}
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                # 1) 定位 schema FQN
                r = await client.get(
                    f"{base}/api/v1/databaseSchemas",
                    params={"name": schema, "limit": 100},
                    headers=headers,
                )
                r.raise_for_status()
                fqn = None
                for item in r.json().get("data", []):
                    if item.get("name") == schema:
                        fqn = item.get("fullyQualifiedName")
                        break
                if not fqn:
                    logger.warning(
                        f"OpenMetadata schema '{schema}' FQN not found in catalog"
                    )
                    return []
                # 2) 拉该 schema 下表
                r2 = await client.get(
                    f"{base}/api/v1/tables",
                    params={
                        "databaseSchema": fqn,
                        "limit": 200,
                        "fields": "name,description",
                    },
                    headers=headers,
                )
                r2.raise_for_status()
                result = []
                for t in r2.json().get("data", []):
                    name = t.get("name")
                    if not name:
                        continue
                    result.append(
                        {"name": name, "description": self._shorten_desc(t.get("description") or "", self.config.description_max_chars)}
                    )
                return result
        except Exception as e:
            logger.warning(f"OpenMetadata list_tables_rest failed: {e}")
            return []

    @staticmethod
    def _shorten_desc(desc: str, max_chars: int = 0) -> str:
        """压缩长描述为单行文本。

        - ``max_chars <= 0``：不截断，返回完整描述（仅把换行/多空格压成单行）。
        - ``max_chars > 0``：优先提取【业务定义】段落并取到第一个句号（或分号），
          避免硬切断句；无结构段落时按 max_chars 截断。
        """
        desc = (desc or "").strip()
        one_line = " ".join(desc.split())
        if max_chars <= 0 or len(one_line) <= max_chars:
            return one_line
        m = re.search(r"【业务定义】\s*(.*?)(?=【|$)", one_line, re.S)
        if m:
            one_line = " ".join(m.group(1).strip().split())
            if len(one_line) <= max_chars:
                return one_line
        for sep in ("。", "；", ";"):
            idx = one_line.find(sep)
            if 0 < idx <= max_chars:
                return one_line[: idx + 1]
        return one_line[:max_chars] + "…"

    async def list_glossary_terms(
        self,
        glossary_name: str,
        whitelist: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """通过 REST 拉取指定术语库的术语，按白名单筛选并压缩为短描述。

        返回 {术语名: 压缩后的描述}。失败/未启用返回空 dict。
        """
        if not self.is_enabled:
            return {}
        base = self._rest_base_url()
        if not base or not glossary_name:
            return {}
        headers = {"Accept": "application/json", **self._build_headers()}
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                # 1) 定位术语库 id
                r = await client.get(
                    f"{base}/api/v1/glossaries",
                    params={"name": glossary_name, "limit": 100},
                    headers=headers,
                )
                r.raise_for_status()
                gid = None
                for g in r.json().get("data", []):
                    if g.get("name") == glossary_name:
                        gid = g.get("id")
                        break
                if not gid:
                    logger.warning(f"OpenMetadata glossary '{glossary_name}' not found")
                    return {}
                # 2) 拉全部术语，按白名单筛选
                r2 = await client.get(
                    f"{base}/api/v1/glossaryTerms",
                    params={"glossary": gid, "limit": 200},
                    headers=headers,
                )
                r2.raise_for_status()
                result: Dict[str, str] = {}
                for t in r2.json().get("data", []):
                    name = t.get("name", "")
                    if not name:
                        continue
                    if whitelist and not any(w in name for w in whitelist):
                        continue
                    desc = self._shorten_desc(t.get("description") or "", self.config.description_max_chars)
                    if desc:
                        result[name] = desc
                return result
        except Exception as e:
            logger.warning(f"OpenMetadata list_glossary_terms failed: {e}")
            return {}

    async def get_glossary_term(self, glossary_name: str, term_name: str) -> str:
        """按术语名返回完整定义（不截断）；未找到/失败返回空串。

        errorcode / 测项 / 指标等业务知识都在术语库里，供 get_glossary_term 工具按需取用。
        """
        if not self.is_enabled:
            return ""
        base = self._rest_base_url()
        if not base or not glossary_name or not term_name:
            return ""
        headers = {"Accept": "application/json", **self._build_headers()}
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                # 1) 定位术语库 id
                r = await client.get(
                    f"{base}/api/v1/glossaries",
                    params={"name": glossary_name, "limit": 100},
                    headers=headers,
                )
                r.raise_for_status()
                gid = None
                for g in r.json().get("data", []):
                    if g.get("name") == glossary_name:
                        gid = g.get("id")
                        break
                if not gid:
                    return ""
                # 2) 按名/描述鲁棒匹配：名字相同优先；否则名互相包含、关键词命中、
                #    描述里含错误码（如 "code 30"）也算
                r2 = await client.get(
                    f"{base}/api/v1/glossaryTerms",
                    params={"glossary": gid, "limit": 200},
                    headers=headers,
                )
                r2.raise_for_status()
                terms = r2.json().get("data", [])
                best_desc = ""
                best_score = -1
                # 错误码查询：去掉 "code"/"错误码" 前缀后的数字，用于描述匹配
                code_num = ""
                m = re.search(r"code\s*(\d+)", term_name, re.I) or re.search(
                    r"(\d+)", term_name
                )
                if m:
                    code_num = m.group(1)
                for t in terms:
                    n = t.get("name", "") or ""
                    d = t.get("description") or ""
                    if n == term_name:
                        score = 1000
                    elif term_name in n or n in term_name:
                        score = 500
                    else:
                        # 查询词的 CJK n-gram 命中术语名（如 "初始化不良代码" 的
                        # "初始化" 命中 "初始化与开卡"）；长 n-gram 权重更高
                        score = 0
                        query_cjk = re.sub(r"[^\u4e00-\u9fa5]", "", term_name)
                        for glen in range(2, min(5, len(query_cjk)) + 1):
                            for i in range(len(query_cjk) - glen + 1):
                                gram = query_cjk[i : i + glen]
                                if gram in n:
                                    score = max(score, len(gram) * 10)
                        # 描述里含目标错误码（如 "30"）
                        if code_num and re.search(
                            rf"(?<!\d){re.escape(code_num)}(?!\d)", d
                        ):
                            score = max(score, 300)
                    if score > best_score:
                        best_score = score
                        best_desc = d
                # 最低匹配阈值：至少 2 字 n-gram(20) / 描述含错误码(300) / 名字匹配(500+) 才算命中
                if best_score >= 20:
                    return " ".join(best_desc.split())
                return ""
        except Exception as e:
            logger.warning(f"OpenMetadata get_glossary_term failed: {e}")
            return ""

    async def get_table_schema(self, table_name: str) -> str:
        """返回指定表完整结构文本；失败/未启用返回空串。

        优先 REST API（确定性，直接返回列结构）；失败/未启用回退 MCP 工具。
        注意：MCP 自动发现工具容易误匹配到 search_metadata 等搜索工具（需
        query 参数），因此 table_schema_tool 为空时也优先走 REST。
        """
        if not self.is_enabled:
            return ""
        # 1) REST 优先（确定性，返回列结构）
        try:
            schema_text = await self._get_table_schema_rest(table_name)
            if schema_text:
                return schema_text
        except Exception as e:
            logger.warning(f"OpenMetadata get_table_schema(REST) failed: {e}")
        # 2) MCP 兜底
        try:
            tool_name = self.config.table_schema_tool
            if not tool_name:
                # 默认用 get_entity_details（避免误匹配 search_metadata）
                tool_name = "get_entity_details"
            if tool_name == "get_entity_details":
                fqn = self.config.table_schema_fqn_template.format(
                    schema=self.config.schema or "", table=table_name
                )
                arguments = {"entityType": "table", "fqn": fqn}
            else:
                arguments = {self.config.table_schema_arg: table_name}
            return await self._call_tool(tool_name, arguments)
        except Exception as e:
            logger.warning(f"OpenMetadata get_table_schema(MCP) failed: {e}")
            return ""

    async def _get_table_schema_rest(self, table_name: str) -> str:
        """通过 REST API 拉取指定表结构（列名/类型/描述）。

        1. GET /api/v1/databaseSchemas?name=<schema> 定位 schema FQN
        2. GET /api/v1/tables?databaseSchema=<fqn>&name=<table>&fields=columns
           精确命中表名后返回列结构 JSON。失败返回空串。
        """
        base = self._rest_base_url()
        schema = self.config.schema or ""
        if not base or not schema or not table_name:
            return ""
        headers = {"Accept": "application/json", **self._build_headers()}
        try:
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                # 1) 定位 schema FQN
                r = await client.get(
                    f"{base}/api/v1/databaseSchemas",
                    params={"name": schema, "limit": 100},
                    headers=headers,
                )
                r.raise_for_status()
                sfqn = None
                for item in r.json().get("data", []):
                    if item.get("name") == schema:
                        sfqn = item.get("fullyQualifiedName")
                        break
                if not sfqn:
                    logger.warning(
                        f"OpenMetadata schema '{schema}' FQN not found for table schema"
                    )
                    return ""
                # 2) 按 schema + 表名精确查找，带列结构
                r2 = await client.get(
                    f"{base}/api/v1/tables",
                    params={
                        "databaseSchema": sfqn,
                        "name": table_name,
                        "fields": "columns",
                        "limit": 20,
                    },
                    headers=headers,
                )
                r2.raise_for_status()
                target = None
                for t in r2.json().get("data", []):
                    if t.get("name") == table_name:
                        target = t
                        break
                if not target:
                    return ""
                cols = target.get("columns") or []
                result = {
                    "table_name": table_name,
                    "fully_qualified_name": target.get("fullyQualifiedName"),
                    "description": self._shorten_desc(
                        target.get("description") or "", self.config.description_max_chars
                    ),
                    "columns": [
                        {
                            "name": c.get("name"),
                            "data_type": c.get("dataType"),
                            "description": self._shorten_desc(
                                c.get("description") or "", self.config.description_max_chars
                            ),
                        }
                        for c in cols
                    ],
                }
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"OpenMetadata get_table_schema_rest failed: {e}")
            return ""

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用 MCP 工具并返回文本内容（每次调用新建 session，对齐 MCPToolPack）。"""
        from mcp import ClientSession

        async with mcp_transport_client(
            url=self.config.server_uri,
            transport=self.config.transport,
            headers=self._build_headers(),
            verify=True,
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resp = await session.call_tool(tool_name, arguments=arguments)
        return self._extract_text(resp)

    async def _discover_tool(self, keywords: List[str]) -> Optional[str]:
        """从 list_tools() 中按描述关键字挑选最匹配的工具名。"""
        try:
            async with mcp_transport_client(
                url=self.config.server_uri,
                transport=self.config.transport,
                headers=self._build_headers(),
                verify=True,
            ) as (read, write):
                from mcp import ClientSession

                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
            best_name = None
            best_score = 0
            kw_lower = [k.lower() for k in keywords]
            exclude_lower = [k.lower() for k in self.config.discover_exclude_keywords]
            for t in tools.tools:
                name = (t.name or "").lower()
                desc = (t.description or "").lower()
                haystack = f"{name} {desc}"
                # 命中排除关键字（写/测试/治理类）直接跳过，避免误匹配到 create_*/test_* 等
                if any(ex in haystack for ex in exclude_lower):
                    continue
                score = sum(1 for k in kw_lower if k in haystack)
                if score > best_score:
                    best_score = score
                    best_name = t.name
            return best_name
        except Exception as e:
            logger.warning(f"OpenMetadata discover_tool failed: {e}")
            return None

    @staticmethod
    def _extract_text(resp) -> str:
        """从 MCP call_tool 响应中提取文本。"""
        content = getattr(resp, "content", None) or []
        parts = []
        for item in content:
            if getattr(item, "type", None) == "text":
                parts.append(getattr(item, "text", "") or "")
        return "\n".join(parts)

    def _parse_table_list(self, text: str) -> List[Dict[str, str]]:
        """解析表清单文本。

        优先按 JSON 解析（OpenMetadata MCP 通常返回 JSON）；失败则按行启发式解析
        （每行形如 "表名 描述" 或 "表名：描述"）。
        """
        if not text:
            return []
        # 1) 尝试 JSON
        try:
            data = json.loads(text)
            # 错误 / 空搜索（如 search_metadata 缺参返回 {"error": ...} 或
            # {"totalFound": 0, "results": []}）→ 返回空，让调用方降级，避免注入错误文本
            if isinstance(data, dict) and (
                "error" in data or "totalFound" in data or "returnedCount" in data
            ):
                return []
            items = data if isinstance(data, list) else data.get("tables") or data.get("data") or []
            result = []
            for it in items:
                if isinstance(it, dict):
                    name = (
                        it.get("name")
                        or it.get("table_name")
                        or it.get("table")
                        or it.get("entityName")
                    )
                    desc = (
                        it.get("description")
                        or it.get("table_comment")
                        or it.get("comment")
                        or ""
                    )
                    if name:
                        result.append({"name": str(name), "description": str(desc or "")})
            if result:
                return result
        except Exception:
            pass
        # 2) 行启发式解析
        result = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if "：" in line:
                name, _, desc = line.partition("：")
            elif ":" in line:
                name, _, desc = line.partition(":")
            else:
                parts = line.split(None, 1)
                name, desc = parts[0], (parts[1] if len(parts) > 1 else "")
            if name:
                result.append({"name": name, "description": desc})
        return result
