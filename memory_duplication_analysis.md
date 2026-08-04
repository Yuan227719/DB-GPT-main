# ShortTermMemory 与 historical_dialogues 消息重复问题：分析与修复方案

> 日期：2026-08-03
> 范围：`/v1/chat/react-agent` 接口（`agentic_data_api.py`）
> 结论：**消息重复确认存在**。附带发现：模型"记不住上下文"的根因**不在重复**，而在历史加载链路的两处断点。
> 本文档给出证据链、选定方案与具体改动点。

---

## 1. 问题结论

`_load_thinking_messages`（`base_agent.py:1838`）组装最终发给 LLM 的消息列表时，
**同一段历史对话会以两种形式各出现一次**：

| 形式 | 来源 | 消息位置 |
|------|------|---------|
| 扁平 human/AI 文本（全量历史轮次） | chat_history 表（conversation service） | 消息 #2 `historical_dialogues` |
| ReAct step（Question/Thought/Action/Observation，最近 5 步） | gpts_messages 表 → ShortTermMemory 恢复 | 消息 #3 `memory_list` |

两条路径都源自同一份会话内容，只是**读表不同、粒度不同**，导致发往 LLM 的消息里内容重叠，浪费 token 且可能干扰模型判断。

**但注意**：本接口当前 `gpts_messages` 缺少 action_report（见第 4 节断点 2），
build() 恢复实际为空，所以"历史轮次两路径重复"在现状下**尚未真正发生**；
真正发生的重复是**重试轮里当前输入重复**（第 3.2 节）。一旦修好持久化，第 3.1 节的
历史轮次重复才会浮现，因此两个问题必须一起设计（见第 5 节）。

---

## 2. 现状：两条上下文注入路径

### 路径 A：historical_dialogues（全量历史，扁平文本）

- 加载点：`agentic_data_api.py:4284-4314`
- 数据源：`conv_service.get_history_messages(conv_id)`（`dbgpt-serve/.../conversation/service/service.py:187`）
  → 读 chat_history 表（`StorageConversation` 的 message_storage）
- 内容：**全部**历史轮次，按"偶数位=human、奇数位=ai"交替注入（`base_agent.py:1987-1998`）
- 注意：当前 user_input 不在其中。`agentic_data_api.py:3505` 的 `add_user_message(user_input)`
  只进内存对象，到 `4877` 行运行结束后才 `save_to_storage()` 落库。所以历史对话是**上一轮请求**的完整内容。

### 路径 B：memory_list（ShortTermMemory，ReAct step）

- 读取点：`base_agent.py:1901` `read_memories(observation)` → `ReActAgent.read_memories`（`react_agent.py:274`）
  → `self.memory.read()` → `ShortTermMemory.read`（`memory/base.py:770`）→ 直接返回 `_fragments`
- 数据源分两部分：
  1. **build() 恢复的历史**：`agentic_data_api.py:4244` `build()`（`base_agent.py:359-372`）
     → gpts_messages 表 `get_agent_history_memory`（`memory/gpts/gpts_memory.py:152`）
     → `recovering_memory`（`role.py:458`）→ `write_batch` 写入 ShortTermMemory
  2. **本轮运行写入**：每轮 `write_memories`（`role.py:276-392`）写一个 fragment
- 由于 `ShortTermMemory(buffer_size=5)`（`memory/agent_memory.py:316`），恢复全量历史后
  **只保留最近 5 个 step**（`memory/base.py:437-463` 逐个 `write` 时裁剪）

---

## 3. 重复点详细分析

### 3.1 主要重复：历史轮次在两路径各出现一次

假设上一轮请求留下了 8 个 ReAct step（多轮对话），本轮请求组装消息时：

- 消息 #2 `historical_dialogues`：这 8 轮对话的扁平 human/AI 文本（**全部**）
- 消息 #3 `memory_list`：这 8 轮中最近 5 个 step（Question/Thought/Action/Observation）

**同一轮对话内容出现两次**。这是最主要、最确定的重复。

### 3.2 次要重复：重试轮中当前 user_input 出现两次

- round 0 结束时 `write_memories` 写入的 fragment 含 `question` 字段（`role.py:334-335`，
  仅 `current_retry_counter == 0` 时注入），`question = received_message.content`（含 db_summary_context）
- round 1+ 重读 `memory_list` 时，这个 fragment 变成 `"Question: <user_input>"`（消息 #3）
- 而 user_prompt（消息 #4，`base_agent.py:2022-2026`）又是当前输入 `"Observation: <user_input>"`

