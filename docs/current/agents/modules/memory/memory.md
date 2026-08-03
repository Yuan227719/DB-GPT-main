# 记忆介绍

> 记忆模块在 Agent 架构设计中扮演着非常重要的角色。它存储从环境中感知到的信息，并利用记录的记忆来促进未来的动作。记忆模块可以帮助 Agent 积累经验、自我进化，并以更加一致、合理和有效的方式行事。

## 记忆模块概述

### 记忆操作

在 DB-GPT Agent 中，有三种主要的记忆操作：

1. **记忆读取**：记忆读取的目的是从记忆中提取有意义的信息，以增强 Agent 的动作。
2. **记忆写入**：记忆写入的目的是将感知到的环境信息存储到记忆中。将有价值的信息存储在记忆中，为将来检索有信息的记忆奠定了基础，使 Agent 能够更高效、更理性地行动。
3. **记忆反思**：记忆反思模拟人类观察和评估自身认知、情感和行为过程的能力。当应用于 Agent 时，其目标是使 Agent 具备独立总结和推断更抽象、更复杂和更高级别信息的能力。

### 记忆结构

在 DB-GPT Agent 中，有四种主要的记忆结构：
1. **感觉记忆**：类似于人类的感觉记忆，感觉记忆注册感知输入，接收来自环境的观察结果，部分感觉记忆将被转移到短期记忆。
2. **短期记忆**：短期记忆临时缓冲最近的感知信息，它接收部分感觉记忆，并可通过其他观察结果或检索到的记忆得到增强，从而进入长期记忆。
3. **长期记忆**：长期记忆存储 Agent 的经验和知识，它接收来自短期记忆的信息，并随时间推移巩固重要信息。
4. **混合记忆**：混合记忆是感觉记忆、短期记忆和长期记忆的组合。

## DB-GPT Agent 中的记忆

### 记忆的相关概念

- `Memory`：记忆是一个类，存储所有记忆内容，目前可以是 `SensorMemory`、`ShortTermMemory`、`EnhancedShortTermMemory`、`LongTermMemory` 和 `HybridMemory`。
- `MemoryFragment`：`MemoryFragment` 是一个抽象类，用于存储记忆信息。`AgentMemoryFragment` 是一个继承自 `MemoryFragment` 的类，包含记忆内容、记忆 ID、记忆重要性、最后访问时间等。
- `GptsMemory`：`GptsMemory` 用于存储对话和规划信息，不属于记忆结构的一部分。
- `AgentMemory`：`AgentMemory` 是一个包含 `Memory` 和 `GptsMemory` 的类。

### 创建记忆

如前所述，记忆包含在 `AgentMemory` 类中，以下是一个示例：
```python
from dbgpt.agent import AgentMemory, ShortTermMemory

# 创建一个 Agent 记忆，默认记忆为 ShortTermMemory
memory = ShortTermMemory(buffer_size=5)
agent_memory = AgentMemory(memory=memory)
```

另外，在 `AgentMemory` 类中，你可以传入 `GptsMemory`。按常规理解，`GptsMemory` 不属于记忆结构的一部分，它用于存储对话和规划信息。

`GptsMemory` 的示例：
```python
from dbgpt.agent import AgentMemory, ShortTermMemory, GptsMemory

# 创建一个 Agent 记忆，默认记忆为 ShortTermMemory
memory = ShortTermMemory(buffer_size=5)
# 存储对话和规划信息
gpts_memory = GptsMemory()
agent_memory = AgentMemory(memory=memory, gpts_memory=gpts_memory)
```

### 在 Agent 中读写记忆

Agent 会调用 `read_memories` 方法从记忆中读取记忆片段，并调用 `write_memories` 方法将记忆片段写入记忆。

当 Agent 调用 LLM 时，记忆将被写入 LLM 提示词中；当 LLM 返回响应后，Agent 会将查询和响应写入记忆。

正如我们在 [配置到提示词](../profile/profile_to_prompt) 中提到的，提示词模板中有一个名为 `most_recent_memories` 的模板变量，它将被最近的记忆替换。

#### 读取记忆以构建提示词

以下是一个从记忆中读取记忆并构建提示词的示例：
```python
import os
import asyncio
from dbgpt.agent import (
    AgentContext,
    ShortTermMemory,
    AgentMemory,
    ConversableAgent,
    ProfileConfig,
    LLMConfig,
    BlankAction,
    UserProxyAgent,
)
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient(
    model_alias="gpt-4o",
    api_base=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

context: AgentContext = AgentContext(
    conv_id="test123",
    language="en",
    temperature=0.9,
    max_new_tokens=2048,
    verbose=True,  # 添加 verbose=True 以打印对话历史
)

# 创建一个 Agent 记忆，包含一个短期记忆
memory = ShortTermMemory(buffer_size=2)
agent_memory: AgentMemory = AgentMemory(memory=memory)

# 自定义用户提示词模板，包含最近的记忆和问题
user_prompt_template = """\
{% if most_recent_memories %}\
Most recent observations:
{{ most_recent_memories }}
{% endif %}\

{% if question %}\
Question: {{ question }}
{% endif %}
"""

# 自定义写入记忆模板，包含问题和思考
write_memory_template = """\
{% if question %}user: {{ question }} {% endif %}
{% if thought %}assistant: {{ thought }} {% endif %}\
"""


async def main():
    # 创建一个带有自定义用户提示词模板的配置
    joy_profile = ProfileConfig(
        name="Joy",
        role="Comedians",
        user_prompt_template=user_prompt_template,
        write_memory_template=write_memory_template,
    )
    joy = (
        await ConversableAgent(profile=joy_profile)
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(BlankAction)
        .build()
    )
    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()
    await user_proxy.initiate_chat(
        recipient=joy,
        reviewer=user_proxy,
        message="My name is bob, please tell me a joke",
    )
    await user_proxy.initiate_chat(
        recipient=joy,
        reviewer=user_proxy,
        message="What's my name?",
    )


if __name__ == "__main__":
    asyncio.run(main())
```
在上面的示例中，我们在 `AgentContext` 中设置了 `verbose=True`，以打印对话历史。

