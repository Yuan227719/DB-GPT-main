# 交接文档：react-agent 上下文方案收尾（memory_duplication_analysis 未完成项）

> 日期：2026-08-10
> 项目：DB-GPT monorepo，`/v1/chat/react-agent`（半导体测试数据分析，st_embed 库 / FL412E / SHCS26074748）
> 目的：承接 `memory_duplication_analysis.md`（2026-08-03）中**未完成方案**，作为新会话的起点

---

## 一、当前运行状态（新会话先确认）

- **后端运行中**：PID 需新会话确认（`ps aux | grep "dbgpt start webserver"`），配置 `configs/openai.toml`，端口 5670
- **前端已部署**：`packages/dbgpt-app/src/dbgpt_app/static/web`，构建 id `rX9Aw-mBYULu41I5WLOEx`
- **git 未提交改动**：`agentic_data_api.py`、`base_agent.py`、`react_agent.py`、`react_parser.py`、`openmetadata_client.py`、`conn_kyuubi.py`、`ManusLeftPanel.tsx`、`index.tsx`、`web/locales/*/chat.ts`
- **swap**：已加 `/swapfile2`（6G，总 9G），用于前端构建防 OOM
- 后端日志 `/tmp/dbgpt_server.log`；前端构建日志 `/tmp/frontend_build*.log`

---

## 二、2026-08-10 已完成并验证的修复（本次会话）

> 这些是 2026-08-10 三个会话逐步完成的，全部已重启/重建生效，端到端验证通过。

### 后端
| 改动 | 文件 | 说明 |
|------|------|------|
| `max_timeout` 600→1200 | `base_agent.py:138` | 复杂任务不再被 10 分钟截断 |
| 超时 final_content 兜底 | `agentic_data_api.py` ~4849 | 超时/未 terminate 时不再暴露原始 ReAct 文本：最后一步 html_interpreter 成功→"已生成 HTML 报告"；否则"已达 N 步限制，见上方步骤" |
| `step.thought` 实时推前端 | `agentic_data_api.py` thinking_chunk 分支 | 清洗后思考增量实时推前端（`**Action**` 星号格式已支持） |
| thinking 字段持久化 | 同上 | 思考文本累积进 history/live step 的 `thinking` 字段，刷新后恢复 |
| 残留"思考中"占位清理 | `run_agent` 持久化前 | 清掉 running 占位，避免最终 view 卡死步骤（曾现于 7860940b step-20） |
| `[step]` 诊断日志 | `_append_or_replace_step` | 每步创建/替换打日志，方便排查 step 丢失 |
| `elapsed_seconds` 持久化 | `run_agent` view payload | 总耗时落库，完成后前端仍显示 |
| 思考清洗支持 `**Action**` 星号格式 | clean_chunk 正则 | 模型输出 `**Action**:` 带星号，旧正则清洗不生效 → 思考卡片显示 Action Intention/Reason |

### 前端
| 改动 | 文件 | 说明 |
|------|------|------|
| B2 思考卡片（内容+进度+计时） | `ManusLeftPanel.tsx` StepCard isThinkingStep | "思考中"小胶囊升级为卡片：实时思考 + 第 N/总 步 + 已思考 mm:ss |
| header 显示 thought+action | 同上 `summarizeThoughtText` | "思考摘要 · 下一步：{action}" |
| `cleanThoughtText` 统一清洗 | 同上（模块级） | B2 卡片/header/ThoughtBubble 显示前去掉 Action/Intention/Reason/Input 行 |
| 对话总计时 | `index.tsx` | 消息区顶部 sticky "总耗时 mm:ss"，发送/checkLive 启动、done 停止；restoreFromHistory 读 `elapsed_seconds` |
| HTML 刷新后 auto-preview | `index.tsx` restoreFromHistory | 完成后 iframe 渲染 HTML 报告（与 SSE final 一致） |
| live 轮询 2.5s→1s | `index.tsx` checkLive | 刷新后思考内容更实时 |
| 思考内容从 `thinking` 字段恢复 | `index.tsx` applyLiveSteps / restoreFromHistory | 优先读 `s.thinking` |

