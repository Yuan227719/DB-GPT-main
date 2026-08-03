# 档案模块

> 智能体通常通过扮演特定角色来执行任务，例如程序员、教师和领域专家。
> 档案模块旨在指明智能体角色的档案信息，这些信息通常
> 被写入提示词中以影响 LLM 的行为。智能体档案通常包含
> 基本信息（如年龄、性别和职业）、心理信息
> （反映智能体的个性）以及社会信息（详细描述智能体之间的关系）。
>
> 用于描述智能体档案的信息选择在很大程度上取决于具体的应用场景。
> 例如，如果应用旨在研究人类的认知过程，那么心理信息就变得至关重要。

## DB-GPT 智能体中的档案

档案对于 DB-GPT 中的智能体至关重要，它们用于影响智能体的行为。

在[编写自定义智能体](../../introduction/custom_agents.md)部分，您已经看到了一个基本的档案示例。

```python
from dbgpt.agent import ConversableAgent, ProfileConfig

class MySummarizerAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        # 智能体的名称
        name="Aristotle",
        # 智能体的角色
        role="Summarizer",
        # 智能体的核心功能目标，告诉 LLM 它能做什么
        goal=(
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories."
        ),
        # 智能体的介绍和描述，用于任务分配和展示。
        # 如果为空，将使用 goal 的内容。
        desc=(
            "You can summarize provided text content according to user's questions"
            " and output the summarization."
        ),
    )
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

在上面的示例中，`ProfileConfig` 类用于定义智能体的档案。
这是一种定义智能体档案的简单方式，您只需提供智能体的名称、角色、目标和描述。

让我们看看从档案生成的最终提示词。
首先，我们单独创建一个档案配置。

```python
from dbgpt.agent import ProfileConfig

profile: ProfileConfig = ProfileConfig(
    # 智能体的名称
    name="Aristotle",
    # 智能体的角色
    role="Summarizer",
    # 智能体的核心功能目标，告诉 LLM 它能做什么
    goal=(
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ),
    # 智能体的介绍和描述，用于任务分配和展示。
    # 如果为空，将使用 goal 的内容。
    desc=(
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    ),
)

# 从配置创建档案
real_profile = profile.create_profile()
system_prompt = real_profile.format_system_prompt(question="What can you do?")
user_prompt = real_profile.format_user_prompt(question="What can you do?")

print(f"System Prompt: \n{system_prompt}")
print("#" * 50)
print(f"User Prompt: \n{user_prompt}")
```

运行上述代码将生成以下提示词：

```
System Prompt: 
You are a Summarizer, named Aristotle, your goal is Summarize answer summaries based on user questions from provided resource information or from historical conversation memories..
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.



##################################################
User Prompt: 

Question: What can you do?
```

如您所见，档案用于生成系统提示词和用户提示词，它们将传递给 LLM 以生成响应。

因此，您可以轻松地看到从档案生成的真实提示词，这对于调试和理解智能体的行为非常有用，我们不会对您隐藏太多细节。

## 下一步是什么？
- 有多少种方式可以为智能体创建档案？[了解更多](./profile_creation.md)
- 档案如何转换为 LLM 提示词？[了解更多](./profile_to_prompt.md)
