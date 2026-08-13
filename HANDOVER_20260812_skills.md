# 交接文档：2026-08-12 skills 处理（Problem A：指标问题自动触发 indicator-calc）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`（半导体测试数据分析，st_embed / 商规EMBED）
> 关联：`HANDOVER_20260812_latency_skills.md`（本日模型慢诊断 + skills 待办入口）；`HANDOVER_20260812_indicator_calc.md`（Problem B 已修，Problem A 待修）；`HANDOVER_20260811_indicator_calc.md`
> 本会话：**只摸清 skills 机制与修复方案，未改任何 skill 代码（用户明确要求）**。下个会话照此文档实施。

---

## 一、任务目标（Problem A：skill 不自动触发）

**现象**：指标类问题（"FL412E 工单各工序良率趋势…做完整 HTML 报告"）没触发 indicator-calc，agent 直接 sql_query 探索表。

**根因**：技能靠 LLM 自觉调 `select_skill`/`load_skill`，**不可靠**。LLM 常跳过技能直接干活。

**修复方向（已定，待实施）**：问题命中**强指标词**时代码直接设 `pre_matched_skill=indicator-calc`，强制进技能模式——不需要 LLM 自觉。

---

## 二、已摸清的 skill 加载机制（关键，实施依据）

### `pre_matched_skill` 设置后会发生什么（全部已核实）
1. `agentic_data_api.py:4403-4420`：构建 `skill_prompt_context` 注入 system prompt（`## 已加载技能指令（{name}）`）。
2. `agentic_data_api.py:4671`：`is_skill_mode = pre_matched_skill is not None`。
3. `agentic_data_api.py:5461-5496`：agent 开头发射 **"Load Skill: {name}"** step（展示 SKILL.md instructions）。

**结论**：`pre_matched_skill` 一旦设置，技能 prompt 自动注入 + 自动展示，"Load Skill" 步骤自动出现。**LLM 无需再调 `load_skill`**。因此自动预匹配即可让 indicator-calc 生效。

### 当前 `pre_matched_skill` 逻辑（agentic_data_api.py:2265-2278）
```python
pre_matched_skill = None
if skill_name:                          # 仅 ext_info 显式指定才匹配
    pre_matched_skill = registry.get_skill(skill_name)
    # ...大小写兜底...
    if pre_matched_skill:
        react_state["matched"] = pre_matched_skill
        react_state["skill_prompt"] = pre_matched_skill.get_prompt()
```
→ **只在 ext_info `skill_name` 时设置**。这就是要扩展的点。

### 相关代码位置
| 位置 | 内容 |
|---|---|
| `agentic_data_api.py:1799` | `user_input = dialogue.user_input`（自动匹配的匹配源） |
| `agentic_data_api.py:2265-2278` | `pre_matched_skill`（**修复点**，在 ext_info 判断后加关键词匹配） |
| `agentic_data_api.py:2296-2310` | `_mentions_excel(text)`（**现成参考**：关键词 in 判断） |
| `agentic_data_api.py:2325-2374` | `select_skill` 工具（LLM 自觉选择路径，保留不动） |
| `agentic_data_api.py:2376+` | `load_skill` 工具（LLM 自觉加载路径，保留不动） |
| `agentic_data_api.py:4403-4420` | skill_prompt_context 注入 system prompt |
| `agentic_data_api.py:4671` | is_skill_mode |
| `agentic_data_api.py:5461-5496` | "Load Skill" step 发射 |
| `skills/indicator-calc/SKILL.md` | 技能名 `indicator-calc`，触发词+流程 |

### 技能注册
- `/api/v1/skills/list` = **11 个技能**，indicator-calc 在列。
- 技能目录：`skills/{indicator-calc, pdf, xlsx, docx, pptx, mcp-builder, skill-creator, agent-browser, csv-data-analysis, walmart-sales-analyzer, financial-report-analyzer}`。
- `registry.get_skill("indicator-calc")` 可用（名 = SKILL.md frontmatter `name: indicator-calc`）。

---

## 三、实施方案（下会话照做）

### 核心改动（agentic_data_api.py，一处）
在 `pre_matched_skill` 的 ext_info 分支（2265-2278）后追加：

```python
# 若 ext_info 未指定技能，且用户上传了文件 → 跳过自动匹配（避免劫持 Excel 分析）
# 否则命中强指标词 → 自动预匹配 indicator-calc
if not pre_matched_skill and not file_path:
    if _mentions_indicator(user_input):
        pre_matched_skill = registry.get_skill("indicator-calc")
        if pre_matched_skill:
            react_state["matched"] = pre_matched_skill
            react_state["skill_prompt"] = pre_matched_skill.get_prompt()
            logger.info(f"Auto pre-matched skill from indicators: indicator-calc")
```

