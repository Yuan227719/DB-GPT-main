# 交接文档：2026-08-12 会话（模型"回答慢"根因破案 → 下一步处理 skills）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`（半导体测试数据分析，st_embed / 商规EMBED）
> 关联：`HANDOVER_20260812_docker_redeploy.md`（镜像修复+部署）→ 本会话纯诊断，无代码改动 → **下一步：处理 skills（Problem A 技能不自动触发）**
> 本会话：**定位"模型回答慢"的真正根因（后端请求排队，非拥挤/非思考模式/非GPU满），并量化 agent 请求上下文与工具空间**

---

## 一、本会话核心结论（"模型慢"已破案）

**结论一句话**：模型本身不慢（空闲时飞快），慢 = **模型后端请求排队**（推理框架吞吐瓶颈）。dashboard 显示"空闲"是假象，因为**它只统计外网并发，看不到内网（服务器/本机）的 agent 请求**。

### 证据链（全部实测）

| # | 现象 | 证据 |
|---|---|---|
| 1 | 不是模型拥挤 | 直连 aicode.longsys.com 返回 `429 "User concurrency limit reached, max: 3, timeout: 60s"`——**per-key 并发上限 3**，非模型算力满 |
| 2 | 不是思考模式慢 | 同一 "1+1" 请求：空闲 **0.3s** / 忙时 **61.7s**（≈429 的 60s 超时）；`reasoning_tokens=0`、`reasoning_content=null` → 无思考痕迹 |
| 3 | 模型本身能力没问题 | 写 500 字短文：TTFT **0.19s**、**105 token/s** 飞快 |
| 4 | 不是网络 | 网关自报 `time_to_first_token_ms: 30780`，客户端只占 ~170ms |
| 5 | dashboard"空闲"= 只显示外网并发 | **用户破案**：真实并发 = 外网 + 内网（服务器 10.5.3.67 / 本机打 aicode.longsys.com 都是内网路径） |
| 6 | 低并发≠低算力 | agent 请求上下文巨大，算力消耗按 token 计不是按请求数计 |

### 机制：两层排队，只有一层是算力

```
你的请求
  ↓
① 网关 policy 限流（per-key max 3, 60s）── 配额策略，非算力（429 就是这层，提 key 并发可绕）
  ↓
② 推理框架请求队列（vLLM/TRT 等）── 算力层 ← 0.3s vs 61.7s 抖动就在这层
  ↓
GPU 计算（prefill 消化 2万+ token 输入 + decode 逐 token 生成）
```

**结论：本质是算力限制**（推理框架吞吐 = GPU 能力 + 框架并发配置）。LongSys 未扩容前无法从 DB-GPT 侧根治；本地可控 = 精简上下文 / 错峰。提 key 并发只解决①层，②层 GPU 忙照样排队。

---

## 二、量化：你的每次对话上下文

从日志真实 payload tokenize（tiktoken cl100k）：

| 项 | 数值 |
|---|---|
| 每次 LLM 请求 | **18,747 → 26,585 tokens**（随轮次递增），完整历史最高 **~54k** |
| 固定 system prompt | **~12k tokens**（27k+ 字符），每次请求都原样带，不随对话增长 |
| system 构成 | 1 条 system（19 个工具描述+规则+表清单）+ user 历史 + assistant 历史 |

**19 个声明工具 vs 实际只用 6 个**（真实对话实测）：

- 实际用：`sql_query`(69次) `terminate`(18) `get_table_info`(18) `todowrite`(15) `code_interpreter`(9) `html_interpreter`(6)
- 声明但未用 13 个：**skill 4件套**（load_skill/execute_skill_script_file/get_skill_resource/execute_skill_script）+ 通用杂项（shell_interpreter/load_file/load_tools/execute_tool/execute_analysis/knowledge_retrieve）+ 场景相关但本次未用（get_table_schema/get_glossary_term/get_lineage）
- 用户顾虑"上下文不能砍"→ 已澄清：砍**必需信息**不行，但**从不用的工具**（13/19）和**跨层重复**（todowrite 在 prompt 出现 12 次、sql_query 9 次）是纯浪费；工具空间越杂模型越容易挑错，删废重是"帮模型聚焦"

---

## 三、本会话动作

1. **停止本机 3 个测试容器**（`dbgpt-verify` / `dbgpt-verify2` / `dbgpt-withdata-test`，已 Exited）——**不是占槽主因**（一直空闲），停掉无副作用，如需清理可 `sudo docker rm`
2. **更新记忆**（`project_docker_deploy_0812.md`、`reference_debug_env.md`）：推翻"模型思考模式慢"旧结论 → 真因是后端排队；dashboard 只显示外网并发

