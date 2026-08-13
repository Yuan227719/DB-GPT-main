# 交接文档：规则路由 + 简化注入 + get_table_info（2026-08-10）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`，半导体测试数据分析（st_embed）
> 关联：`HANDOVER_20260810_lineage_glossary.md`（血缘工具 + get_glossary_term）、
>       `HANDOVER_20260810.md`（早退/前端修复）、`HANDOVER_20260810_memory.md`（上下文方案）、
>       `HANDOVER_20260811_burnin.md`（get_table_info 瘦身 A+C + Burnin 口径修正 + 前端折叠/滚动条）
> 本会话：方案6A → 规则路由 → 简化表描述注入 → get_table_info 按需取

---

## 一、本会话做了什么（全部已生效）

### 1. 方案6A：每表"适用场景"路由提示（已上线）

- `agentic_data_api.py` 新增 `_TABLE_ROUTING_HINTS`（30 表 → `适用:` 关键词）
- `_build_compact_catalog` 行尾追加 `｜ 适用: ...`（信息型，不加命令条款）
- 作用：agent 扫一眼即可定位目标表，避免反复 sql_query 探索
- 原则：**DWD 优先于 ODS**（DWD 已清洗并关联 dim 补全 flash_pn/item_control）

### 2. 规则路由：意图识别 → 选表（本会话核心）

- `agentic_data_api.py` 新增 `_ROUTING_KEYWORDS`（业务词→候选表）+ `route_tables(question)`
  → 返回 `(候选表 top-8, 知识源标记 {glossary, knowledge})`
- **dws_indicator_w 收紧**（用户业务规则）：只在 `周/周报/周ecc/ecc分布/周分布/fbb比率/fbb_ratio/指标` 触发，
  不用"良率/坏块/批次/波动"等泛词误路由
- 20 场景验证：**18/20 命中**（2 个合理不命中：场景14 表清单、场景20 血缘，见 `scenario_routing_test.md`）
- 期望表已按用户修正同步（场景 1/2/8 去 dim_base_wo_di；场景7 术语表；场景12 +dwd_mes_lot；
  场景 1/6/12/13/18 去 dws_indicator_w）

### 3. 数据库信息注入：每表【业务定义】+ 适用提示（prompt 33k → 26k，省 21%）

- `_build_compact_catalog` 输出每表一行：`- {table}: {【业务定义】段} ｜ 适用: {hint}`
- 只取完整描述里的【业务定义】（表是干什么的），【粒度】【指标】【核心维度】【核心字段】不注入
- 完整业务描述存入 `_OM_TABLE_DESC_CACHE`（进程级缓存），供 `get_table_info` 按需取
- 完整 prompt 见 `current_system_prompt_routing.md`（25,970 字符）

### 4. 新增 `get_table_info(table)` 工具（一次拿全）

- 返回：**业务描述（OpenMetadata）+ 结构（列/类型）+ DolphinScheduler 血缘/计算逻辑 + 上下游 + 构建工作流**
- 组合现有 `get_table_schema` + `get_lineage`，agent 一次调用不用分三次
- 已注册进完整模式 ToolPack（`agentic_data_api.py`） + 模板工具描述 #19
- **修复（2026-08-10 二次）**：
  1. schema 部分缺 schema 推导（schema 为空时 REST 拉结构失败）→ 补 `get_current_db_name` 推导（同 get_table_schema）
  2. 血缘传裸名匹配不到（cache key 是 `st_embed.xxx` 完整名）→ `get_table_lineage` 加裸名模糊匹配（`endswith(".表名")`），所有调用者受益
  3. 验证通过：`get_table_info("ods_mes_production_report")` 返回 description + schema + upstream(`masterdata_db.dim_wo`, `mes_db.dwd_yield_lot_station`) + fields 计算逻辑
- **瘦身（2026-08-11）**：A 去重 schema 里的重复 description（只留顶层）；C 过滤 fields——只留 `expr!=列名` 真计算 + 列描述含 取自/来自/解析/别名/派生 的派生列（如 `burnin_time`=item 的 time_elapse、`test_number`=note JSON 解析，血缘解析器抓不到这类改名，靠列描述兜底，expr 直接放列描述）。验证：`dwd_dut_result_w` JSON 11,447 字符、fields 55→23 条、upstream/downstream 完整、burnin_time 别名关系可见。用户确认"工单"路由词与 upstream/downstream 顺序均维持现状。

### 5. 注入改造：路由建议 + 知识源引导 + 工具说明