配套：加 `_mentions_indicator(text)` 辅助函数（参考 `_mentions_excel`:2296），关键词清单见下节（**待用户确认**）。

### 不动的部分
- `select_skill` / `load_skill` 工具保留（LLM 显式要求时仍可走）。
- ext_info `skill_name` 显式指定逻辑保留（优先于自动匹配）。
- 上传文件场景跳过自动匹配（`file_path` 非空），避免 Excel/文件分析被劫持。

---

## 四、强指标词清单（⏳ 待用户确认，未定）

交接文档标注"关键词范围待用户确认"，本会话未获得答案（用户要求先写文档）。

### 候选方案
1. **保守强词（推荐）**：良率/DPPM/FBB/坏块/ECC/温度/电流/burnin/烧录/老化/箱线图/测试工单/测试样品/周报/日报/失效。不匹配宽泛词（工单/趋势/月）。误触率最低。
2. **含英文缩写**：追加 BB/GBB/UECC/PSF/ESF/SLC/TLC/QLC（风险：BB 可能出现在型号/批次名，FBB 可能是产品型号前缀）。
3. **全量词（含宽泛词）**：按 SKILL.md 现有触发词（含 工单/趋势/月/指标/BB 等）。触发最多但误触率高。

> 注意：SKILL.md 的触发词包含 工单/趋势/月 等宽泛词，但 handover 建议**排除**这些，避免"查工单 SN"误触发。**实施前必须让用户确认清单。**

### 一个设计细节
`_mentions_indicator` 用子串匹配（如 `_mentions_excel`），但**英文缩写建议词边界匹配**（避免 "bb" 匹配到 "abbc"），可参考 `route_tables`(259) 或 `_mentions_excel` 的 `keyword in lowered` 风格，按用户确认的词定。

---

## 五、测试计划（实施后）

1. **指标问题触发**：问"FL412E 各工序良率趋势" → 日志出现 `Auto pre-matched skill from indicators` + 前端出现 "Load Skill: indicator-calc" 步骤 + 走 SKILL.md 算法而非裸 sql_query。
2. **宽泛词不触发**："查一下这个工单的 SN" → 不触发，走普通路径。
3. **上传文件不触发**：上传 Excel 问问题 → 不自动进 indicator-calc（走 Excel 技能/文件分析）。
4. **显式 ext_info 优先**：指定 skill_name 时仍用指定的。
5. **回归**：`select_skill`/`load_skill` 手动路径仍可用。

---

## 六、附带发现（可选的后续优化，本次不动）

### 工具清单：19 个声明 vs 6 个实际使用（真实对话实测）
- 实际用：`sql_query`(69) `terminate`(18) `get_table_info`(18) `todowrite`(15) `code_interpreter`(9) `html_interpreter`(6)
- 声明未用 13 个：skill 4件套（load_skill/execute_skill_script_file/get_skill_resource/execute_skill_script）+ 通用杂项（shell_interpreter/load_file/load_tools/execute_tool/execute_analysis/knowledge_retrieve）+ 场景相关（get_table_schema/get_glossary_term/get_lineage）
- **用户顾虑**："上下文不能砍，砍了模型都不知道要什么"。应对：砍**必需信息**不行，但**从不用的工具**和**跨层重复**（todowrite 在 prompt 出现 12 次）是纯浪费。**此优化需用户明确同意后另做，不在 Problem A 范围内。**

### 上下文量化（模型慢相关，见 latency 文档）
- 每次请求 18k-27k tokens，system prompt 固定 ~12k。模型慢根因 = 后端排队（非拥挤/非思考），dashboard 只显示外网并发。

---

## 七、当前运行状态

- **本机后端**：PID `3596544`（端口 5670），日志 `/tmp/dbgpt_server.log`。
- **服务器**：10.5.3.67:5670 容器 `dbgpt` 活跃（同事在用）。
- **测试容器**：dbgpt-verify / dbgpt-verify2 / dbgpt-withdata-test 已 Exited（本日停掉）。
- **未提交代码**：Dockerfile.custom / openmetadata_client.py / requirements-pinned.txt（redeploy 会话）；agentic_data_api.py / base_agent.py / react_agent.py / react_parser.py / conn_kyuubi.py / web（Problem B 会话）。**本会话无代码改动。**

---

## 八、下个会话第一步

1. **问用户确认强指标词清单**（第四节），确认后实施第三节方案。
2. 重启后端（改 agentic_data_api.py 后）：
   ```bash
   cd /home/taoyuan/projects/DB-GPT-main
   pkill -f "dbgpt start webserver"; sleep 3
   nohup .venv/bin/dbgpt start webserver --config configs/openai.toml >> /tmp/dbgpt_server.log 2>&1 &
   ```
3. 跑第五节测试计划。
