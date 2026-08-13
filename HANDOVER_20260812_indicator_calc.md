# 交接文档：2026-08-12 会话（Problem B 前后端交互彻底修复 + 连接器固定；Problem A skill 未处理）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`（半导体测试数据分析，st_embed / 商规EMBED）
> 关联：`HANDOVER_20260811_indicator_calc.md`（Problem B 前端守卫初版、indicator-calc 技能构建、Problem A 待修）
> 本会话：**定位并修复 Problem B 的真正根因（后端架构），思考胶囊/连接器固定/配置调整；Problem A（skill 不自动触发）仍未处理**

---

## 一、本会话已完成

### 1. 【核心】Problem B 真正根因：后端 history_steps 随生成器死亡冻结（已修复）

**根因**（上一会话只修了前端守卫，没抓到后端）：
- `history_steps`（用于持久化 view + `/live` 实时步骤）原来由 **SSE 生成器主循环** 构建。
- **刷新页面会取消生成器（GeneratorExit）→ 循环停止消费 stream_queue → history_steps 冻结**在当时的步数。
- agent 后台任务（run_agent）继续跑，但持久化的是冻结的残缺步骤。
- 实测证据（用户会话 bb55eb52）：agent 实际跑 16+ 步（op_snapshots），持久化 view 只有 1 个 todowrite step，而 task_plan 却 4/5 完成——todos 由 agent 工具直接更新（存活），steps 由生成器构建（冻结）。

**修复**（`agentic_data_api.py`，架构重构）：
1. 把生成器主循环的事件处理抽成 **`process_agent_event(event) -> List[str]`**（更新 history_steps / _todo_list / live updated_at + 返回待发 SSE 串）。
2. **run_agent 自己消费 stream_queue 构建 history_steps**（`generate_reply` 作子任务 + 事件循环），SSE 串塞进 **`sse_queue`**；生成器只做转发（`while True: yield sse_queue.get()`）。
3. **`_LIVE_AGENT_STEPS[conv_id]` 提前到生成器开头注册**（human 落库后、慢速初始化前），否则发送后立刻刷新时 /live 未注册返回 running=false，前端不进 live 轮询。
4. `process_agent_event` 顶部每事件刷新 `live["updated_at"]`（防 >15min 僵尸兜底误判 running=false）。

**实测验证**（真实模型 + 真实断开）：
- 断开时 1 步 → 断开后 `/live` 增长到 12 步 → 持久化 **11 个真实步骤**（get_table_info+sql_query×10）+ 真实答案。
- 发送后 1 秒 `/live` 即返回 running=true（提前注册生效）。
- 前端加载该会话，11 步卡片全部渲染。

### 2. 前端守卫（本会话完善 + 上会话初版）

| 守卫 | 作用 | 位置 |
|---|---|---|
| `activeStreamConvRef` | 发送瞬间 router 竞态：跳过流式会话的重复 loadConversation | index.tsx:644/808/1589/2120 |
| `renderedConvRef` | 已渲染消息归属；loadConversation 空历史/不完整历史不盲目清空/替换 | index.tsx:647/1660/2422/2652 |
| trailingHuman 守卫 | 最新一轮只有 human 时不整体替换已显示内容 | index.tsx:2687 |
| checkLive 重试 | "最新一轮只有human" 会话重试 /live 数秒，等后端注册进 live | index.tsx:2626 |
| checkLive running=false | 先清 thinking + running 步骤置 done（防"正在思考"卡住） | index.tsx:2569 |
| /live 带 task_plan | 刷新后任务清单恢复 | agentic_data_api.py:5410/6190 |
| restoreFromHistory | 恢复 taskPlan + elapsed_seconds + HTML 预览 | index.tsx:2417 |

### 3. 连接器/数据库固定（2026-08-11 尾部，本会话确认）

`index.tsx` 模块级：
```ts
const PINNED_DB_NAMES = ['st_embed'];
const PINNED_CONNECTOR_KEYWORDS = ['openmetadata', 'dolphin', 'st_embed'];
```
- 固定连接器/数据库：不能 X 掉、自动选中保持、锁图标；DB 锁定 st_embed 不能切换其他库。
- 说明：数据库已锁死为 st_embed（如要临时查其他库需放宽）。

### 4. 配置调整（2026-08-12）

- `agentic_data_api.py:5121`：`ReActAgent(max_retry_count=50, max_timeout=3600)`（步数上限 = max_retry_count，超时 60 分钟）
- `base_agent.py:138`：默认 `max_timeout: int = 3600`

---

## 二、待处理（Problem A：skill 不自动触发）⏳ 未处理

**现象**：指标类问题（含良率/坏块/errorcode，如"FL412E 工单各工序良率趋势…做完整 HTML 报告"）没触发 indicator-calc，agent 直接 sql_query 探索表。

**已核实**：system prompt 技能清单包含 indicator-calc（日志确认），但 LLM 没调 `select_skill`/`get_skill_resource`——技能靠 LLM 自觉选择，不可靠。

