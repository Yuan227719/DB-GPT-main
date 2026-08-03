# 档案到提示词

在前面的章节中，我们已经介绍了如何为智能体创建档案，并了解了如何从档案生成提示词。

在本节中，我们将进一步介绍如何从档案生成提示词。

## 什么是提示词模板

在前面的章节中，我们使用了内部模板来生成提示词，让我们看看这个模板：

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

real_profile = profile.create_profile()

print(f"System Prompt Template: \n{real_profile.get_system_prompt_template()}")
print("#" * 50)
print(f"User Prompt Template: \n{real_profile.get_user_prompt_template()}")
```

运行上述代码将生成以下输出：
```
System Prompt Template: 
You are a {{ role }}, {% if name %}named {{ name }}, {% endif %}your goal is {{ goal }}.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.
{% if resource_prompt %}{{ resource_prompt }} 
{% endif %}{% if expand_prompt %}{{ expand_prompt }} 
{% endif %}
*** IMPORTANT REMINDER ***
{% if language == 'zh' %}Please answer in simplified Chinese.
{% else %}Please answer in English.
{% endif %}
{% if constraints %}{% for constraint in constraints %}{{ loop.index }}. {{ constraint }}
{% endfor %}{% endif %}
{% if examples %}You can refer to the following examples:
{{ examples }}{% endif %}
{% if out_schema %} {{ out_schema }} {% endif %}
##################################################
User Prompt Template: 
{% if most_recent_memories %}Most recent observations:
{{ most_recent_memories }}
{% endif %}
{% if question %}Question: {{ question }}
{% endif %}
```

该模板是一个 jinja2 模板，目前我们在智能体中仅使用 jinja2，因为它简单且灵活。

## 使用自定义提示词模板

首先，创建一个简单的系统提示词模板和用户提示词模板：

```python
my_system_prompt_template = """\
You are a {{ role }}, {% if name %}named {{ name }}, {% endif %}your goal is {{ goal }}.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
{% if language == 'zh' %}\
Please answer in simplified Chinese.
{% else %}\
Please answer in English.
{% endif %}\
"""  # noqa

my_user_prompt_template = "User question: {{ question }}"
```

然后，使用自定义提示词模板创建档案：

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
    system_prompt_template=my_system_prompt_template,
    user_prompt_template=my_user_prompt_template,
)

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
User question: What can you do?
```