### 验证结果
- **v_html_0810/0811/0812 端到端**：17/20/12 步全 done（0812 有一次模型偶发格式错乱触发 act() 提示重试后恢复），0 残留思考中占位，html_interpreter 含 `[html]` output
- **elapsed_seconds 真实落库**：v_html_0812 = 433.2s → 前端显示"总耗时 7:13"
- **刷新后 HTML**：iframe 渲染完整 FL412E 报告
- **清洗**：mock + 真实会话均不含 Action Intention/Reason

### 踩坑记录
- **index.tsx 漏 import `useCallback`**：`next.config` 的 `ignoreBuildErrors` 让它构建成功但运行时 `ReferenceError`。改前端必查 hooks import。
- **前端构建 OOM**：`next build` 在 "Collecting page data" 阶段被 kill。解决：加 6G swapfile（`sudo fallocate -l 6G /swapfile2 && mkswap && swapon`），`rm -rf .next out` 后重试。
- **prettier 必跑**：改 index.tsx/ManusLeftPanel.tsx 后必须 `npx prettier --write` 再构建，否则构建报错。

---

## 三、`memory_duplication_analysis.md` 未完成方案（下一步重点）

> 上下文方案（build() 后 clear memory、view 修复、task_progress 渲染、紧凑表清单、术语注入、get_table_schema 等）**大部分已实施 ✅**。以下是 **⏳ 待确认/未完成**项，按优先级排列。

### 优先级 1：运行时稳定性（10.5 清单）
| 待做 | 解决 | 位置 |
|------|------|------|
| **服务错误识别**（500/waitlist/forward → 清晰提示"模型服务繁忙"，而非"格式不正确"） | 10.1/10.3 | `llm_client.py` / `react_agent.py` / `base_agent.py` 错误路径 |
| **增强重试**（指数退避 5-8 次，替代固定 3 次/10s） | 10.1 | `base_agent.py` thinking 重试逻辑（~1148） |
| **防重复循环**（记录最近 N 次 (action, action_input)，连续相同注入干预） | 10.2 | `base_agent.py:1085-1099`（现有 `_LOOP_WARN_THRESHOLD` 需验证是否生效） |
| **prompt 探索引导**（禁 information_schema/SHOW TABLES、schema=st_embed、空结果不重复查询） | 10.2 | `workflow_prompt`（`agentic_data_api.py`） |
| **解析器容错**（坏输出恢复：检测到 `"sql":`/`"todos":` 还原对应工具）+ 重试提示更具体 | 10.3 | `react_parser.py` |

### 优先级 2：表路由优化（方案 6，§9.2）
- **A. 每表加"适用场景"提示**（轻，立竿见影）：紧凑清单每张表后加 `适用: 良率/坏块比率/批次波动` 路由提示。改 `_build_compact_catalog` 格式化 + 路由映射表
- **B. 问题路由知识库**（中）：20+ 场景→目标表+SQL 模板 KB，agent 用 `knowledge_retrieve` 先查
- **建议**：先 A 后 B

### 优先级 3：经验闭环（方案 7，§9.3）
- 采集（请求完成落 `(问题, 用过的表, SQL, 成功/失败, 耗时)`）→ 沉淀（LLM 提炼 `问题类型→表→SQL模板`）→ 应用（L1 更新路由提示 / L2 运行时检索注入 / L3 动态路由）→ 反馈
- 经验闭环是**方案 6A 和方案 2 的自动化内容来源**
- MVP：先落采集层（记录表），再沉淀脚本

### 优先级 4：其余待确认
| 待做 | 说明 |
|------|------|
| 改动点 2：fragment id 加固（§5.3） | 可选双保险：`Role.write_memories` 记录本轮 fragment id，`ReActAgent.read_memories` 过滤，不依赖 clear() |
| 方案 1：跨 schema 字典表纳入清单 | `embed_db.dim_indicator`、`masterdata_db.dim_test_item`、`embed_db.dim_errorcode_information` 等业务字典表（已部分被 `get_glossary_term` 覆盖，是否还需纳入待定） |
| 方案 3：术语库扩充 | ErrorCode 分类、测项枚举、指标来源表加进「商规EMBED生产测试术语库」 |
| 方案 4：血缘工具 `get_table_lineage` | 覆盖场景 20（表上下游），OpenMetadata `get_entity_lineage` |
| 方案 5：探索引导 prompt | 复杂问题先 get_table_schema/查字典表，避免盲目 sql_query |

