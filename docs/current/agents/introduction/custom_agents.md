# 编写自定义智能体

## 介绍

在本示例中，我们将向您展示如何创建一个可以用作总结器的自定义智能体。

## 安装

通过运行以下命令安装所需的包：

```bash
pip install "dbgpt[agent,simple_framework]>=0.7.0" "dbgpt_ext>=0.7.0" -U
pip install openai
```

## 创建自定义智能体

### 初始化智能体

在大多数情况下，您只需继承基础智能体并重写相应的方法即可。

```python
from dbgpt.agent import ConversableAgent

class MySummarizerAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### 定义角色

在设计每个智能体之前，需要定义其角色、身份和功能定位。具体定义如下：

```python
from dbgpt.agent import ConversableAgent, ProfileConfig

class MySummarizerAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        # 智能体的名称
        name="Aristotle",
        # 智能体的角色
        role="Summarizer",
        # 智能体的核心功能目标，告知 LLM 它可以做什么。
        goal=(
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories."
        ),
        # 智能体的介绍和描述，用于任务分配和展示。
        # 如果为空，则使用 goal 的内容。
        desc=(
            "You can summarize provided text content according to user's questions"
            " and output the summarization."
        ),
    )
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### 补充提示约束

智能体的提示词默认使用固定模板组装（如果有特殊需求，可以绑定外部模板）。主要包含：
1. 身份定义（自动构建）
2. 资源信息（自动构建）
3. 约束逻辑
4. 参考案例（可选）
5. 输出格式模板和约束（自动构建）

因此，我们可以如下定义智能体提示词的约束：

```python
from dbgpt.agent import ConversableAgent, ProfileConfig

class MySummarizerAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        # 智能体的名称
        name="Aristotle",
        # 智能体的角色
        role="Summarizer",
        # 智能体的核心功能目标，告知 LLM 它可以做什么。
        goal=(
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories."
        ),
        # 智能体的介绍和描述，用于任务分配和展示。
        # 如果为空，则使用 goal 的内容。
        desc=(
            "You can summarize provided text content according to user's questions"
            " and output the summarization."
        ),
        # 参考以下内容。可以包含多个约束和推理
        # 限制逻辑，并支持使用参数模板 {{ param_name }}。
        constraints=[
            "Prioritize the summary of answers to user questions from the improved resource"
            " text. If no relevant information is found, summarize it from the historical "
            "dialogue memory given. It is forbidden to make up your own.",
            "You need to first detect user's question that you need to answer with your"
            " summarization.",
            "Extract the provided text content used for summarization.",
            "Then you need to summarize the extracted text content.",
            "Output the content of summarization ONLY related to user's question. The "
            "output language must be the same to user's question language.",
            "If you think the provided text content is not related to user questions at "
            "all, ONLY output '{{ not_related_message }}'!!.",
        ]
    )
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### 提示模板格式

如果在提示词中使用了动态参数，则需要在实际对话过程中组装值，并且需要重载并实现以下接口（`_init_reply_message`）：

```python
from dbgpt.agent import AgentMessage, ConversableAgent, ProfileConfig

NOT_RELATED_MESSAGE = "Did not find the information you want."


class MySummarizerAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        # 智能体的名称
        name="Aristotle",
        # 智能体的角色
        role="Summarizer",
        # 智能体的核心功能目标，告知 LLM 它可以做什么。
        goal=(
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories."
        ),
        # 智能体的介绍和描述，用于任务分配和展示。
        # 如果为空，则使用 goal 的内容。
        desc=(
            "You can summarize provided text content according to user's questions"
            " and output the summarization."
        ),
        # 参考以下内容。可以包含多个约束和推理
        # 限制逻辑，并支持使用参数模板 {{ param_name }}。
        constraints=[
            "Prioritize the summary of answers to user questions from the improved resource"
            " text. If no relevant information is found, summarize it from the historical "
            "dialogue memory given. It is forbidden to make up your own.",
            "You need to first detect user's question that you need to answer with your"
            " summarization.",
            "Extract the provided text content used for summarization.",
            "Then you need to summarize the extracted text content.",
            "Output the content of summarization ONLY related to user's question. The "
            "output language must be the same to user's question language.",
            "If you think the provided text content is not related to user questions at "
            "all, ONLY output '{{ not_related_message }}'!!.",
        ],
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        # 填充提示模板中的动态参数
        reply_message.context = {"not_related_message": NOT_RELATED_MESSAGE}
        return reply_message