→ 重试轮中当前输入以 "Question:" 和 "Observation:" 两种前缀各出现一次。

### 3.3 代码注释里的行号已过期

`agentic_data_api.py:4279-4283` 注释引用 `base_agent.py L1373`，但当前 `memory_list` 的
extend 实际在 `base_agent.py:2006-2007`。且注释"同一轮 user_input 会出现多次"的机制
与 3.1 / 3.2 的描述略有出入（见上文）。

---

## 4. 附带发现：模型"记不住上下文"的根因（不是重复）

### 4.1 现象

聊天时模型无法记住之前轮次的内容。排查发现：**模型每个请求几乎收不到自己过去的回答**，
两条历史注入路径都拿不到上一轮的 AI 输出。

### 4.2 断点 1：AI 回复以 `view` 消息保存，historical_dialogues 全部跳过

- `agentic_data_api.py:4875`：AI 回复用 `storage_conv.add_view_message(...)` 保存
  （不是 `add_ai_message`），所以每轮在 chat_history 表 = `[human(问题), view(AI回复)]`
- `_append_view_messages`（`core/interface/message.py:1466`）只会给缺 view 的 ai 消息补 view，
  **不会把 view 转回 ai**
- `agentic_data_api.py:4300` 加载历史时：
  ```python
  if role_str == "view":
      continue   # ← 上一轮的 AI 回复全被跳过
  ```
- 结果：`historical_dialogues` 里**只有过去的用户问题，没有任何 AI 回答**
- 附带影响：跳过 view 后剩余全是 human 消息，而 `base_agent.py:1987-1998` 又按
  `i % 2 == 0 → HUMAN / i % 2 == 1 → AI` 重新标记角色 → **奇数位的用户问题被误标成 AI**

### 4.3 断点 2：gpts_messages 无 action_report，build() 恢复为空

- gpts_messages 唯一写入点 `_a_append_message`（`base_agent.py:1415`）只在 `receive()` 里被调用
- 本接口直接调 `agent.generate_reply(...)`（`agentic_data_api.py:4317`），**绕过了 receive**
  → 用户消息和最终回复都不写 gpts_messages；仅重试轮通过 `sender.send(retry_message, ...)`
  （`base_agent.py:802`）触发 receive 写入，但该消息无 action_report
- `llm_client` 的 `memory.push_message`（`agent/util/llm/llm_client.py:266`）只推消息队列，不落库
- `get_agent_history_memory`（`memory/gpts/gpts_memory.py:179`）严格过滤：
  ```python
  return [m["action_output"] for m in new_list if m["action_output"]]
  ```
- 结果：`get_agent_history_memory` 返回 `[]` → `recovering_memory` 恢复为空
  → memory_list 无历史 step（只有本轮 write_memories 写入的）

### 4.4 与重复问题的关系

| | 记不住上下文 | 重复 |
|---|---|---|
| 根因 | 两条历史路径**都拿不到**上一轮内容（view 被跳过 + gpts_messages 无 action_report） | 同一条对话被**两条路径同时注入** |
| 现状 | 模型几乎看不到自己的历史回答 | 历史轮次重复暂时没发生（恢复为空）；实际重复的是重试轮当前输入（memory_list 的 `"Question: ..."` vs user_prompt 的 `"Observation: ..."`） |

**关键联动**：一旦修好持久化让模型能记住（build() 恢复生效），memory_list 会重新装满历史；
若 historical_dialogues 也修好（view 不跳过），两条路径将真正重复。
**两个问题必须一起设计修复**，否则修好一个会放大另一个。

---

## 5. 选定方案：互补语义

### 5.1 目标语义

```
消息 #2 historical_dialogues = 全部过去轮次（扁平文本，来自 chat_history，含 AI 回复）
消息 #3 memory_list        = 仅当前这轮运行的 ReAct step（来自本轮 write_memories）
两者互不重叠：
  - 历史完整（不再受 buffer_size=5 窗口限制）
  - 保留本轮 ReAct 轨迹（Thought/Action/Observation 结构）
  - 不浪费 token，不干扰模型
```

> **前置条件**：historical_dialogues 要承担"全量历史"职责，必须先修好断点 1（见 5.5 改动点 3），
> 否则它仍是空的（只有用户问题）。改动点 1（清空 memory）必须与改动点 3 一起上线。

### 5.2 改动点 1（最小改动，作用域限本接口）—— ✅ 已实施

`agentic_data_api.py` `build()` 之后立即清空恢复到 ShortTermMemory 的历史：