---

## 四、如何重启 / 重建 / 测试

### 重启后端
```bash
cd /home/taoyuan/projects/DB-GPT-main
# 先杀旧进程
ps aux | grep "dbgpt start webserver" | grep -v grep | awk '{print $2}' | xargs -r kill; sleep 3
nohup .venv/bin/dbgpt start webserver --config configs/openai.toml >> /tmp/dbgpt_server.log 2>&1 &
# 端口 5670
```

### 重建前端
```bash
cd /home/taoyuan/projects/DB-GPT-main/web
npx prettier --write pages/index.tsx new-components/chat/content/ManusLeftPanel.tsx   # 必须先过格式
rm -rf .next out
nohup npm run compile >> /tmp/frontend_build.log 2>&1 &   # 约 7 分钟，OOM 用 swap 兜底
# 完成后：
rm -rf ../packages/dbgpt-app/src/dbgpt_app/static/web/*
cp -r out/* ../packages/dbgpt-app/src/dbgpt_app/static/web/
```

### 测试
```bash
# 端到端（真实模型，10-20 分钟）
/tmp/test_html_0810.sh   # 发复杂问题 + 等完成（改 conv 名避免冲突）
# 前端验证（mock，秒级）
NODE_PATH=/home/taoyuan/projects/DB-GPT-main/web/node_modules node /tmp/verify_clean.js
NODE_PATH=/home/taoyuan/projects/DB-GPT-main/web/node_modules node /tmp/verify_all_final.js
# 后端诊断日志（每步创建）
grep "\[step\]" /tmp/dbgpt_server.log | tail
# 上下文用量（后端每轮 LLM 调用时打日志）
grep "Context status" /tmp/dbgpt_server.log | tail
```

---

## 五、关键文件索引

- `memory_duplication_analysis.md` — **上下文方案主文档**，含全部未完成项（§9.1 状态总览）
- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py` — react-agent 主逻辑（SSE、live、tools、history 注入、final_content、thinking 持久化）
- `packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py` — ReAct 骨架（max_timeout、重试、消息组装、上下文管理）
- `packages/dbgpt-core/src/dbgpt/agent/expand/react_agent.py` — act() 兜底、read_memories
- `packages/dbgpt-core/src/dbgpt/agent/util/react_parser.py` — ReAct 解析（`**Action**:` 归一化、容错待做）
- `packages/dbgpt-core/src/dbgpt/agent/util/openmetadata_client.py` — OpenMetadata REST/MCP
- `packages/dbgpt-core/src/dbgpt/agent/util/llm/llm_client.py` — LLM 流式（thinking_chunk 来源）
- `web/pages/index.tsx` — 前端主逻辑（SSE 处理、live 轮询、总计时、HTML auto-preview）
- `web/new-components/chat/content/ManusLeftPanel.tsx` — 步骤卡片、思考卡片、header 摘要
- `configs/openai.toml` — 模型配置（Deepseek-V4-Flash，proxy/openai）

---

## 六、给新会话的下一步建议

1. 先确认后端/前端运行状态，`git status` 看未提交改动
2. **优先做优先级 1（运行时稳定性）**：服务错误识别 + 增强重试 + 防重复循环，这三个直接提升复杂任务成功率（当前 0812 有 1 次格式错乱触发重试）
3. 再做**表路由优化（方案 6A）**：每表加"适用场景"提示，减少 agent 盲目 sql_query 探索
4. 若要做经验闭环（方案 7），先实现采集层（记录 `问题→用过的表→SQL→结果`）
5. 注意：改前端必须 prettier + 查 hooks import；构建 OOM 用 swap 兜底