`database_context` 现包含：
```
## 数据库信息（30 表一行简化索引）
## 本次问题相关表（路由识别）   ← route_tables 实时命中
## 业务术语与口径（13 术语）
## 术语与知识辅助                 ← 命中失效/errorcode/原因时注入
## 工具说明（get_table_info 一键拿全 / get_table_schema / get_lineage / get_glossary_term）
- 扩展引导：查不到→get_lineage 追上下游 / get_table_schema 探索
```

### 6. 知识源路由（术语库/知识库）

- 触发词：`失效/不良/errorcode/含义/定义/原因/根因/怎么解决/为什么`
- 术语库 `get_glossary_term`：已启用
- 知识库 `knowledge_retrieve`：**未建**（触发词与引导保留，待建好即启用）

---

## 二、当前状态

- **后端运行中**：PID 需新会话确认，配置 `configs/openai.toml`，端口 5670
- **20 场景批量测试后台跑**：`/tmp/scen20_results/progress.log` 看进度，结果在 `/tmp/scen20_results/scen_N.json`（注：注入改为【业务定义】版后已重启重跑）
- **交付物**：
  - `current_system_prompt_routing.md` —— 当前完整 prompt（25,970 字符，业务定义版）
  - `scenario_routing_test.md` —— 规则路由测试文档（20 场景 + 判定标准）
  - `plan_routing_calc_expand.md` —— 方案文档（决策点全部确认）
  - `/tmp/route_preview.py` —— 路由验证脚本（SCEN 已同步期望表）
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

### 复跑路由测试
```bash
.venv/bin/python /tmp/route_preview.py
# 期望：18/20 ✓（场景14/20 合理不命中）
```

### 单场景端到端
```bash
CONV=$(python3 -c "import uuid; print(uuid.uuid4())")
bash /tmp/scenario_test.sh "$CONV" "SHCS26074748 工单在 MES 里良率水平如何？从哪一天开始偏低？主要 errorcode 是什么？" 900
# 完成后查最终答案：
curl -s "http://127.0.0.1:5670/api/v1/chat/dialogue/messages/history?con_uid=$CONV"
```

### 批量 20 场景
```bash
/tmp/run_20_batch.sh   # 后台：nohup /tmp/run_20_batch.sh > /tmp/scen20_batch.log 2>&1 &
# 进度：tail /tmp/scen20_results/progress.log
```

---

## 四、关键文件索引

| 文件 | 作用 |
|---|---|
| `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py` | `_TABLE_ROUTING_HINTS`、`_ROUTING_KEYWORDS`、`route_tables`、`get_table_info`、`_OM_TABLE_DESC_CACHE`、注入改造 |
| `packages/dbgpt-core/src/dbgpt/agent/util/dolphinscheduler_client.py` | 血缘客户端（get_table_lineage，get_table_info 复用） |
| `packages/dbgpt-core/src/dbgpt/agent/util/openmetadata_client.py` | 表描述/结构/术语（get_table_info 复用） |
| `current_system_prompt_routing.md` | **当前完整 prompt（21,244 字符）** |
| `scenario_routing_test.md` | 规则路由测试文档 |
| `plan_routing_calc_expand.md` | 方案文档（决策点已定） |
| `/tmp/route_preview.py` | 路由验证脚本（SCEN 20 场景 + 期望表） |

---

## 五、给新会话的下一步建议

1. **确认后端运行** + 查 20 场景批量测试结果（`/tmp/scen20_results/progress.log`）
2. **分析测试结果**：重点看 agent 是否主动用 `get_table_info` 拿完整信息算指标、失效类是否走 `get_glossary_term`；
   若路由命中的表 agent 没查全，调 `_ROUTING_KEYWORDS` 关键词
3. **知识库待建**：`knowledge_retrieve` 触发词已留，建好 knowledge_space 后配置即启用
4. **提示词设计原则（用户强调）**：修"工具能力"优于加"命令规则"；提示词改动默认"信息型"
5. **遗留优化（用户已认可方向，未实施）**：MCP 工具瘦身（`search_metadata`/`semantic_search` 让模型查术语时乱搜，
   术语查询应走 `get_glossary_term`，可选从 MCP 段隐藏/降权）

---

## 六、已知限制

- **规则路由靠关键词**：同义词/新业务词需手动加 `_ROUTING_KEYWORDS`；组合问题可能漏表（有索引+get_table_info 兜底）
- **闲聊意图判定**：prompt 常驻小简化描述（~0.6k），闲聊轮不浪费；agent 自行判断要不要查数据
- **knowledge_retrieve 未启用**：知识库未建，失效分析暂时只靠 `get_glossary_term`
- **get_table_info 描述缓存**：`_OM_TABLE_DESC_CACHE` 进程级，TTL 30min，OpenMetadata 更新后最长 30min 生效