```

### 资源预加载（可选）

如果有一些特定资源，需要在智能体初始化时预先加载绑定的资源。您可以参考以下实现。具体根据资源的实际情况决定。在大多数情况下，这不是必需的。

```python
from dbgpt.agent import ConversableAgent, AgentMessage

class MySummarizerAgent(ConversableAgent):
    # ... 其他代码
    async def preload_resource(self) -> None:
        # 加载所需资源
        for resource in self.resources:
            # 加载您的资源，请在此处编写您自己的代码
            pass
```

### 结果检查（可选）

如果需要严格验证动作执行结果，有两种模式：代码逻辑验证和 LLM 验证。当然，验证不是必需的，默认未实现即为通过。以下是使用 LLM 验证的示例：

```python

from typing import Tuple, Optional

from dbgpt.agent import ConversableAgent, AgentMessage
from dbgpt.core import ModelMessageRoleType

CHECK_RESULT_SYSTEM_MESSAGE = (
    "You are an expert in analyzing the results of a summary task."
    "Your responsibility is to check whether the summary results can summarize the "
    "input provided by the user, and then make a judgment. You need to answer "
    "according to the following rules:\n"
    "    Rule 1: If you think the summary results can summarize the input provided"
    " by the user, only return True.\n"
    "    Rule 2: If you think the summary results can NOT summarize the input "
    "provided by the user, return False and the reason, split by | and ended "
    "by TERMINATE. For instance: False|Some important concepts in the input are "
    "not summarized. TERMINATE"
)

class MySummarizerAgent(ConversableAgent):
    # ... 其他代码
    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        current_goal = message.current_goal
        action_report = message.action_report
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.thinking(
            messages=[
                AgentMessage(
                    role=ModelMessageRoleType.HUMAN,
                    content=(
                        "Please understand the following user input and summary results"
                        " and give your judgment:\n"
                        f"User Input: {current_goal}\n"
                        f"Summary Results: {task_result}"
                    ),
                )
            ],
            prompt=CHECK_RESULT_SYSTEM_MESSAGE,
        )
        
        fail_reason = ""
        if check_result and (
            "true" in check_result.lower() or "yes" in check_result.lower()
        ):
            success = True
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = (
                    "The summary results cannot summarize the user input due"
                    f" to: {fail_reason}. Please re-understand and complete the summary"
                    " task."
                )
            except Exception:
                fail_reason = (
                    "The summary results cannot summarize the user input. "
                    "Please re-understand and complete the summary task."
                )
        return success, fail_reason
```

## 创建自定义动作

### 初始化动作

所有智能体对外部环境和真实世界的操作都通过 `Action` 来实现。Action 定义了智能体的输出内容结构，并实际执行相应的操作。具体的 `Action` 实现继承自 `Action` 基类，如下所示：

```python
from typing import Optional
from pydantic import BaseModel, Field
from dbgpt.vis import Vis
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.agent.util import cmp_string_equal

NOT_RELATED_MESSAGE = "Did not find the information you want."

# 当前智能体需要执行的动作所需的参数对象
class SummaryActionInput(BaseModel):
    summary: str = Field(
        ...,
        description="The summary content",
    )

