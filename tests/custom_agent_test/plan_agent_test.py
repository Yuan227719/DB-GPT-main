
import asyncio
import os

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    AutoPlanChatManager,
    LLMConfig,
    UserProxyAgent,
)
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent 
from dbgpt.model.proxy import OpenAILLMClient

async def main():
    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # 或其他模型，例如 "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(
        conv_id="test123", language="en", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test123")

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    sql_boy = (
        await DataScientistAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(db_resource)
        .bind(agent_memory)
        .build()
    )
    manager = (
        await AutoPlanChatManager()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([sql_boy])

    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="Analyze student scores from at least three dimensions",
    )

    # dbgpt-vis 消息信息
    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())