```python
agent = await agent_builder.build()  # 异步构建 agent（会从 gpts_messages 恢复历史到 ShortTermMemory）
# 互补语义：全量历史由 historical_dialogues 提供（chat_history 表，见下）
# 清空 build() 恢复到 ShortTermMemory 的历史，使 memory_list 只包含本轮运行的 ReAct step
await agent.memory.clear()
```

效果：
- 本轮 round 0：`read_memories` 返回空 → memory_list 为空，消息仅 system_prompt +
  historical_dialogues + user_prompt，无重复
- 本轮 round 1+：memory_list 只含本轮各 step，与 historical_dialogues（仅过去轮次）不重叠
- 不删除 gpts_messages / chat_history 里的持久化数据；下一请求 build() 照常恢复再被清空，行为一致
- 只影响 `/v1/chat/react-agent` 接口，不影响其他入口点的默认 `build()` 行为

安全性核对：
- `AgentMemory.clear()` → `self.memory.clear()` → 清空 `ShortTermMemory._fragments`
  （`memory/agent_memory.py:404-407` → `memory/base.py:800-806`）
- gpts_memory（共享、持久化）不受影响；`task_progress_summary` 是实例普通属性，不受影响
- 本轮 step 通过 `write_memories`（`role.py:385` `self.memory.write(fragment)`）照常累积

### 5.3 改动点 2（可选加固，不依赖 API 主动清空）

若希望"memory_list 仅本轮"的语义内置到 agent 层（而非依赖调用方记得 clear），可在
`Role.write_memories` 中记录本轮创建的 fragment id，并在 `ReActAgent.read_memories`
中过滤：

```python
# role.py write_memories（约 385 行，await self.memory.write(fragment) 后）
if not hasattr(self, "_run_fragment_ids"):
    object.__setattr__(self, "_run_fragment_ids", set())
self._run_fragment_ids.add(fragment.id)   # 仅本轮 write_memories 创建的 fragment

# react_agent.py read_memories（约 283 行）
memories = await self.memory.read(observation)
run_ids = getattr(self, "_run_fragment_ids", set())
memories = [m for m in memories if m.id in run_ids]   # 只返回本轮 step
```

> 注：build() 恢复走 `write_batch`（`role.py:470`），不会进 `_run_fragment_ids`；
> 恢复的 fragment 保留原始 id，与本轮 `new_id()` 生成的新 id 天然区分。
> 此方案改动更大（跨 Role / ReActAgent），但语义自洽，不依赖调用方。
> **当前建议先采用改动点 1，改动点 2 作为后续加固预留。**

### 5.4 改动点 3（前置修复：让 historical_dialogues 真的包含历史 AI 回复）—— ✅ 已实施

当前 historical_dialogues 因跳过 view 消息而缺失 AI 回复（见 4.2），**必须先修复**才能承担
"全量历史"职责。两种改法（已采用改法 A + base_agent role 兜底）：

- **改法 A（推荐，改加载侧）**：`agentic_data_api.py:4300` 不再直接跳过 view，
  而是从 view 消息的 `history_payload` 中提取 `final_content`（AI 回答）作为 AI 回复注入：

  ```python
  if role_str == "view":
      # 从 view payload 中提取 final_content 作为 AI 回复
      try:
          payload = json.loads(content)
          final = payload.get("final_content")
          if final:
              historical_dialogues.append(
                  AgentMessage(content=final, role=_Role.AI)
              )
      except Exception:
          pass
      continue
  ```

  这样每轮 = `[human, ai, human, ai, ...]`，`base_agent.py:1987-1998` 的
  奇偶角色标记也能正确对齐，不再误标。

- **改法 B（改保存侧，改动面更大）**：`agentic_data_api.py:4875` 改用
  `storage_conv.add_ai_message(final_content)` 保存 AI 回复，让 chat_history 每轮 = `[human, ai]`。
  注意前端展示 / view 逻辑需相应调整。

> 建议先采用改法 A（只动加载侧，不动存储结构）。

### 5.5 改动点 4（长任务记忆：让 task_progress 真正渲染进 system prompt）—— ✅ 已实施

**背景**：ShortTermMemory `buffer_size=5`（已调至 10）只留最近 5 个 step；30 步任务里前 25 步在
memory_list 中全部不可见。设计上本有 `task_progress_summary`（`role.py:210-238`）作为
兜底——它把全部 step 摘要累积在实例属性 `_task_progress`（不随 buffer 淘汰），
注入 `context["task_progress"]`（`base_agent.py:1914-1916`）。

