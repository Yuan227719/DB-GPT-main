# 交接文档：get_table_info 瘦身 + Burnin 口径修正 + 前端折叠/滚动条（2026-08-11）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`，半导体测试数据分析（st_embed）
> 关联：`HANDOVER_20260810_routing.md`（规则路由 + 简化注入 + get_table_info）、
>       `HANDOVER_20260810_lineage_glossary.md`、`HANDOVER_20260810_memory.md`
> 本会话：get_table_info 瘦身（A+C）→ 前端思考折叠/滚动条 → Burnin 语义排查 + 路由/口径修正

---

## 一、本会话做了什么（全部已生效）

### 1. get_table_info 瘦身（A+C，前端 token 减负）

- **A 去重**：schema 里的 `description` 与顶层 `result["description"]` 重复 → 去掉 schema 里的
- **C 过滤 fields**：只保留"有计算/改名/别名派生"的列：
  1. `expr!=列名` 真计算（如 `NOW()`、`dim.wo_status`）
  2. 恒等映射但列描述含 `取自/来自/解析/别名/派生` 的派生列（如 `burnin_time` 取自 item 的 time_elapse）——血缘解析器抓不到这类改名，靠列描述兜底，expr 直接放列描述
- 验证：`dwd_dut_result_w` JSON 11,447 字符、fields 55→23 条、upstream/downstream 完整、burnin_time 别名关系可见
- **用户确认维持现状**："工单"路由词不动；upstream/downstream 顺序不动

### 2. 前端：思考折叠 + 可见滚动条（已构建部署）

- **根因**：`web/styles/globals.css` 全局 `::-webkit-scrollbar { display: none }` 隐藏所有滚动条
- **思考折叠**：`ManusLeftPanel.tsx` 的 `ThoughtBubble` —— 长思考（首行后 >80 字符）默认折叠只留首行 + 展开箭头，点击展开/收起完整思考；短思考不变
- **可见滚动条**：`side-bar.tsx` 会话列表 + `index.tsx` 主聊天消息区 加 `scrollbar-default` 类（6px 灰滚动条）
- **未动**：思考胶囊（思考中卡片）、正在思考状态栏
- 部署：`cd web && npm run compile` → `rsync -a --delete web/out/ packages/dbgpt-app/src/dbgpt_app/static/web/`（新 buildId 已生效）

### 3. Burnin 语义排查（大量数据核实，关键）

**真实口径（数据查证）**：
- **宽表 `dwd_dut_result_w.burnin_time` = 各测项 time_elapse 的全量拷贝**（随 item 变化，一个 result_guid 内 53 个不同值），**不是真烧录时长**
- **真烧录时长在 `dwd_fa_ecc_die_di.burnin_time`**：eMMC 产品线特有，由宽表 `item_name LIKE 'VDT_INFO_CYCLE_%' AND subitem_name LIKE 'VDT_COUNT_VCC%'` 行的 time_elapse 过滤得到
- **单位秒**，历史数据可能有 min（分钟）形式（旧口径，需×60），现行为秒
- **eUFS 等无 VDT 测项的产品**：`dwd_fa_ecc_die_di.burnin_time` 为空
- 样例（LTW26087357，eMMC YL512E）：7913 SN，41~296 秒，avg 218.3s，双簇（短簇 42~46s / 长簇 255~296s）

### 4. Burnin 代码修正（agentic_data_api.py）

| 位置 | 改动 |
|---|---|
| `_ROUTING_KEYWORDS` | burnin/burin/burn-in/burn in/烧录/老化 → **`["dwd_fa_ecc_die_di"]`**（最准）；不再指向宽表/温度表 |
| `_TABLE_ROUTING_HINTS` | dwd_fa_ecc_die_di 标注"Burnin 烧录时长（最准，eMMC VDT...，秒，历史可能 min）"；dwd_dut_result_w 标注"burnin_time 是各测项 time_elapse 拷贝，非真烧录"；dwd_power_temperature_di 去掉 burnin |
| `_COLUMN_SEMANTIC_OVERRIDES`（新增） | (dwd_fa_ecc_die_di, burnin_time) 准确描述；(dwd_dut_result_w, burnin_time) time_elapse 拷贝说明 |
| `_build_glossary_section` | 内置硬编码术语 `烧录/Burnin（老化）`（OM 术语库暂没有，指向 dwd_fa_ecc_die_di；将来 OM 补了同名术语可删） |
| 表描述 | **保留【业务定义】+ 适用**（讨论过去掉，用户决定保留——路由未命中时模型靠表描述自选表） |

### 5. 端到端验证（eMMC 烧录场景）

- 模型流程：`get_table_info(dwd_fa_ecc_die_di)`（读修正口径）→ `dim_base_wo_di` 查工单状态（wait_return_goods=已发放/未完成）→ `dwd_fa_ecc_die_di` 统计 burnin_time
- 答案（conv=25651989）：7913 SN、41~296s、avg 218.3s、中位 274.1s、双簇分布 —— 与数据验证完全一致

