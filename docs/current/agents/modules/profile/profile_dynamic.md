# 动态档案

在前面的章节中，我们已经介绍了如何从档案生成提示词。
有时，您只想以简单的方式修改档案的一部分，这里我们将介绍如何创建动态档案。

## 档案的动态字段

这里我们使用 `DynConfig` 来创建动态档案，您可以修改原始档案的字段。

创建一个名为 `profile_dynamic.py` 的 Python 文件，并添加以下代码：

```python
from dbgpt.agent import ProfileConfig, DynConfig

profile: ProfileConfig = ProfileConfig(
    # 智能体的名称
    name=DynConfig(
        "Aristotle",
       key="summary_profile_name",
       provider="env"
    ),
    # 智能体的角色
    role="Summarizer",
)
```

在上面的示例中，我们使用 `DynConfig` 创建了一个动态档案字段 "name"，
默认值为 "Aristotle"，key 为 "summary_profile_name"，provider 为 "env"。
`provider="env"` 表示该字段的值将从环境变量中读取。

然后，您可以从配置创建档案并生成提示词。

```python
real_profile = profile.create_profile()
system_prompt = real_profile.format_system_prompt(question="What can you do?")
user_prompt = real_profile.format_user_prompt(question="What can you do?")
print(f"System Prompt: \n{system_prompt}")
print("#" * 50)
print(f"User Prompt: \n{user_prompt}")
```

在未设置环境变量的情况下运行上述代码：
```bash
python profile_dynamic.py
```

输出将是：
```
System Prompt: 
You are a Summarizer, named Aristotle, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.



##################################################
User Prompt: 

Question: What can you do?
```

在设置了环境变量的情况下运行上述代码：
```bash
summary_profile_name="Plato" python profile_dynamic.py
```

输出将是：
```
System Prompt: 
You are a Summarizer, named Plato, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.



##################################################
User Prompt: 

Question: What can you do?
```
