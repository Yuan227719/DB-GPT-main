---
title: 上下文管理
---

# Agent 上下文管理

Agent 上下文管理可在模型上下文窗口内维持长时间运行的 ReAct 对话，同时不丢失任务的运行状态。它在每次模型调用前追踪 Token 使用量，发出实时的上下文状态事件，并在对话过大时逐步应用更强力的压缩策略。

## 概述

```text
用户任务
   |
   v
Agent 构建消息
系统提示词 + 任务进度 + 记忆 + 最近的 ReAct 轮次
   |
   v
统计 Token 数量
ProxyTokenizerWrapper.count_token(model_name)
回退方案: len(content) // 4
   |
   v
计算预算
effective_budget = max_context_tokens - reserved_tokens
usage_ratio = used_tokens / effective_budget
   |
   v
状态分类
normal < warning < error < critical < overflow
   |
   +-- normal --------------------------------------+
   |                                                |
   v                                                |
发送消息给 LLM                                      |
   |                                                |
warning 及以上状态                                  |
   |                                                |
   v                                                |
第 1 层: 观测结果微压缩                              |
截断旧的工具观测结果                                  |
   |                                                |
   v                                                |
重新统计并发送 context.status 事件                   |
   |                                                |
   +-- 低于 warning --------------------------------+
   |                                                |
   v                                                |
第 2 层: 会话记忆压缩                                |
丢弃旧的 ReAct 轮次，保留最近的轮次                    |
   |                                                |
   v                                                |
重新统计并发送 context.status 事件                   |
   |                                                |
   +-- 低于 error ----------------------------------+
   |                                                |
   v                                                |
第 3 层: 全上下文压缩                                |
使用 LLM 总结旧的轮次                                |
   |                                                |
   v                                                |
重新统计并发送 context.status 事件                   |
   |                                                |
   +----------------------------------------------->+

如果 LLM 仍然返回上下文溢出错误：

LLM context_too_long / maximum context length 错误
   |
   v
第 4 层: 响应式压缩
保留系统提示词 + 最后 2 个 ReAct 轮次
   |
   v
使用压缩后的消息重试模型调用一次
```

工具结果通过独立的快照路径进行保存：

```text
动作执行成功
   |
   v
写入完整操作快照
step, action, action_input, observation, thought, timestamp
   |
   v
在记忆片段上存储快照路径
并在任务进度元数据中记录
   |
   v
为后续提示词重建记忆
Observation: 简短或压缩后的观测结果
[完整详情请查看: /path/to/snapshot.json]
   |
   v
第 1 层 / 第 2 层可缩减提示词文本
而无需删除原始的工具结果文件
```

## Token 预算

上下文管理器在模型调用前统计当前 `AgentMessage` 列表中的 Token 数量。统计使用 `ProxyTokenizerWrapper` 和当前激活的 `model_name`。如果分词器无法统计内容，DB-GPT 会回退到使用每 Token 约四个字符的粗略估算。

可用的上下文窗口为：

```text
effective_budget = max_context_tokens - reserved_tokens
```

`reserved_tokens` 为模型响应预留空间，确保提示词不会填满整个模型窗口。

## 状态与阈值

| 状态 | 默认触发条件 | 说明 |
| --- | --- | --- |
| `normal` | `< 70%` | 不进行压缩。 |
| `warning` | `>= 70%` | 开始轻量级压缩。 |
| `error` | `>= 90%` | 必要时使用基于 LLM 的摘要压缩。 |
| `critical` | `>= 95%` | 与 error 相同，但以更紧急的状态上报。 |
| `overflow` | `>= 100%` | 提示词已超出有效预算。 |

每次统计和每层压缩后，后端会发出一个 `context.status` 事件，包含以下内容：

```json
{
  "type": "context.status",
  "used": 19000,
  "budget": 115904,
  "ratio": 0.164,
  "state": "normal",
  "compact_layer": null
}
```

UI 会将此渲染为紧凑的上下文窗口指示器。

## 压缩层级

### 第 1 层: 观测结果微压缩

第 1 层是最轻量的压缩。它仅缩短来自工具调用的旧 `Observation:` 消息。最近的轮次保持完整。

规则：

- 当使用量达到 `warning_threshold` 时触发。
- 当轮次早于 `max_observation_age_rounds` 时被视为旧轮次。
- 旧的观测结果被截断至 `truncated_observation_max_chars` 字符。
- 如果观测结果有快照路径，压缩后的消息会保留指向完整详情的指针。

这一层是廉价且确定性的，不会调用 LLM。

### 第 2 层: 会话记忆压缩

第 2 层从提示词中移除旧的完整 ReAct 轮次。它依赖于已注入系统提示词中的任务进度摘要，因此 Agent 仍然知道已完成的任务。

