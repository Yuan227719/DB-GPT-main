# 交接文档：血缘工具 + get_glossary_term 增强（2026-08-10）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`，半导体测试数据分析（st_embed）
> 关联：`HANDOVER_20260810.md`（前一会话：早退修复、前端修复）
> 本文档覆盖本会话新增：DolphinScheduler 血缘工具、get_glossary_term 层级增强

---

## 一、本会话做了什么（全部已生效）

### 1. get_glossary_term 支持父术语返回完整字典

**问题**：用户问"每个 errorcode 的含义"时，模型不调 `get_glossary_term`（它是单术语查询），反而去 OpenMetadata 通用搜索（`search_metadata`/`semantic_search`），把 DIMM 等其他术语库混进答案。

**根因**：`get_glossary_term(term_name)` 是单术语查询，面对"列举全部"（103 条 errorcode）没有合适参数 → 模型判断它回答不了 → 转投 OpenMetadata 通用搜索。工具能力缺口，不是模型笨，也不是提示词"太清楚"。

**修复**（`packages/dbgpt-core/src/dbgpt/agent/util/openmetadata_client.py`）：
- `get_glossary_term` 命中术语后，用新增 `_collect_child_terms()` 递归收集所有子术语（按 `parent.fullyQualifiedName` 匹配）
- `get_glossary_term("不良代码（ErrorCode）")` → 现在返回 10 大类完整 errorcode 字典（103 条）
- 单查不破坏：`get_glossary_term("90")` 仍返回具体 errorcode

**配套提示词**（`agentic_data_api.py`）：@tool 描述 + 模板工具 #17 描述更新为"传父术语返回完整子字典"——**信息型，未加任何"必须/禁止"规则**（避免制造懒模型）。

### 2. DolphinScheduler 血缘工具（版本驱动增量）

**背景**：从 DolphinScheduler 30 个工作流 ETL SQL 解析表级+字段级血缘（`st_embed_lineage_report.md` 是静态快照）。用户要求接成工具，但调度实时变化，静态 JSON 会过期 → 版本驱动增量刷新。

**连接**：
- **connector**（`connector_instance` 表，display_name=`dolphinscheduler`，id=`275beaef-8d13-4f14-af8c-c65ea0073483`）：server_uri=`https://dp-dolphin.longsys.com/dolphinscheduler`、project_code=`171521334547168`、token 加密入库（复用 CredentialStore + `your_secret_key`）
- **`_load_dolphinscheduler_config()`**（`agentic_data_api.py`）：自动发现 connector + 解密 token，镜像 OpenMetadata 模式

**客户端**（`packages/dbgpt-core/src/dbgpt/agent/util/dolphinscheduler_client.py`，新建）：
- `get_workflow_versions()`：拉全量工作流 `{code: version}`（`/process-definition?pageSize=100`，~0.2s）
- `get_workflow_tasks(code)`：拉某工作流任务 SQL
- `_parse_task()`：sqlglot(Spark) 解析 `MERGE INTO` 目标表 + USING 源表 + 字段映射
- `ensure_fresh()`：**版本驱动增量**——对比缓存版本指纹，只重拉版本变化的工作流重解析，其余用缓存
- `get_table_lineage(table)`：返回 `{upstream, downstream, fields, build_workflows}`

**@tool**（`agentic_data_api.py`）：
- `get_lineage(table_name)` 已加入 ToolPack（`get_glossary_term` 旁）和模板工具 #18
- 返回 JSON：上游表 / 下游表 / 字段映射（列 ← 来源表达式 + 引用列）

**端到端验证通过**（真实会话）：模型第一步调 `get_lineage("st_embed.dws_indicator_w")`，返回 8 上游 + 2 下游 + 字段映射，最终答案正确。

---

## 二、当前状态