class SummaryAction(Action[SummaryActionInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        # 当前智能体需要使用的资源类型
        # 这里我们不需要使用资源，直接返回 None
        return None
    
    @property
    def render_protocol(self) -> Optional[Vis]:
        # 当前智能体需要使用的可视化渲染协议
        # 这里我们不需要使用可视化渲染，直接返回 None
        return None
    
    @property
    def out_model_type(self):
        return SummaryActionInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """执行动作。
        
        动作的实际执行入口。模型推理完成后会自动发起动作执行。
        """
        try:
            # 解析输入消息
            param: SummaryActionInput = self._input_convert(ai_message, SummaryActionInput)
        except Exception:
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found, "
                f"ai message: {ai_message}",
            )
        # 检查总结内容是否与用户问题无关
        if param.summary and cmp_string_equal(
            param.summary, 
            NOT_RELATED_MESSAGE,
            ignore_case=True,
            ignore_punctuation=True,
            ignore_whitespace=True,
        ):
            return ActionOutput(
                is_exe_success=False,
                content="the provided text content is not related to user questions at all."
                f"ai message: {ai_message}",
            )
        else:
            return ActionOutput(
                is_exe_success=True,
                content=param.summary,
            )
```

### 将动作绑定到智能体

在智能体和动作的开发定义完成后，将动作绑定到相应的智能体。

```python
from pydantic import BaseModel
from dbgpt.agent import Action,ConversableAgent

class SummaryActionInput(BaseModel):
    ...

class SummaryAction(Action[SummaryActionInput]):
    ...

class MySummarizerAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([SummaryAction])
```

### 动作扩展参数处理

```python
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from dbgpt.agent import Agent, Action, AgentMessage, ActionOutput, AgentResource, ConversableAgent


class SummaryActionInput(BaseModel):
    ...

class SummaryAction(Action[SummaryActionInput]):
    ...

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        # 读取智能体传入的扩展参数
        extra_param = kwargs.get("action_extra_param_key", None)
        pass
    
class MySummarizerAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([SummaryAction])
    
    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return {"action_extra_param_key": "this is extra param"}
```

## 使用您的自定义智能体

自定义智能体创建完成后，您可以通过以下方式使用它：

```python

import asyncio
import os

from dbgpt.agent import AgentContext, ConversableAgent, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.model.proxy import OpenAILLMClient

class MySummarizerAgent(ConversableAgent):
    ...

async def main():
    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # 或其他模型，例如 "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(conv_id="summarize")

    agent_memory: AgentMemory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="summarize")

    summarizer = (
        await MySummarizerAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()
  

    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message="""I want to summarize advantages of Nuclear Power according to the following content.
            Nuclear power in space is the use of nuclear power in outer space, typically either small fission systems or radioactive decay for electricity or heat. Another use is for scientific observation, as in a Mössbauer spectrometer. The most common type is a radioisotope thermoelectric generator, which has been used on many space probes and on crewed lunar missions. Small fission reactors for Earth observation satellites, such as the TOPAZ nuclear reactor, have also been flown.[1] A radioisotope heater unit is powered by radioactive decay and can keep components from becoming too cold to function, potentially over a span of decades.[2]
            The United States tested the SNAP-10A nuclear reactor in space for 43 days in 1965,[3] with the next test of a nuclear reactor power system intended for space use occurring on 13 September 2012 with the Demonstration Using Flattop Fission (DUFF) test of the Kilopower reactor.[4]
            After a ground-based test of the experimental 1965 Romashka reactor, which used uranium and direct thermoelectric conversion to electricity,[5] the USSR sent about 40 nuclear-electric satellites into space, mostly powered by the BES-5 reactor. The more powerful TOPAZ-II reactor produced 10 kilowatts of electricity.[3]
            Examples of concepts that use nuclear power for space propulsion systems include the nuclear electric rocket (nuclear powered ion thruster(s)), the radioisotope rocket, and radioisotope electric propulsion (REP).[6] One of the more explored concepts is the nuclear thermal rocket, which was ground tested in the NERVA program. Nuclear pulse propulsion was the subject of Project Orion.[7]
            Regulation and hazard prevention[edit]
            After the ban of nuclear weapons in space by the Outer Space Treaty in 1967, nuclear power has been discussed at least since 1972 as a sensitive issue by states.[8] Particularly its potential hazards to Earth's environment and thus also humans has prompted states to adopt in the U.N. General Assembly the Principles Relevant to the Use of Nuclear Power Sources in Outer Space (1992), particularly introducing safety principles for launches and to manage their traffic.[8]
            Benefits
            Both the Viking 1 and Viking 2 landers used RTGs for power on the surface of Mars. (Viking launch vehicle pictured)
            While solar power is much more commonly used, nuclear power can offer advantages in some areas. Solar cells, although efficient, can only supply energy to spacecraft in orbits where the solar flux is sufficiently high, such as low Earth orbit and interplanetary destinations close enough to the Sun. Unlike solar cells, nuclear power systems function independently of sunlight, which is necessary for deep space exploration. Nuclear-based systems can have less mass than solar cells of equivalent power, allowing more compact spacecraft that are easier to orient and direct in space. In the case of crewed spaceflight, nuclear power concepts that can power both life support and propulsion systems may reduce both cost and flight time.[9]
            Selected applications and/or technologies for space include:
            Radioisotope thermoelectric generator
            Radioisotope heater unit
            Radioisotope piezoelectric generator
            Radioisotope rocket
            Nuclear thermal rocket
            Nuclear pulse propulsion
            Nuclear electric rocket
            """,
    )
    print(await agent_memory.gpts_memory.app_link_chat_message("summarize"))