**问题**：该注入只在 system prompt 模板里有 `{{ task_progress }}` 占位符时才对模型可见。
本接口绑定的是 `workflow_prompt_template`（`agentic_data_api.py:4241`），
**模板里没有 `{{ task_progress }}`** → jinja2 对未引用变量静默丢弃，模型看不到。
（`task_progress` 只被传给了 `manage_context`，`base_agent.py:2017`，供压缩层当摘要用。）

**改法**：
- 改法 A：给 `workflow_prompt` 加 `{{ task_progress }}` 占位符。
  注意它是 f-string 拼接，需写成 `{{{{ task_progress }}}}` 才能最终让 jinja2 看到
  `{{ task_progress }}`。
- 改法 B：不 bind 自定义模板，改用 Role 默认 `_REACT_SYSTEM_TEMPLATE`
  （`react_agent.py:69-73` 已内置 `{% if task_progress %}`）。

> 建议先采用改法 A（保留现有 workflow_prompt 的 skills/connector 等注入）。

### 5.6 为何不选其他方案

| 方案 | 舍弃 | 原因 |
|------|------|------|
| 只留 memory_list（去掉 historical_dialogues） | 超过最近 5 步的历史 | 长对话丢失早期上下文 |
| 只留 historical_dialogues（去掉 build 恢复） | ReAct 结构化轨迹 | 本轮 Thought/Action 连续性是 ReAct 核心 |
| 全局删掉 build() 恢复 | — | `build()` 是 `ConversableAgent` 基类方法，影响所有入口点，风险过大 |

---

## 6. DB 元数据向量化注入问题与最终方案

### 6.1 现状链路

**写入侧（启动时一次）**：`dbgpt_app/base.py:33` 后台线程 `init_db_summary` →
`DBSummaryClient.db_summary_embedding`（`db_summary_client.py:69`）→ `RdbmsSummary`
用 connector 遍历所有表读元数据（Trino 下逐表 `DESCRIBE` + 查表注释）→
`DBSchemaAssembler` 分 chunk → 存 chromadb（`<dbname>_profile` 表级 +
`<dbname>_profile_field` 字段级）。之后每 30 分钟 `schema-check` 线程只在表名集合变化时
刷新（`connector_manager.py:137`，`_has_table_set_changed` 只跑 SHOW TABLES）。

**检索侧（每次提问必跑）**：`agentic_data_api.py:1644-1685` →
`get_table_info_no_throw()` 对 Trino 返回空（`MetaData.reflect` 被 patch 成 no-op）→
`get_db_summary(db, user_input, 20)`（每次提问无条件执行）→ `DBSchemaRetriever`
从 chromadb 检索 top-20 张表 → 每张表 `_retrieve_field` **全量返回字段**（上限 200）→
反序列化成完整 `CREATE TABLE` → 拼成 `db_summary_context` →
`agentic_data_api.py:4254` 拼进 user message。

### 6.2 它造成的问题

| 问题 | 机制 |
|------|------|
| **上下文膨胀** | 每次提问带 top-20 张表完整字段 → 超预算触发 ContextManager Layer 2 丢弃早期轮次（`compact.py:139`），而 task_progress 又没渲染（见 5.5 改动点 4）→ 丢的历史无补偿 = 放大器 |
| **schema 自身重复** | schema 拼进 user_input → `question` → round 0 memory fragment（`role.py:334-335`）→ 重试轮 memory_list 再现（问题 B） |
| **无关检索注入** | 闲聊也拉进 20 张"最相似"表 |
| **注意力稀疏（若改塞 system prompt）** | 全量 schema 进 system prompt 会让提示词过长，模型遵循指令效果下降 |
| **初始化开销** | Trino/Kyuubi 向量化要逐表 DESCRIBE，且通过 ZK 连接远程引擎，很慢（仅启动/表变化时，不随提问） |

### 6.3 结论：是不是它导致"看不到上下文"

不是主因，是放大器。主因是断点 1/2（view 跳过 + gpts_messages 无 action_report）。
schema 膨胀通过"撑爆上下文 → Layer 2 丢轮次 → 无 task_progress 补偿"放大该问题。

### 6.4 最终方案：紧凑表索引 + 按需取表结构工具

> 否决"全量 schema 进 system prompt"（注意力稀释）与"每问 top-20"（元数据不全、重复）两条路。

| 内容 | 放哪 | token 量 |
|------|------|---------|
| 表名 + 一句表描述（紧凑清单） | system prompt `{database_context}`，会话级缓存 | 很小，500 张表也仅几百行短文本 |
| 完整表结构（列/类型/注释） | **按需**：新增 `get_table_schema(table_name)` 工具 | 只在 LLM 想查某表时才取 |

