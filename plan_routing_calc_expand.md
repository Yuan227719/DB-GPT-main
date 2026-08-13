# 方案：路由选表 + 计算逻辑注入 + 多轮扩展

> 日期：2026-08-10 ｜ 前置：方案6A（每表 `适用:` 路由提示，已上线）+ 规则路由验证（18/20 命中，`scenario_routing_test.md`）
> 本方案新增三块：① 期望表修正 ② 路由选中表→DolphinScheduler 计算逻辑注入（指标口径）③ 第一轮路由查不到→多轮扩展

---

## 一、需求与目标

1. **期望表修正**：用户对 20 场景的期望目标表做了修改（去冗余、补必需），需同步路由测试集。
2. **计算逻辑**：agent 需要知道指标字段怎么算（口径）——**不预注入 prompt**，用 `get_lineage(表)` 工具按需取（用户确认，见第三节）。
3. **知识源路由**：失效/不良代码/查原因类问题 → 链接术语库（`get_glossary_term`）与知识库（`knowledge_retrieve`，待建）。
4. **多轮扩展**：第一轮路由从限定表里查不到 → 支持多轮扩展搜索，不死磕初始选表。

---

## 二、期望表修正（用户改动，已确认）

| # | 原期望表 | 修正后 | 改动原因 |
|---|---|---|---|
| 1 | ods_mes, dwd_mes_lot, dws_indicator_w, **dim_base_wo_di** | 去掉 dim_base_wo_di | 良率/errorcode 查询不需要工单维度 |
| 2 | dwd_item, dwd_subitem, dwd_w, **dim_base_wo_di** | 去掉 dim_base_wo_di | 测项/子项查询不需要工单维度 |
| 7 | dws_fa_ecc_plane, dws_fa_bb_block, **ods_mes_production_report** | dws_fa_ecc_plane, dws_fa_bb_block, **术语表** | FWError/VPError 含义走 `get_glossary_term` 术语库，不是 MES 表 |
| 8 | dwd_power_current_di, **dim_base_wo_di** | 去掉 dim_base_wo_di | 电流比例查询单表即可 |
| 12 | dim_base_wo_di, dws_indicator_w, ods_mes | **+dwd_mes_lot** | 返测良率也查 lot 明细 |

> **关键推论**：路由目标不只有"数据表"，还有"知识源"（术语表 → `get_glossary_term`）。路由结果需区分两类，注入时分别处理。

---

## 三、计算逻辑：不预注入，工具按需取（用户确认 2026-08-10）

### 3.1 结论

路由选中表后，**不预注入"计算口径段"**——`get_lineage(table)` 工具已能按需返回该表的
字段级计算逻辑（`fields`: 列←表达式+引用列），预注入只会膨胀 prompt，违背 token 优化目标。

### 3.2 提示词只做两件事

1. **列出工具**（现有即可用）：`sql_query`、`get_table_schema`、`get_lineage`、`get_glossary_term`
2. **一句信息型说明**（做法，非命令）：
   - 查某表**字段怎么算 / 上下游依赖** → 用 `get_lineage(表名)`（返回 fields 计算逻辑 + upstream/downstream）
   - 查表结构 → `get_table_schema(表名)`；术语含义 → `get_glossary_term(术语)`

### 3.3 最终提示词结构（路由后）

```
## 数据库信息
- 数据库名: st_embed
- {选中表 N 张完整描述}
## 其他表索引
- {其余表，一行：表名 ｜ 适用:}
## 业务术语与口径
- {13 术语}
## 工具说明
- sql_query: 执行 SQL（Trino 语法）
- get_table_schema(表): 查看任意表结构
- get_lineage(表): 查看表字段计算逻辑（列←表达式）+ 上下游表
- get_glossary_term(术语): 查业务术语含义
```

**收益**：无"计算口径"段 → prompt 更小；agent 需要口径时调 `get_lineage` 按需拿完整信息（比预注入的更准、可覆盖任意表）。

---

## 3.4 知识源路由：失效/不良代码/查原因 → 术语库 + 知识库（用户确认 2026-08-10）

### 路由目标扩展：不只"数据表"，还有两类"知识源"