输出将如下所示：

``````shell
--------------------------------------------------------------------------------
User (to Joy)-[]:

"My name is bob, please tell me a joke"

--------------------------------------------------------------------------------
un_stream ai response: Sure thing, Bob! Here's one for you:

Why don't scientists trust atoms?

Because they make up everything!

--------------------------------------------------------------------------------
String Prompt[verbose]: 
system: You are a Comedians, named Joy, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.



human: 
Question: My name is bob, please tell me a joke

LLM Output[verbose]: 
Sure thing, Bob! Here's one for you:

Why don't scientists trust atoms?

Because they make up everything!
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Sure thing, Bob! Here's one for you:\n\nWhy don't scientists trust atoms?\n\nBecause they make up everything!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Sure thing, Bob! Here's one for you:

Why don't scientists trust atoms?

Because they make up everything!

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
User (to Joy)-[]:

"What's my name?"

--------------------------------------------------------------------------------
un_stream ai response: Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!

--------------------------------------------------------------------------------
String Prompt[verbose]: 
system: You are a Comedians, named Joy, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.



human: Most recent observations:
user: My name is bob, please tell me a joke 
assistant: Sure thing, Bob! Here's one for you:

Why don't scientists trust atoms?

Because they make up everything! 

Question: What's my name?

LLM Output[verbose]: 
Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
Joy (to User)-[gpt-4o]:

"Your name is Bob! \n\nAnd here's another quick joke for you:\n\nWhy don't skeletons fight each other?\n\nThey don't have the guts!"
>>>>>>>>Joy Review info: 
Pass(None)
>>>>>>>>Joy Action report: 
execution succeeded,
Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!

--------------------------------------------------------------------------------
``````

在第二次对话中，你可以在用户提示词中看到 `Most recent observations`：
``````
--------------------------------------------------------------------------------
String Prompt[verbose]: 
system: You are a Comedians, named Joy, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.



human: Most recent observations:
user: My name is bob, please tell me a joke 
assistant: Sure thing, Bob! Here's one for you:

Why don't scientists trust atoms?

Because they make up everything! 

Question: What's my name?

LLM Output[verbose]: 
Your name is Bob! 

And here's another quick joke for you:

Why don't skeletons fight each other?

They don't have the guts!
--------------------------------------------------------------------------------
``````

#### 写入记忆

当 Agent 收到 LLM 的响应后，它会将查询和响应写入记忆。在记忆片段中，`content` 是字符串类型，因此你应该决定如何将信息存储在 content 中。

在上述示例中，`write_memory_template` 为：
```python
write_memory_template = """\
{% if question %}user: {{ question }} {% endif %}
{% if thought %}assistant: {{ thought }} {% endif %}\
"""
```
`question` 是用户查询，`thought` 是 LLM 响应，我们将在下一节中进一步介绍。

## 自定义记忆读写

我们可以通过继承 `ConversableAgent` 类并重写 `read_memories` 和 `write_memories` 方法来自定义记忆的读写。

```python
from typing import Optional
from dbgpt.agent import (
    ConversableAgent,
    AgentMemoryFragment,
    ProfileConfig,
    BlankAction,
    ActionOutput,
)

write_memory_template = """\
{% if question %}user: {{ question }} {% endif %}
{% if thought %}assistant: {{ thought }} {% endif %}\
"""


class JoyAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name="Joy",
        role="Comedians",
        write_memory_template=write_memory_template,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([BlankAction])

    async def read_memories(
        self,
        question: str,
    ) -> str:
        """从记忆中读取记忆。"""
        memories = await self.memory.read(observation=question)
        recent_messages = [m.raw_observation for m in memories]
        # 合并最近的消息。
        return "".join(recent_messages)

    async def write_memories(
        self,
        question: str,
        ai_message: str,
        action_output: Optional[ActionOutput] = None,
        check_pass: bool = True,
        check_fail_reason: Optional[str] = None,
    ) -> None:
        """将记忆写入记忆存储。

        建议你根据需求重写此方法，以将对话保存到记忆中。

        Args:
            question(str): 接收到的用户问题。
            ai_message(str): AI 消息，LLM 输出。
            action_output(ActionOutput): 动作输出。
            check_pass(bool): 检查是否通过。
            check_fail_reason(str): 检查失败的原因。
        """
        if not action_output:
            raise ValueError("需要动作输出才能保存到记忆。")

        mem_thoughts = action_output.thoughts or ai_message
        memory_map = {
            "question": question,
            "thought": mem_thoughts,
        }
        # 这是写入记忆的模板。
        # 它在 Agent 的配置中进行配置。
        write_memory_template = self.write_memory_template
        memory_content: str = self._render_template(write_memory_template, **memory_map)
        fragment = AgentMemoryFragment(memory_content)
        await self.memory.write(fragment)
```

在上面的示例中，我们重写了 `read_memories` 以从记忆中读取记忆，在 DB-GPT 中，最近的记忆将构成提示词模板中的 `most_recent_memories`。同时重写了 `write_memories` 以将记忆写入记忆存储。

**因此，你可以根据需求自定义记忆的读写。**

## 总结

在本文档中，我们介绍了 DB-GPT Agent 中的记忆模块，以及如何在 Agent 中使用记忆。在接下来的章节中，我们将介绍如何在 DB-GPT Agent 中使用每种记忆结构。