**拟修复（待用户确认匹配词范围，未实施）**：
- 加"指标问题自动预匹配"：问题命中**强指标词**时代码直接设 `pre_matched_skill=indicator-calc`，强制进技能模式（SKILL.md 核心流程生效）。
- 位置：`agentic_data_api.py:2255` `pre_matched_skill` 逻辑（现仅 ext_info 显式 skill_name 才匹配）。`_mentions_excel`(2286) 是现成参考。
- 建议只匹配强指标词（良率/DPPM/FBB/坏块/ECC/温度/电流/burnin/烧录/老化/箱线图/测试工单/测试样品/周报/日报/失效），不匹配宽泛词（工单/趋势/月）。
- 上传文件时跳过自动匹配（避免劫持 Excel 分析）。

---

## 三、当前运行状态

- **后端运行中**：PID `3596544`（`ps aux | grep "dbgpt start webserver"`），端口 5670，日志 `/tmp/dbgpt_server.log`。
- **技能已加载**：`/api/v1/skills/list` = 11 个，indicator-calc 在列。
- **前端已部署**：buildId `wXWKUkZh4aH4AO00IvkYA`（`static/web/_next/static/`）。
- **代码改动**（未提交）：`agentic_data_api.py`、`base_agent.py`（max_timeout）、`web/pages/index.tsx`（前端守卫+固定+重试）、`skills/indicator-calc/**`（既有）。
- 注意：上次清理时把残留的旧后端进程 kill -9 了，当前只有 1 个 webserver。

---

## 四、如何重启 / 测试

### 重启后端（改了 Python 后）
```bash
cd /home/taoyuan/projects/DB-GPT-main
pkill -f "dbgpt start webserver"; sleep 3
nohup .venv/bin/dbgpt start webserver --config configs/openai.toml >> /tmp/dbgpt_server.log 2>&1 &
```

### 重建前端（改了 index.tsx 后）
```bash
cd /home/taoyuan/projects/DB-GPT-main/web
npx prettier --write pages/index.tsx
npm run compile   # next build && next export → web/out
cp -r out/* ../packages/dbgpt-app/src/dbgpt_app/static/web/
# 浏览器刷新（无需重启后端，前端是静态站）
```

### 回归测试重点
1. **发送后立刻刷新**：live 实时步骤/思考胶囊应出现（提前注册 live + 前端重试已修）。
2. **运行中刷新 → 跑完**：步骤完整（不冻结）、持久化 view 含全部步骤、最终答案正常。
3. **消息不被清空**：发送瞬间/刷新后消息保留。
4. **连接器固定**：OpenMetadata/DolphinScheduler/st_embed 无 X、自动选中。
5. **断开续跑**（若模型配合）：断开后 /live steps 继续增长、持久化完整。

---

## 五、关键文件索引

| 文件 | 作用 |
|---|---|
| `agentic_data_api.py:~1821` | 提前注册 `_LIVE_AGENT_STEPS`（发送后立刻刷新也能 live） |
| `agentic_data_api.py:5121` | `ReActAgent(max_retry_count=50, max_timeout=3600)` |
| `agentic_data_api.py:5200+` | run_agent：generate_reply 子任务 + 消费 stream_queue 构建 history_steps |
| `agentic_data_api.py:5492+` | `process_agent_event()`：事件处理核心（history/todo/live updated_at + SSE 串） |
| `agentic_data_api.py:~5968` | 生成器 SSE 转发循环（读 sse_queue） |
| `agentic_data_api.py:2255` | `pre_matched_skill`（Problem A 修复点） |
| `base_agent.py:138` | `max_timeout` 默认 3600 |
| `web/pages/index.tsx:644/647` | activeStreamConvRef / renderedConvRef |
| `web/pages/index.tsx:2626` | checkLive trailingHuman 重试 |
| `web/pages/index.tsx:2687` | loadConversation trailingHuman 守卫 |
| `web/new-components/chat/content/ManusLeftPanel.tsx:966-972,567-614` | 思考胶囊渲染 |
| `skills/indicator-calc/SKILL.md` | indicator-calc 触发词 + 流程（Problem A 相关） |

---

## 六、给新会话的下一步建议

1. **修 Problem A（skill 不自动触发）**：强指标词自动预匹配 indicator-calc（关键词范围先跟用户确认；上传文件时跳过）。参考 `_mentions_excel`(2286) + `pre_matched_skill`(2255) + `react_state["matched"]/["skill_prompt"]` 注入。
2. **数据库锁定可放宽**：目前 st_embed 锁死不能切换，用户若需查其他库，把 DB picker 的阻止切换逻辑放宽成"仅默认选中可切换"。
3. **既有待办**：方案 7 经验闭环（攒10/人工确认/flow，设计已定稿暂缓，见 `project_memory_duplication_todo.md`）；burnin 未完成样品待办（见 `project_burnin_08011.md`）。