if __name__ == "__main__":
    asyncio.run(main())
```

完整代码如下：

```python
import asyncio
import os
from typing import Any, Dict, Optional, Tuple, List

from dbgpt.agent import (
    Agent,
    Action,
    ActionOutput,
    AgentContext,
    AgentMemory,
    AgentMessage,
    AgentResource,
    ConversableAgent,
    LLMConfig,
    ProfileConfig,
    ResourceType,
    UserProxyAgent,
)
from dbgpt.agent.util import cmp_string_equal
from dbgpt.core import ModelMessageRoleType
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.vis import Vis
from pydantic import BaseModel, Field

NOT_RELATED_MESSAGE = "Did not find the information you want."

CHECK_RESULT_SYSTEM_MESSAGE = (
    "You are an expert in analyzing the results of a summary task."
    "Your responsibility is to check whether the summary results can summarize the "
    "input provided by the user, and then make a judgment. You need to answer "
    "according to the following rules:\n"
    "    Rule 1: If you think the summary results can summarize the input provided"
    " by the user, only return True.\n"
    "    Rule 2: If you think the summary results can NOT summarize the input "
    "provided by the user, return False and the reason, split by | and ended "
    "by TERMINATE. For instance: False|Some important concepts in the input are "
    "not summarized. TERMINATE"
)


class MySummarizerAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        # 智能体的名称
        name="Aristotle",
        # 智能体的角色
        role="Summarizer",
        # 智能体的核心功能目标，告知 LLM 它可以做什么。
        goal=(
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories."
        ),
        # 智能体的介绍和描述，用于任务分配和展示。
        # 如果为空，则使用 goal 的内容。
        desc=(
            "You can summarize provided text content according to user's questions"
            " and output the summarization."
        ),
        # 参考以下内容。可以包含多个约束和推理
        # 限制逻辑，并支持使用参数模板 {{ param_name }}。
        constraints=[
            "Prioritize the summary of answers to user questions from the improved resource"
            " text. If no relevant information is found, summarize it from the historical "
            "dialogue memory given. It is forbidden to make up your own.",
            "You need to first detect user's question that you need to answer with your"
            " summarization.",
            "Extract the provided text content used for summarization.",
            "Then you need to summarize the extracted text content.",
            "Output the content of summarization ONLY related to user's question. The "
            "output language must be the same to user's question language.",
            "If you think the provided text content is not related to user questions at "
            "all, ONLY output '{{ not_related_message }}'!!.",
        ],
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([SummaryAction])

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        # 填充提示模板中的动态参数
        reply_message.context = {"not_related_message": NOT_RELATED_MESSAGE}
        return reply_message

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return {"action_extra_param_key": "this is extra param"}

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        current_goal = message.current_goal
        action_report = message.action_report
        task_result = ""
        if action_report:
            task_result = action_report.content

        check_result, model = await self.thinking(
            messages=[
                AgentMessage(
                    role=ModelMessageRoleType.HUMAN,
                    content=(
                        "Please understand the following user input and summary results"
                        " and give your judgment:\n"
                        f"User Input: {current_goal}\n"
                        f"Summary Results: {task_result}"
                    ),
                )
            ],
            prompt=CHECK_RESULT_SYSTEM_MESSAGE,
        )

        fail_reason = ""
        if check_result and (
            "true" in check_result.lower() or "yes" in check_result.lower()
        ):
            success = True
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = (
                    "The summary results cannot summarize the user input due"
                    f" to: {fail_reason}. Please re-understand and complete the summary"
                    " task."
                )
            except Exception:
                fail_reason = (
                    "The summary results cannot summarize the user input. "
                    "Please re-understand and complete the summary task."
                )
        return success, fail_reason


# 当前智能体需要执行的动作所需的参数对象
class SummaryActionInput(BaseModel):
    summary: str = Field(
        ...,
        description="The summary content",
    )