| 问题类型 | 路由目标 | 引导工具 |
|---|---|---|
| errorcode/不良代码/**失效含义** | 术语库 | `get_glossary_term(术语)` |
| **失效原因 / 查原因 / 怎么解决 / 根因** | 知识库 | `knowledge_retrieve("...")` |
| 两者都有（如"看失效原因"） | 术语库 + 知识库 | 两者 |

### 触发词

```
"失效" / "不良" / "errorcode" / "错误码" / "含义" / "原因" / "根因" / "怎么解决" / "为什么"
```

命中 → 注入"术语与知识辅助"段（路由结果含 `__GLOSSARY__` / `__KNOWLEDGE__`）：

```
## 术语与知识辅助（失效/不良/查原因类）
- errorcode/不良代码/失效 含义 → get_glossary_term(术语) 查术语库
- 失效原因/经验/解决方案 → knowledge_retrieve("...") 查知识库
```

### 现状确认（2026-08-10）

- `get_glossary_term`：**已启用**（OpenMetadata 术语库）
- `knowledge_retrieve`：**知识库未建**（用户确认）。触发词与引导设计**保留在方案中**，待知识库建好即启用；**当前失效/不良/含义类问题先靠 `get_glossary_term`**

---

## 四、多轮扩展重试

### 4.1 问题

现状：agent 用选中表 `sql_query` 返回空/报错时，可能直接 terminate（历史场景 4/18/19 早退、场景 9/10 空结果终止）。

### 4.2 方案：血缘扩展引导 + 全表索引兜底（信息型，不加禁令）

- **全表索引始终注入**（已有）：30 表一行 `表名 ｜ 适用:`，agent 知道自己有哪些表可用
- **血缘扩展引导**：注入段加一句信息型提示——

```
若所选表查不到所需数据，可用 get_lineage(表) 查看该表的上游/下游表，换表再查；
或 get_table_schema(任意表) 查看结构确认。
```

- **效果**：agent 第一轮选中表查不到 → 主动 `get_lineage` 追上下游 / `get_table_schema` 探索其他表 → 多轮扩展，而不是死磕/早退

### 4.3 备选：代码级自动扩展（复杂，暂不做）

第一轮查询返回空时，代码自动放宽路由（降关键词阈值、扩大到 top-15）重新注入。
- 优点：确定性
- 缺点：需请求级状态跟踪、拦截查询结果，实现复杂；且空结果不一定该扩表（可能是口径问题）

> 建议先做 **4.2**（零代码、引导现有工具），观察效果，不够再上 4.3。

---

## 五、整合架构（用户新流程 2026-08-10）

**核心转变**：prompt **只留简化表描述**（常驻，很小）；**完整信息（描述+结构+血缘+计算逻辑）按需检索进上下文**，不预注入。

```
## 数据库信息（常驻 prompt，简化描述 ~0.6k）
- 数据库名: st_embed
- {30 表一行：表名 ｜ 适用:}        ← 不再有完整描述
## 工具说明
- sql_query / get_table_schema / get_lineage / get_table_info / get_glossary_term
- get_table_info(表): 一次返回 完整描述 + 结构 + DolphinScheduler 血缘/计算逻辑 + 上下游

用户问题
  → route_tables(question)（关键词路由）
      ├─ 命中 → 预拉选中表完整信息（get_table_info）进上下文，agent 第一轮就能用
      └─ 未命中 → 不预拉，agent 靠简化描述自由发挥"猜"去哪找表
  → agent ReAct 循环（循环循环）
      ├─ 需要某表 → get_table_info(表)：完整描述+结构+血缘+计算逻辑 → Observation 进上下文（只出现一次）
      ├─ 失效/不良/含义 → get_glossary_term(术语) [+ knowledge_retrieve(知识库，待建)]
      ├─ 查不到 → get_lineage 追上下游 / 换 get_table_info 其他表
      └─ 直至回答
```

### 为什么这版更好

- **prompt 极小**：30 表一行简化描述（~0.6k），每轮 ReAct 都带但不浪费（对比 13.5k 全描述）
- **完整信息只出现一次**：按需 `get_table_info` 拉入，作为 Observation 进上下文，不重复
- **意图门控问题消失**：prompt 常驻就是小简化描述，闲聊轮也才 0.6k，不用纠结"闲聊 vs 数据"；真正要表时 agent 自调工具
- **路由成为引导而非门控**：命中预拉加速，未命中不阻塞（简化描述保视野 + 自由发挥）

### 新增工具：`get_table_info(table)`

组合现有能力，一次拿全（agent 不用分三次调）：

```python
{
  "table": "dws_indicator_w",
  "description": "【业务定义】周粒度指标汇总表…（OpenMetadata 完整描述）",
  "schema": ["guid", "indicator_name", "indicator_value", ...],   # get_table_schema
  "fields": {"indicator_value": {"expr": "…", "refs": [...]},      # get_lineage 计算逻辑
             "gbb_cnt": {"expr": "uecc+psf+esf+bb_skip", ...}, ...},
  "upstream": [...], "downstream": [...], "build_workflows": [...]
}
```

---

## 六、实施步骤

1. **简化表描述**：`_build_compact_catalog` 改为只输出一行索引（`表名 ｜ 适用:`），不再拼完整描述
2. **新工具 `get_table_info(table)`**：`agentic_data_api.py` 新增 @tool，组合 OpenMetadata 完整描述 + `get_table_schema` + `DolphinSchedulerClient.get_table_lineage`
3. **路由接入**：新增 `_ROUTING_KEYWORDS` + `route_tables(question)`；请求进来路由命中时预拉选中表 `get_table_info` 进上下文
4. **工具说明段**：`database_context` 改为 简化表描述 + 工具说明（`get_table_info` 一键拿全、`get_lineage` 追上下游、`get_glossary_term` 查术语）
5. **验证**：复跑 `/tmp/route_preview.py`；抽 1-2 场景端到端看 agent 是否主动 `get_table_info` 拿完整信息算指标、失效类走 `get_glossary_term`

---

## 七、决策点（已确认 2026-08-10）

1. ~~计算逻辑注入~~ **已解决**：不预注入，靠 `get_lineage` / `get_table_info` 工具按需取
2. ~~新增工具 get_table_info~~ **确认保留**：返回 完整描述+结构+血缘/计算逻辑+上下游（组合 OpenMetadata + get_table_schema + get_lineage）
3. **术语表处理**：**只引导 `get_glossary_term`**，术语问题不注入表描述
4. **多轮扩展**：**先做信息型引导**（4.2），不够再上代码级自动扩展
5. **dws_indicator_w 张力**：**选 A**——期望表去掉它，路由词保持收紧；agent 需要时用 `get_lineage`/`get_table_info` 找到。测试集已同步（场景 1/6/12/13/18 期望去掉 dws_indicator_w，复跑 18/20 ✓）