**会话级缓存**（仿 `REACT_AGENT_MEMORY_CACHE`，`agentic_data_api.py:3478`）：
`conv_id -> 紧凑表清单`，首次涉库问题加载，后续请求复用注入。

**新增工具** `get_table_schema(table_name)`：返回指定表完整结构（列/类型/描述），
供 LLM 在需要时调用。元数据来源：**完全信任 OpenMetadata**（见 6.5 已定决策），
Kyuubi 仅负责数据查询。

**意图门控**：会话级判断是否涉库，涉库才建缓存注入；纯闲聊不注入。

**用户"查某表数据"的理想流程**：
```
用户: 帮我查 orders 表的数据
  → LLM: get_table_schema("orders")      ← 按需拿列名/类型
  → LLM: sql_query("SELECT * FROM orders LIMIT 50")
  → 返回数据 ✅
```
紧凑表清单让 LLM 知道有哪些表；`get_table_schema` 让 LLM 需要时拿任意表结构。
完整性、上下文体积、注意力三方面兼顾。

**删除**：`agentic_data_api.py:4253-4254` 把 schema 拼进 user message 的路径
（避免问题 B 的重复），schema 只经 system prompt 注入。

### 6.5 元数据源升级：OpenMetadata 作为数据目录（替代 chromadb 抓取）

用户已配置 OpenMetadata MCP connector（取 `商规EMBED` schema 下的表元数据）。
架构升级为**元数据面（OpenMetadata）与数据面（Kyuubi/Trino）分离**：

| | chromadb（现方案） | OpenMetadata（目标） |
|---|---|---|
| 描述来源 | 只能抓 DB COMMENT，质量不可控 | 治理过的业务元数据：表/字段描述、标签、业务术语 |
| 紧凑表清单 | 向量检索 top-k，可能不全 | 按 `schema=商规EMBED` 直接列全量，天然做清单 |
| 语义匹配 | 依赖 embedding 模型 | 描述本身够清晰，LLM 直接读 |
| 新鲜度 | 30min 定时检查 | 有版本/血缘，但可能滞后实际 schema |

```
OpenMetadata（元数据面）                  Kyuubi/Trino（数据面）
  ├─ 紧凑表清单：表名 + 中文描述           └─ sql_query（conn_kyuubi，已就绪）
  ├─ get_table_schema：列/类型/描述            实际数据查询
  └─ 会话级缓存 → 注入 system prompt
```

**两种集成方式**：
- **方式 A（服务端直连 OpenMetadata API，推荐做紧凑表清单）**：请求开始（首次涉库问题）
  直接调 OpenMetadata API 按 schema 拉全量表+描述 → 会话缓存 → 注入 system prompt。
  优点：确定性、一次拉全、不依赖 LLM 调用。
- **方式 B（现有 MCP connector 工具，做 get_table_schema）**：OpenMetadata MCP 工具暴露为
  agent 工具，LLM 按需调用。复用现有 connector 机制（`_select_connector_tools`，
  `agentic_data_api.py:317`）。缺点：让 LLM 主动枚举全表不可靠，不适合做表清单。

> 推荐组合：**表清单用方式 A，`get_table_schema` 用方式 B**。

**已定决策**：
1. **新鲜度策略：完全信任 OpenMetadata** —— 表/列结构、类型、描述都以 OpenMetadata 为
   权威来源，`get_table_schema` 不再回退 Kyuubi `DESCRIBE`（Kyuubi 只负责数据查询）。
   前提：OpenMetadata 是该 schema 的元数据源头，schema 变更会在 OpenMetadata 同步。
2. **缓存 TTL：30 分钟** —— 表清单（conv_id 维度）与术语（进程级）都带 TTL，
   OpenMetadata 更新后最长 30 分钟自动重拉，无需重启/开新会话（`_OM_CACHE_TTL`，
   可配 `openmetadata_cache_ttl_seconds`）。
3. **描述全量不截断** —— 表/术语描述默认全量（`description_max_chars=0`），
   保留【业务定义】【粒度】【指标】【核心维度】【核心字段】全段落；
   需要时可配 `openmetadata_description_max_chars` 截断（按句号断句，不切词）。

**待确认 → 已解决（实施验证）**：
1. **MCP 工具名/入参**：该 OpenMetadata MCP 暴露 16 个工具（`list_tools()` 确认），
   **无干净的 list-tables 工具**（只有 `search_metadata` 需 query、`get_entity_details` 需 FQN、
   `semantic_search`）。`get_table_schema` 用 **`get_entity_details`**
   （`entityType=table` + `fqn={schema}.{table}`，模板可配）。自动发现已排除写/测试/治理类工具，
   避免误匹配（曾误匹配 `get_test_definitions`）。