---

## 二、当前状态

- **后端运行中**：PID 需新会话确认（本次 2556837），配置 `configs/openai.toml`，端口 5670
- **代码改动**：`agentic_data_api.py`（路由/提示/列修正/术语）、`ManusLeftPanel.tsx`/`index.tsx`/`side-bar.tsx`（前端）、`globals.css`（原样，scrollbar-default 已有）
- **前端**：已构建部署到 `static/web`（新 buildId），刷新浏览器生效

---

## 三、如何重启 / 测试

### 重启后端
```bash
cd /home/taoyuan/projects/DB-GPT-main
kill <旧PID>
nohup .venv/bin/dbgpt start webserver --config configs/openai.toml >> /tmp/dbgpt_server.log 2>&1 &
# 端口 5670
```

### 路由验证
```bash
.venv/bin/python - <<'PYEOF'
import sys
sys.path.insert(0, "packages/dbgpt-app/src/dbgpt_app/openapi/api_v1")
from agentic_data_api import route_tables
for q in ["烧录测试时长是多少？", "Burnin 测试时长", "老化测试做了多久？"]:
    print(q, "->", route_tables(q)[0][:4])
PYEOF
# 期望：烧录/老化/Burnin 都命中 dwd_fa_ecc_die_di
```

### Burnin 端到端（eMMC 工单）
```bash
# 用 LTW26087357（YL512E/eMMC，有 VDT）或 SHCS26074748（eUFS4.1，无 VDT 应返回空）
# 走 /v1/chat/react-agent，看模型是否 get_table_info(dwd_fa_ecc_die_di) 并正确算 burnin_time
```

### 直接查数据（复现口径）
```bash
# 连接脚本模板见 /tmp/query_*.py（ZK 发现 kyuubi_adhoc + LDAP p_dp_all_rpt）
# 关键查询：dwd_fa_ecc_die_di.burnin_time（eMMC VDT）；dwd_dut_result_w.burnin_time（time_elapse 拷贝）
```

---

## 四、关键文件索引

| 文件 | 作用 |
|---|---|
| `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py` | `_COLUMN_SEMANTIC_OVERRIDES`、burnin 路由/提示/术语、get_table_info A+C、表描述 |
| `web/new-components/chat/content/ManusLeftPanel.tsx` | ThoughtBubble 折叠、cleanThoughtText、capsule/状态栏 |
| `web/pages/index.tsx` | 主聊天消息区 scrollbar-default、stepThoughts 渲染 |
| `web/components/layout/side-bar.tsx` | 会话列表 scrollbar-default |
| `web/styles/globals.css` | `::webkit-scrollbar display:none`（根因）、`.scrollbar-default` |
| `web/out/` → `packages/dbgpt-app/src/dbgpt_app/static/web/` | 前端构建产物（已同步） |
| `HANDOVER_20260810_routing.md` | 上会话：规则路由/简化注入/get_table_info |

---

## 五、给新会话的下一步建议

1. **③ 未完成样品判定条件（未做）**：`dim_base_wo_di` 有 `undone_amount`/`wo_status`，但"未完成样品"在测试数据的判定口径没定义（undone_amount？缺某测项？test_result？）。eMMC 场景模型直接把 wait_return_goods 工单全当未完成，需确认业务口径
2. **dolphinscheduler 启动噪音（可选修复）**：`connector/service/service.py:207` 用 `ensure_future` 后台重水合所有 connector，dolphinscheduler 非 MCP 类型报 `Unknown connector type`，异常未接住。非阻塞（DS 走 `_load_dolphinscheduler_config` 直连），可选在重水合循环跳过非 MCP 类型
3. **列修正只在 get_table_info 生效**：`get_table_schema` 直调仍见 OM 旧描述；若要一致，需在 get_table_schema 也应用 `_COLUMN_SEMANTIC_OVERRIDES`（用户未定）
4. **OM 源头未改**：口径硬编码在代码里，OM 列描述/术语库没动。若想让 OM 成为源头，需在 OM UI 改列描述 + 术语库加 burnin 术语（加白名单）
5. **提示词原则（用户强调）**：修工具能力优于加命令规则；提示词默认信息型

---

## 六、已知限制

- **Burnin 是 eMMC 特有**：eUFS 等无 VDT 的产品 `dwd_fa_ecc_die_di.burnin_time` 为空，模型需识别产品类型（product_type=eMMC）再取
- **burnin_time 双形式**：历史 min / 现行秒，描述已标注需×60，模型需留意
- **宽表 burnin_time 语义误导**：已用描述/提示纠正（time_elapse 拷贝非真烧录），但 OM 源头未改
- **路由未命中**：靠表描述【业务定义】自选表（用户决定保留描述）
- **`</think>` 标签**：模型 thinking 流含 `</think>`（无 `<think>`），前端显示原样，用户决定不动