**无代码改动**（本会话纯诊断 + 实测脚本在 `/tmp/sse_diag*.py`、payload 样本在 `/tmp/payloads2/`，仅分析用）。

---

## 四、待办：处理 skills（Problem A）⏳ 本会话未实施

### Problem A：skill 不自动触发（indicator-calc）

- **现象**：指标类问题（"FL412E 工单各工序良率趋势…做完整 HTML 报告"）没触发 indicator-calc，agent 直接 sql_query 探索表。
- **已核实**：system prompt 技能清单含 indicator-calc（日志确认），但 LLM 不调 `select_skill`/`get_skill_resource`——技能靠 LLM 自觉选择，不可靠。
- **拟修复**（待实施）：问题命中**强指标词**时代码直接设 `pre_matched_skill=indicator-calc`，强制进技能模式。
  - 位置：`agentic_data_api.py:2255` `pre_matched_skill` 逻辑（现仅 ext_info 显式 skill_name 才匹配）；`_mentions_excel`(2286) 是现成参考。
  - 建议强词：良率/DPPM/FBB/坏块/ECC/温度/电流/burnin/烧录/老化/箱线图/测试工单/测试样品/周报/日报/失效；**不匹配**宽泛词：工单/趋势/月。
  - **上传文件时跳过**自动匹配（避免劫持 Excel 分析）。
  - **关键词范围待用户确认**（见 `HANDOVER_20260811_indicator_calc.md` 与 `project_indicator_calc_skill.md`）。

### 新增方向（本会话发现）：skill 工具清单 vs 预匹配机制

处理 skills 时一并确认：**SKILL.md 是怎么被加载的？**
- 若靠 `pre_matched_skill` 自动注入 skill_prompt → LLM 可能**不需要** `load_skill`/`execute_skill_script` 等 skill 工具显式调用
- 若需 LLM 主动 `load_skill` → 那才是 Problem A 的根因（LLM 不可靠）
- 结论会影响 19 工具清单是否可精简（skill 4件套 是否保留）

---

## 五、当前运行状态

- **本机后端**：PID `3596544`（端口 5670），日志 `/tmp/dbgpt_server.log`，当前闲置（12:02 后无模型请求）
- **服务器**（10.5.3.67:5670）：容器 `dbgpt` 活跃（同事在用，16:39-16:40 密集请求），`--restart unless-stopped`
- **本机测试容器**：3 个已 Exited 50 分钟
- **技能**：`/api/v1/skills/list` = 11 个，indicator-calc 在列（见 `skills/indicator-calc/SKILL.md`）
- **未提交代码改动**（非本会话产生，来自 redeploy/Problem B 会话）：`Dockerfile.custom`、`openmetadata_client.py`、`docker/requirements-pinned.txt`(新)、`agentic_data_api.py`、`base_agent.py`、`react_agent.py`、`react_parser.py`、`conn_kyuubi.py`、`web/pages/index.tsx`、`ManusLeftPanel.tsx` 等

---

## 六、关键文件索引

| 文件 | 作用 |
|---|---|
| `agentic_data_api.py:2255` | `pre_matched_skill`（Problem A 修复点） |
| `agentic_data_api.py:2286` | `_mentions_excel`（自动匹配现成参考） |
| `skills/indicator-calc/SKILL.md` | indicator-calc 触发词 + 流程 |
| `skills/` | 11 个技能目录（含 skill 4件套 相关工具） |
| `/tmp/sse_diag*.py` | 本会话实测脚本（429/TTFT/排队验证） |
| `/tmp/payloads2/r*.txt` | 真实请求 payload 样本（上下文 tokenize 用） |
| 记忆 `project_docker_deploy_0812.md` | 本会话破案结论（后端排队/dashboard 外网假象/上下文量化） |

---

## 七、下一步建议（处理 skills）

1. **先和用户确认强指标词范围**（Problem A 的关键词清单），确认后实施 `pre_matched_skill` 自动预匹配（上传文件跳过）。
2. **弄清 SKILL.md 加载机制**：`pre_matched_skill` 是否自动注入 skill_prompt？LLM 是否需要显式 `load_skill`？→ 决定 skill 4件套 工具是否可从 19 清单精简。
3. 顺手可做：工具清单精简（13 个未用工具中，`get_lineage`/`get_table_schema`/`get_glossary_term` 场景有价值保留；skill 4件套 + shell_interpreter + load_file/load_tools/execute_tool/execute_analysis/knowledge_retrieve 若确认无用可删，量化省 token）。
4. 模型慢的根治依赖 LongSys 扩容（多实例/更高 GPU 并发）；本地缓解 = 精简上下文 + 错峰，详见本会话结论。