2. **REST API**：**开放且可用**（`GET /api/v1/glossaries`、`/glossaryTerms`、`/databaseSchemas`、
   `/tables?databaseSchema=<fqn>`），鉴权用同一 JWT。**方式 A 已落地**：
   `list_tables_rest()` 定位 schema FQN（`p_trino_iceberg.iceberg.st_embed`）→ 拉 30 表全量描述。
3. **自动发现 connector**：从 `connector_instance` 表自动发现 `openmetadata` connector
   （server_uri/transport/auth_type），**直接解密凭证**（绕过 connector 重水合 bug，
   `run_until_complete` 在 uvicorn 循环抛 "this event loop is already running"）。

**新增：业务术语与口径注入** —— 从「商规EMBED生产测试术语库」按白名单拉 13 个术语
（数仓分层/字段命名/Entity/Grain/Subject/Period/test_result/汇总指标/ETL字段/测项命名/
GUID生成规则/测试JSON结构/指标），压缩后注入 system prompt（`_GLOSSARY_CACHE` + TTL）。

### 6.6 落地改动点汇总（✅ 均已实施并验证）

| 改动点 | 位置 | 状态 |
|--------|------|------|
| 紧凑表清单注入 `{database_context}`（OpenMetadata REST 方式 A，TTL 缓存） | `agentic_data_api.py`：`_build_compact_catalog`、`list_tables_rest` | ✅ |
| 业务术语与口径注入（13 术语，白名单，TTL 缓存） | `agentic_data_api.py`：`_build_glossary_section`、`OpenMetadataClient.list_glossary_terms` | ✅ |
| `get_table_schema` 工具（OpenMetadata `get_entity_details`，Kyuubi 兜底） | `agentic_data_api.py` `@tool` 区（`sql_query` 旁） | ✅ |
| 自动发现 OpenMetadata connector + 直接解密 token | `agentic_data_api.py`：`_load_openmetadata_config` | ✅ |
| 删除 user message 拼接 schema | `agentic_data_api.py` `received` 构造 | ✅ |
| 移除 chromadb db_summary top-20 注入 | `agentic_data_api.py` `if database_name:` 块 | ✅ |
| 缓存 TTL（表清单 + 术语，默认 30 分钟） | `agentic_data_api.py`：`_OM_CACHE_TTL`、`_is_cache_fresh` | ✅ |
| 新增 `OpenMetadataClient`（REST/MCP 双通道） | `packages/dbgpt-core/src/dbgpt/agent/util/openmetadata_client.py` | ✅ |
| 改动点 4（task_progress 渲染）配套 | 见 5.5 | ✅ |

> 验证：`tests/custom_agent_test/context_governance_verify.py`（36 PASS）+ 端到端
> `/v1/chat/react-agent`（30 表全量清单 + 13 术语注入 + 业务问题如"本周各项目 FBB 坏块比率"正确回答）。

---

## 7. 验证方式

1. 复现：同一 conv_id 下先发一条消息（产生 ≥2 个 ReAct step），再发第二条
2. 抓取第二轮请求中 `_load_thinking_messages` 组装后的 `agent_messages`（可临时加日志
   或在 `base_agent.py:1969` 打印），确认：
   - `historical_dialogues`（消息 #2）**包含上一轮全部内容（含 AI 回复，不再只省问题）**，
     且角色标记正确（不再把用户问题误标成 AI）
   - `memory_list`（消息 #3）只包含**本轮** step，不再出现上一轮 "Question: ..." / "Observation: ..."
3. 确认 token 消耗下降、无重复段落
4. 回归：新会话首轮、单步简单问题、失败重试轮，均不应出现重复
5. **记忆回归**：连续多轮对话，模型应能引用上一轮自己的回答（验证断点 1/2 已修复）

---

## 8. 真实业务场景测试报告（20 个商规EMBED问题）

> 日期 2026-08-04。用 `/v1/chat/react-agent` 实测 + 结构化分析，**先记录问题、不急着改**。

### 8.1 实测结论