class SummaryAction(Action[SummaryActionInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        # 当前智能体需要使用的资源类型
        # 这里我们不需要使用资源，直接返回 None
        return None

    @property
    def render_protocol(self) -> Optional[Vis]:
        # 当前智能体需要使用的可视化渲染协议
        # 这里我们不需要使用可视化渲染，直接返回 None
        return None

    @property
    def out_model_type(self):
        return SummaryActionInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """执行动作。

        动作的实际执行入口。模型推理完成后会自动发起动作执行。
        """
        extra_param = kwargs.get("action_extra_param_key", None)
        try:
            # 解析输入消息
            param: SummaryActionInput = self._input_convert(
                ai_message, SummaryActionInput
            )
        except Exception:
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found, "
                f"ai message: {ai_message}",
            )
        # 检查总结内容是否与用户问题无关
        if param.summary and cmp_string_equal(
            param.summary,
            NOT_RELATED_MESSAGE,
            ignore_case=True,
            ignore_punctuation=True,
            ignore_whitespace=True,
        ):
            return ActionOutput(
                is_exe_success=False,
                content="the provided text content is not related to user questions at all."
                f"ai message: {ai_message}",
            )
        else:
            return ActionOutput(
                is_exe_success=True,
                content=param.summary,
            )


async def main():
    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # 或其他模型，例如 "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(conv_id="summarize")

    agent_memory: AgentMemory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="summarize")

    summarizer = (
        await MySummarizerAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message="""I want to summarize advantages of Nuclear Power according to the following content.
            Nuclear power in space is the use of nuclear power in outer space, typically either small fission systems or radioactive decay for electricity or heat. Another use is for scientific observation, as in a Mössbauer spectrometer. The most common type is a radioisotope thermoelectric generator, which has been used on many space probes and on crewed lunar missions. Small fission reactors for Earth observation satellites, such as the TOPAZ nuclear reactor, have also been flown.[1] A radioisotope heater unit is powered by radioactive decay and can keep components from becoming too cold to function, potentially over a span of decades.[2]
            The United States tested the SNAP-10A nuclear reactor in space for 43 days in 1965,[3] with the next test of a nuclear reactor power system intended for space use occurring on 13 September 2012 with the Demonstration Using Flattop Fission (DUFF) test of the Kilopower reactor.[4]
            After a ground-based test of the experimental 1965 Romashka reactor, which used uranium and direct thermoelectric conversion to electricity,[5] the USSR sent about 40 nuclear-electric satellites into space, mostly powered by the BES-5 reactor. The more powerful TOPAZ-II reactor produced 10 kilowatts of electricity.[3]
            Examples of concepts that use nuclear power for space propulsion systems include the nuclear electric rocket (nuclear powered ion thruster(s)), the radioisotope rocket, and radioisotope electric propulsion (REP).[6] One of the more explored concepts is the nuclear thermal rocket, which was ground tested in the NERVA program. Nuclear pulse propulsion was the subject of Project Orion.[7]
            Regulation and hazard prevention[edit]
            After the ban of nuclear weapons in space by the Outer Space Treaty in 1967, nuclear power has been discussed at least since 1972 as a sensitive issue by states.[8] Particularly its potential hazards to Earth's environment and thus also humans has prompted states to adopt in the U.N. General Assembly the Principles Relevant to the Use of Nuclear Power Sources in Outer Space (1992), particularly introducing safety principles for launches and to manage their traffic.[8]
            Benefits
            Both the Viking 1 and Viking 2 landers used RTGs for power on the surface of Mars. (Viking launch vehicle pictured)
            While solar power is much more commonly used, nuclear power can offer advantages in some areas. Solar cells, although efficient, can only supply energy to spacecraft in orbits where the solar flux is sufficiently high, such as low Earth orbit and interplanetary destinations close enough to the Sun. Unlike solar cells, nuclear power systems function independently of sunlight, which is necessary for deep space exploration. Nuclear-based systems can have less mass than solar cells of equivalent power, allowing more compact spacecraft that are easier to orient and direct in space. In the case of crewed spaceflight, nuclear power concepts that can power both life support and propulsion systems may reduce both cost and flight time.[9]
            Selected applications and/or technologies for space include:
            Radioisotope thermoelectric generator
            Radioisotope heater unit
            Radioisotope piezoelectric generator
            Radioisotope rocket
            Nuclear thermal rocket
            Nuclear pulse propulsion
            Nuclear electric rocket
            """,
    )
    print(await agent_memory.gpts_memory.app_link_chat_message("summarize"))


if __name__ == "__main__":
    asyncio.run(main())
```
