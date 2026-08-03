# 数据驱动的多智能体系统

## 介绍

DB-GPT 智能体是一个数据驱动的多智能体系统，旨在提供一个生产级的智能体开发框架。我们相信，生产级的智能体应用需要基于数据驱动的决策，并且可以在可控的智能体工作流中进行编排。

### 多层 API 设计

- Python 智能体 API：使用 Python 代码构建智能体应用，只需通过 `pip install "dbgpt[agent]"` 安装 `dbgpt` 包
- 应用 API：在 DB-GPT 项目中构建智能体应用，可以使用 DB-GPT 项目中其他模块的所有功能

大多数情况下，您可以使用 Python 智能体 API 以简单的方式构建智能体应用，当您需要将智能体部署到生产环境时，只需对代码进行少量更改。

## 快速开始

### 安装

首先，您需要使用以下命令安装 `dbgpt` 包：

```bash
pip install "dbgpt[agent,simple_framework]>=0.7.0" "dbgpt_ext>=0.7.0"
```

然后，您可以使用以下命令安装 `openai` 包：

```bash
pip install openai
```

### 使用智能体编写您的第一个计算器

LLM 是智能体的"大脑"，现在我们使用 OpenAI LLM。
在 DB-GPT 智能体中，您可以使用 DB-GPT 支持的所有模型，无论是本地部署的 LLM 还是代理模型，无论是部署在单台机器上还是集群中。

```python
import os
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient(
    model_alias="gpt-3.5-turbo", # 或其他模型，例如 "gpt-4o"
    api_base=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
)
```

然后，您需要创建一个智能体上下文和智能体记忆。

```python
from dbgpt.agent import AgentContext, AgentMemory

# language="zh" 表示中文
context: AgentContext = AgentContext(
    conv_id="test123", language="en", temperature=0.5, max_new_tokens=2048
) 
# 创建一个智能体记忆，默认记忆为 ShortTermMemory
agent_memory: AgentMemory = AgentMemory()
```
记忆存储从环境中感知到的信息，并利用记录的记忆来促进未来的行动。
默认记忆是 `ShortTermMemory`，它只保留最近 `k` 轮的对话内容。
您可以使用其他记忆类型，例如 `LongTermMemory`、`SensoryMemory` 和 `HybridMemory`，我们将在后面介绍它们。

然后，您可以创建一个代码助手智能体和一个用户代理智能体。

```python
import asyncio

from dbgpt.agent import LLMConfig, UserProxyAgent
from dbgpt.agent.expand.code_assistant_agent import CodeAssistantAgent


async def main():

    # 创建一个代码助手智能体
    coder = (
        await CodeAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )
    
    # 初始化 GptsMemory
    agent_memory.gpts_memory.init(conv_id="test123")

    # 创建一个用户代理智能体
    user_proxy = await UserProxyAgent().bind(context).bind(agent_memory).build()

    # 通过用户代理智能体发起对话
    await user_proxy.initiate_chat(
        recipient=coder,
        reviewer=user_proxy,
        message="计算 321 * 123 的结果",
    )
    # 获取智能体之间的对话历史消息
    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())

```

您将看到以下输出：

``````bash
--------------------------------------------------------------------------------
User (to Turing)-[]:

"Calculate the result of 321 * 123"

--------------------------------------------------------------------------------
un_stream ai response: ```python
# filename: calculate_multiplication.py

result = 321 * 123
print(result)
```

>>>>>>>> EXECUTING CODE BLOCK 0 (inferred language is python)...
execute_code was called without specifying a value for use_docker. Since the python docker package is not available, code will be run natively. Note: this fallback behavior is subject to change
un_stream ai response: True

--------------------------------------------------------------------------------
Turing (to User)-[gpt-3.5-turbo]:

"```python\n# filename: calculate_multiplication.py\n\nresult = 321 * 123\nprint(result)\n```"
>>>>>>>>Turing Review info: 
Pass(None)
>>>>>>>>Turing Action report: 
execution succeeded,

39483


--------------------------------------------------------------------------------
```agent-plans
[{"name": "Calculate the result of 321 * 123", "num": 1, "status": "complete", "agent": "Human", "markdown": "```agent-messages\n[{\"sender\": \"CodeEngineer\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-code\\n{\\\"exit_success\\\": true, \\\"language\\\": \\\"python\\\", \\\"code\\\": [[\\\"python\\\", \\\"# filename: calculate_multiplication.py\\\\n\\\\nresult = 321 * 123\\\\nprint(result)\\\"]], \\\"log\\\": \\\"\\\\n39483\\\\n\\\"}\\n```\"}]\n```"}]
```
``````

在 DB-GPT 智能体中，大多数核心接口都是异步的，以实现高性能。
因此，我们将以异步方式编写所有构建智能体的代码。在开发过程中，
您可以使用 `asyncio.run(main())` 来运行智能体。

以下是上述代码的示意图：

<p align="left">
  <img src={'/img/agents/introduction/agents_introduction.png'} width="720px" />
</p>

在上述代码中，我们创建了一个 `CodeAssistantAgent` 和一个 `UserProxyAgent`。
`UserProxyAgent` 是用户的代理，它是一个管理智能体，可以发起与其他智能体的对话，
并且可以审查智能体的反馈。

`CodeAssistantAgent` 是一个代码助手智能体，它将生成一些代码来解决用户的
问题，在本例中，它将生成一个 Python 代码来计算 `321 * 123` 的结果，
然后该代码将在其内部的 `CodeAction` 中执行，如果审查通过，
结果将返回给用户。

在代码的最后，我们打印了智能体之间的对话历史消息。

## 下一步

- 如何在 DB-GPT 智能体中使用工具
- 如何在 DB-GPT 智能体中连接数据库
- 如何在 DB-GPT 智能体中使用规划
- 如何在 DB-GPT 智能体中使用各种记忆
- 如何在 DB-GPT 智能体中编写自定义智能体
- 如何将智能体与 AWEL（智能体工作流表达式语言）集成
- 如何将智能体部署到生产环境