| 验证项 | 结果 |
|--------|------|
| 简单查询（"st_embed 有哪些表"） | ✅ 秒级完成，清单+术语正确 |
| 指标查询（"本周各项目 FBB 坏块比率"） | ✅ 正确映射 `{flash_pn}_fbb_ratio_sn` → `dws_indicator_w`，返回中位数+分级 |
| 多轮记忆 | ✅ 记住上一轮内容（view 修复生效） |
| 复杂业务问题（MES 历史良率/测项清单） | ⚠️ **能完成但耗时数分钟**（agent 大量 sql_query 探索，最终生成 HTML 报告）；SSE 客户端需支持长连接 |

### 8.2 20 场景逐条分析

| # | 场景 | 所需数据源 | 当前支持 | 问题 |
|---|------|-----------|---------|------|
| 1 | MES 历史良率（笔数/水平/拐点/errorcode） | `ods_mes_production_report`(work_amount/pass_amount) + `dim_base_project` | 表在清单 | agent 探索 11+ 次 sql_query 才定位，慢 |
| 2 | 宽表测项 item/subitem | **`masterdata_db.dim_test_item`** | ✗ 跨 schema 不在清单 | agent 不知道表结构 |
| 3 | UFS 功耗/温度汇总（阈值/分布） | `dwd_power_current_di` / `dwd_power_temperature_di` | 表在清单 | 试产段口径需业务知识 |
| 4 | UFS GBB 位置/类型/数量 | `dwd_fa_bb_block` / `dws_fa_bb_block` | 表在清单 | 基本可查 |
| 5 | UFS UID→订单→温度/功耗 | `dim_base_sn_di`(efuse_id) | 表在清单 | 需 JOIN 链 |
| 6 | ECC by plane（GBB/FBB/最大/集中性） | `dwd_fa_ecc_plane_di` / `dws_fa_ecc_plane` | 表在清单 | 业务口径（坏块定义）需术语 |
| 7 | FWError/VPError 含义 | **`embed_db.dim_errorcode_information`** | ✗ 跨 schema 不在清单 | agent 看不到 errorcode 字典 |
| 8 | 电流 500-550 比例 | `dwd_power_current_di` | 表在清单 | 可查 |
| 9 | Burin 时长 | `dwd_dut_result_w`(BurnIn subitem) | 表在清单 | 需业务口径（91-0D 等） |
| 10 | 71code 失效 DPPM | `ods_mes_production_report` + **errorcode 字典** | ✗ 部分 | 跨 schema |
| 11 | 软件包 per 站位 | `dwd_dut_result_w`(software_information) | 表在清单 | 可查 |
| 12 | 返测单/返测后良率/新失效 | `dim_base_wo_di`(wo_status) + 返测逻辑 | 表在清单 | **业务逻辑**不在任何地方 |
| 13 | 坏块分布/减 24 块良率损失 | `dws_fa_bb_block` | 表在清单 | 需业务推导 |
| 14 | 新表去哪个表找 | 紧凑表清单 | ✅ | 清单直接给 |
| 15 | MES 与 log 比对缺失 lot | `ods_mes_production_report` vs `ods_dut_result` | 表在清单 | 复杂关联，探索慢 |
| 16 | 测试进展（站位） | `dwd_dut_result`(station) | 表在清单 | 可查 |
| 17 | nandTj 温度对比/vdt/burnin | `dwd_power_temperature_di` | 表在清单 | 业务口径 |
| 18 | 批次良率波动 | `dws_indicator_w` | 表在清单 | 可查 |
| 19 | 版本 log 差异 | `dwd_dut_result_w`(software_information) | 表在清单 | 可查 |
| 20 | 表关联/上下游依赖 | OpenMetadata lineage | ✗ 无工具 | 需 `get_entity_lineage` 类工具 |

### 8.3 问题归纳

1. **跨 schema 表缺失**：`embed_db.dim_indicator`、`masterdata_db.dim_test_item`、
   `embed_db.dim_errorcode_information` 等业务字典表不在清单里（清单只覆盖 st_embed），
   agent 只能靠 info_schema 探索 → 慢且不可靠。
2. **业务逻辑/口径缺失**：返测单、Burin 时长、DPPM、坏块定义等业务规则不在系统提示词/术语库，
   agent 靠猜或做 HTML 推导。
3. **探索低效**：复杂问题 agent 大量 `sql_query` 反复试探（场景 1 达 11 次），
   耗时长；应引导"先 `get_table_schema`/查字典表，再查数据"。
4. **血缘能力缺失**：场景 20（表上下游）无对应工具。

### 8.4 方案建议（按优先级）

1. **扩充清单到相关字典 schema**：把 `embed_db.dim_indicator`、`masterdata_db.dim_test_item`、
   `embed_db.dim_errorcode_information` 等"业务字典表"纳入紧凑清单（schema 稳定、常驻）；
   `get_table_schema` 天然支持跨 schema 取结构。
