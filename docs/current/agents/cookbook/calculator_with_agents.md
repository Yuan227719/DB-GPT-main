# 使用 Agent 作为计算器

在本示例中，我们将向您展示如何将 Agent 用作计算器。

## 安装

运行以下命令安装所需的依赖包：

```bash
pip install "dbgpt[agent]>=0.5.6rc1" -U
pip install openai
```

## 代码

创建一个新的 Python 文件并添加以下代码：

```python
import asyncio

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.model.proxy import OpenAILLMClient


async def main():
    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="test123")
    # 创建 Agent 记忆，默认记忆为 ShortTermMemory
    agent_memory: AgentMemory = AgentMemory()

    # 创建一个代码辅助 Agent
    coder = (
        await CodeAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    # 创建一个用户代理 Agent
    user_proxy = await UserProxyAgent().bind(context).bind(agent_memory).build()

    # 发起与用户代理 Agent 的对话
    await user_proxy.initiate_chat(
        recipient=coder,
        reviewer=user_proxy,
        message="calculate the result of 321 * 123",
    )
    # 获取 Agent 之间的对话历史消息
    print(await agent_memory.gpts_memory.one_chat_completions("test123"))


if __name__ == "__main__":
    asyncio.run(main())
```

您将看到以下输出：

````bash
Prompt manager is not available.
Prompt manager is not available.
Prompt manager is not available.
Prompt manager is not available.
Prompt manager is not available.

--------------------------------------------------------------------------------
User (to Turing)-[]:

"calculate the result of 321 * 123"

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
[{"name": "calculate the result of 321 * 123", "num": 1, "status": "complete", "agent": "Human", "markdown": "```agent-messages\n[{\"sender\": \"CodeEngineer\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-code\\n{\\\"exit_success\\\": true, \\\"language\\\": \\\"python\\\", \\\"code\\\": [[\\\"python\\\", \\\"# filename: calculate_multiplication.py\\\\n\\\\nresult = 321 * 123\\\\nprint(result)\\\"]], \\\"log\\\": \\\"\\\\n39483\\\\n\\\"}\\n```\"}]\n```"}]
```
````