- **后端运行中**：PID 需新会话确认，配置 `configs/openai.toml`，端口 5670
- **提示词最新版**：`current_system_prompt.md`（32,143 字符，含 get_lineage + get_glossary_term 更新描述）
- **sqlglot 已装入 venv**（血缘解析依赖，`pip install sqlglot`，30.15.0）
- **血缘数据**：`/tmp/ds_lineage/lineage.json`（静态快照，已被工具取代）、`st_embed_lineage_report.md`（静态报告）
- 前端未改动（本会话全后端）

---

## 三、如何重启 / 测试

### 重启后端
```bash
cd /home/taoyuan/projects/DB-GPT-main
kill <旧PID>
nohup .venv/bin/dbgpt start webserver --config configs/openai.toml >> /tmp/dbgpt_server.log 2>&1 &
# 端口 5670
```

### 测试 get_lineage（真实会话，模型慢约 2-3 分钟）
```bash
CONV=$(python3 -c "import uuid; print(uuid.uuid4())")
bash /tmp/scenario_test.sh "$CONV" "请告诉我 st_embed.dws_indicator_w 这张表由哪些上游表构建？" 900
# 完成后查最终答案：
curl -s "http://127.0.0.1:5670/api/v1/chat/dialogue/messages/history?con_uid=$CONV"
```

### 测试 get_glossary_term（独立，快）
```bash
# 直接查 OpenMetadata：get_glossary_term("不良代码（ErrorCode）") 应返回 10 大类完整字典
```

### 测试血缘增量刷新
改一个工作流版本后，`get_lineage` 应只重解析该工作流（看日志 `DolphinScheduler lineage refresh: N workflows changed`）。

---

## 四、关键文件索引

| 文件 | 作用 |
|---|---|
| `packages/dbgpt-core/src/dbgpt/agent/util/openmetadata_client.py` | `get_glossary_term` 层级增强（`_collect_child_terms`） |
| `packages/dbgpt-core/src/dbgpt/agent/util/dolphinscheduler_client.py` | **新建**：血缘客户端（版本驱动增量） |
| `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py` | `get_lineage` @tool、`_load_dolphinscheduler_config`、工具描述更新 |
| `current_system_prompt.md` | 最新完整提示词（含 get_lineage） |
| `st_embed_lineage_report.md` | 静态血缘报告（工具已取代实时查询） |
| `connector_instance` 表 | `dolphinscheduler` connector（token 加密） |

---

## 五、给新会话的下一步建议

1. **确认后端运行** + `git status` 看改动
2. **待做（用户已认可方向，未实施）**：
   - **表清单分层注入**：`## 数据库信息` 占提示词 43%（13.5k 字符），热表（dws/ads）全描述 + 温表（dwd/ods）一行索引 + 冷表省略，能省 30-40% token。**注意不要加"必须/禁止"规则**
   - **MCP 工具瘦身**：`search_metadata`/`semantic_search` 让模型查术语时乱搜（混入 DIMM 库），术语查询应走 `get_glossary_term`。可选从 MCP 段隐藏/降权
3. **提示词设计原则（用户强调）**：修"工具能力"优于加"命令规则"；每加一条规则会让模型更机械。失败优先查是不是工具能力缺口，而不是加禁令
4. **DolphinScheduler 只读**：`get_lineage`/`DolphinSchedulerClient` 全部只读（GET），不触发调度运行
5. 用户提到 OpenMetadata 血缘为空（`nodes:1, edges:0`），本工具用 ETL SQL 解析，不依赖 OpenMetadata 血缘

---

## 六、已知限制

- **字段血缘是"任务级"**：取的是每个 MERGE 的 USING 投影列 ← 表达式，CTE 内部的多级追溯未展开（如 `dws_indicator_w.indicator_value` 的分位数结构到最底层表）。当前对 agent 已够用，如需更深可后续做 CTE 内联
- **sqlglot 未声明为项目依赖**：只 `pip install` 进 venv，若重建环境需重新安装（或在 pyproject 声明）
- **血缘只覆盖 st_embed 项目**（30 个工作流），若新增其他项目的表需扩展 project_code
