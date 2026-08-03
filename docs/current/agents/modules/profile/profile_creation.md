# 创建档案

在本节中，您将了解更多关于为智能体创建档案的知识。

## 方法一：使用 ProfileConfig 类

如[档案](profile.md)部分所述，`ProfileConfig` 类用于定义智能体的档案。这是一种定义智能体档案的简单方式。

正式来说，`ProfileConfig` 类支持以下参数：
- `name`：智能体的名称。
- `role`：智能体的角色。
- `goal`：智能体的核心功能目标，告诉 LLM 它能做什么。
- `desc`：智能体的介绍和描述，用于任务分配和展示。如果为空，将使用 goal 的内容。
- `constraints`：可以包含多个约束条件和推理限制逻辑。
- `expand_prompt`：要添加到提示词中的扩展内容，您可以传入一些自定义文本。
- `examples`：提示词中的一些示例。

这是一个使用 `ProfileConfig` 类创建档案的完整示例：

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
    # 智能体的约束条件
    constraints=[
        "Prioritize the summary of answers to user questions from the improved "
        "resource text. If no relevant information is found, summarize it from "
        "the historical dialogue memory given. It is forbidden to make up your "
        "own.",
        "You need to first detect user's question that you need to answer with "
        "your summarization.",
        "Extract the provided text content used for summarization.",
        "Then you need to summarize the extracted text content.",
        "Output the content of summarization ONLY related to user's question. "
        "The output language must be the same to user's question language.",
        "If you think the provided text content is not related to user "
        "questions at all, ONLY output 'Did not find the information you "
        "want.'!!.",
    ],
    # 智能体的介绍和描述，用于任务分配和展示。
    # 如果为空，将使用 goal 的内容。
    desc=(
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    ),
    expand_prompt="Keep your answer concise",
    # 提示词中的一些示例
    examples=""
)
```
在上面的示例中，我们可以看到 'constraints' 和 'expand_prompt' 被添加到档案中。

让我们看看从档案生成的最终提示词。

```python
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
Keep your answer concise 

*** IMPORTANT REMINDER ***
Please answer in English.

1. Prioritize the summary of answers to user questions from the improved resource text. If no relevant information is found, summarize it from the historical dialogue memory given. It is forbidden to make up your own.
2. You need to first detect user's question that you need to answer with your summarization.
3. Extract the provided text content used for summarization.
4. Then you need to summarize the extracted text content.
5. Output the content of summarization ONLY related to user's question. The output language must be the same to user's question language.
6. If you think the provided text content is not related to user questions at all, ONLY output 'Did not find the information you want.'!!.



##################################################
User Prompt: 

Question: What can you do?
```

## 方法二：使用 `ProfileFactory`

使用 `ProfileFactory` 是一种更灵活的创建档案的方式。


### 创建档案工厂

```python
from typing import Optional
from dbgpt.agent import ProfileFactory, Profile, DefaultProfile

class MyProfileFactory(ProfileFactory):
    def create_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Optional[Profile]:
        return DefaultProfile(
            name="Aristotle",
            role="Summarizer",
            goal=(
                "Summarize answer summaries based on user questions from provided "
                "resource information or from historical conversation memories."
            ),
            desc=(
                "You can summarize provided text content according to user's questions"
                " and output the summarization."
            ),
            expand_prompt="Keep your answer concise",
            examples=""
        )
```

### 使用档案工厂

使用档案工厂时，您需要将工厂传递给 `ProfileConfig` 类。
在这种情况下，您不需要提供智能体的名称、角色、目标和描述。

```python
from dbgpt.agent import ProfileConfig

profile: ProfileConfig = ProfileConfig(
    factory=MyProfileFactory(),
)
```

让我们看看从档案生成的最终提示词。

```python
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
Keep your answer concise 

*** IMPORTANT REMINDER ***
Please answer in English.



##################################################
User Prompt: 

Question: What can you do?
```

## 总结

在本节中，您学习了如何使用 `ProfileConfig` 类和 `ProfileFactory` 为智能体创建档案。
使用这些方法定义智能体的档案非常灵活且简单，特别是在您需要创建数千个智能体场景时。