2. **业务查询模式知识库**：针对 20 个高频场景建"问题→表→SQL 模板"KB（可做知识库文档，
   `knowledge_retrieve` 已有），agent 命中模板直接套用。
3. **术语库扩充**：把 ErrorCode 分类、测项枚举、指标来源表加进「商规EMBED生产测试术语库」。
4. **血缘工具**：新增 `get_table_lineage` 工具（OpenMetadata `get_entity_lineage`）。
5. **探索引导**：workflow_prompt 加规则——复杂问题先 `get_table_schema`/查字典表，避免盲目 sql_query。

---

## 9. 相关代码位置索引

| 位置 | 作用 |
|------|------|
| `agentic_data_api.py:4244` | build()（恢复历史到 ShortTermMemory）→ **改动点 1 在此处加 clear()** |
| `agentic_data_api.py:4284-4322` | historical_dialogues 加载与注入 → **改动点 3（改法 A）在此改 view 跳过逻辑** |
| `agentic_data_api.py:3505 / 4877` | 当前 user_input 落库时机；AI 回复以 view 保存（断点 1 来源） |
| `base_agent.py:1838-2034` | `_load_thinking_messages`：消息 #1~#4 组装 |
| `base_agent.py:1987-2007` | 消息 #2 historical_dialogues + 消息 #3 memory_list 注入 |
| `base_agent.py:359-372` | build() 恢复点：gpts_messages → ShortTermMemory |
| `base_agent.py:1415 / 1482` | gpts_messages 唯一写入点 `_a_append_message`（仅 receive 触发，断点 2 来源） |
| `react_agent.py:274-363` | `ReActAgent.read_memories`：解析 fragment 为 AgentMessage |
| `role.py:276-392` | `write_memories`：每轮写一个 fragment |
| `role.py:334-335` | 仅首轮注入 question 字段 |
| `role.py:458-470` | `recovering_memory`：恢复历史到 ShortTermMemory |
| `memory/agent_memory.py:283-402` | AgentMemory：默认 ShortTermMemory(buffer_size=5) |
| `memory/base.py:770-778` | ShortTermMemory.read：直接返回 `_fragments` |
| `memory/gpts/gpts_memory.py:152-179` | get_agent_history_memory：读取历史 action_output（断点 2 过滤点） |
| `core/interface/message.py:1466` | `_append_view_messages`：只为缺 view 的 ai 补 view，不反向转换 |
| `role.py:62 / 210-238 / 345-374` | `_task_progress` 累积与 `task_progress_summary` 渲染（改动点 4 的对象） |
| `agentic_data_api.py:3832-4241` | `workflow_prompt` 构造（改动点 4 改法 A 在此加 `{{{{ task_progress }}}}`） |
| `dbgpt_app/base.py:33` | 启动后台线程 `init_db_summary`（DB 元数据向量化入口） |
| `db_summary_client.py:69 / 133 / 166` | `db_summary_embedding`（写入）、`get_db_summary`（检索）、`init_db_profile`（组装） |
| `db_summary_client.py:312-324` | `<dbname>_profile` / `<dbname>_profile_field` 两个 collection |
| `retriever/db_schema.py:190-234` | `_retrieve_field` 全量返回字段、`_similarity_search` top-k 检索 |
| `agentic_data_api.py:1644-1695` | 每问检索 top-20 注入（第 6 节改造点：会话缓存 + 紧凑清单） |
| `agentic_data_api.py:2330-2436` | `sql_query` 工具（`get_table_schema` 新工具应加在旁） |
| `agentic_data_api.py:4253-4254` | schema 拼进 user message（第 6.4 节删除目标） |
| `conn_kyuubi.py:540-595` | Trino 表注释（`system.metadata.table_comments` / `SHOW CREATE TABLE`） |
| `conn_kyuubi.py:608-638` | `table_simple_info`：实时查 information_schema 列名（廉价替代/兜底） |
| `agentic_data_api.py:291-360` | connector 解析与 `_select_connector_tools`：MCP connector 工具扁平化注入 agent |
| `agentic_data_api.py:4142-4220` | MCP connector 工具描述注入 system prompt（`_connector_prompt`） |
| `agent/resource/connector/catalog.py` | connector 目录（catalog.json 模板；OpenMetadata 为用户自定义实例） |
| `dbgpt-serve/agent/resource/mcp.py` | MCP SSE ToolPack（OpenMetadata 以 MCP server 接入） |