规则：

- 当第 1 层压缩后提示词仍处于或高于 `warning_threshold` 时触发。
- 始终保留至少 `min_keep_recent_rounds` 个轮次。
- 同时保留足够的最新内容以满足 `min_keep_tokens` 的要求。
- 丢弃完整的旧轮次，而非任意单条消息。

这一层同样是确定性的，不会调用 LLM。

### 第 3 层: 全上下文压缩

第 3 层使用 LLM 将旧的对话轮次总结为结构化的上下文摘要，然后保留该摘要和最近的轮次。

规则：

- 当使用量达到或高于 `error_threshold` 时触发。
- 保持最后 `min_keep_recent_rounds` 个轮次不变。
- 将更旧的消息总结为一条合成的摘要消息。
- 摘要提示词要求模型保留精确的任务状态、路径、值、变量名、错误和后续步骤。
- 如果摘要多次失败，断路器会在 `max_compact_failures` 次后停止重试。

这一层成本较高，但相比直接丢弃旧消息能保留更多的语义连续性。

### 第 4 层: 响应式压缩

第 4 层是应急路径。它不由正常的预算状态机触发，而是在模型调用因上下文溢出错误（如 `context_too_long`、`context_length_exceeded` 或 `maximum context length`）失败时触发。

规则：

- 保留系统消息。
- 仅保留最近两个 ReAct 轮次。
- 依赖系统提示词中的任务进度摘要来维持任务连续性。
- 使用压缩后的消息重试模型调用一次。

这一层故意采用激进的策略，因为它仅在模型已经拒绝提示词后使用。

## 工具结果快照

工具观测结果可能很大：SQL 结果表、生成的代码输出、解释器日志、文件路径、报告元数据和中间计算值可能会迅速占据提示词空间。DB-GPT 通过将完整操作详情与必须留在模型上下文中的文本分离来保持提示词的紧凑。

当动作执行成功时，Agent 会为完整操作写入一个 JSON 快照。快照包括：

- `step`
- `action`
- `phase`
- `action_intention`
- `action_reason`
- `thought`
- `action_input`
- `observation`
- `timestamp`
- `conv_id`

默认情况下，快照写入以下目录：

```text
$DBGPT_HOME/workspace/op_snapshots/<conv_id>/
```

如果设置了 `AgentContext.output_dir`，DB-GPT 则使用该目录。

每个快照文件按步骤和动作命名：

```text
step_003_sql_query.json
step_006_code_interpreter.json
```

快照路径附加到内存中的 `AgentMemoryFragment`，同时记录在任务进度元数据中。当 Agent 后续将记忆重建为提示词消息时，会追加一个轻量级的引用：

```text
Observation: <观测文本>
[完整详情请查看: /path/to/step_003_sql_query.json]
```

这在压缩过程中很重要：

- 第 1 层可能截断旧的 `Observation:` 文本，但如果存在快照引用则会保留。
- 第 2 层可能从提示词中移除旧的 ReAct 轮次，但任务进度仍会记录快照文件名作为引用。
- 第 3 层总结旧消息，而原始工具结果保留在磁盘上以便精确恢复。

换句话说，压缩减少了提示词的负载；它不一定是工具输出的唯一保存位置。

## 配置

Agent 上下文管理可在应用程序 TOML 文件中配置：

```toml
[service.web.agent_context]
# 非正值回退到默认的上下文预算。
max_context_tokens = 120000
reserved_tokens = 4096
warning_threshold = 0.70
error_threshold = 0.90
critical_threshold = 0.95
min_keep_recent_rounds = 3
max_observation_age_rounds = 5
truncated_observation_max_chars = 200
min_keep_tokens = 10000
max_compact_failures = 3
```

为了保持行为稳定，在每个 LLM 部署上设置 `context_length`，以便模型元数据反映实际的提供商窗口：

```toml
[[models.llms]]
name = "Qwen/Qwen2.5-Coder-32B-Instruct"
provider = "proxy/siliconflow"
api_key = "${env:SILICONFLOW_API_KEY}"
context_length = 32768
```

通过此配置，切换模型也会切换有效的上下文预算。

## 设计说明

- 第 1 层和第 2 层是确定性的且成本低廉，优先于任何 LLM 摘要。
- 第 3 层仅在上下文接近失败时才使用 LLM。
- 第 4 层是应对模型侧上下文溢出错误的最后手段重试路径。
- 前端独立于普通聊天文本接收 `context.status` 事件，因此 UI 指示器可以更新而不会污染对话。
- 压缩是渐进式的：每层压缩后，DB-GPT 会重新统计 Token 数量，如果提示词恢复到安全状态则不再继续升级。
