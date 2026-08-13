import json
import logging
from typing import Any, Dict, List, Optional, Type, Union

from dbgpt._private.pydantic import Field
from dbgpt.agent import (
    ActionOutput,
    Agent,
    AgentMemoryFragment,
    AgentMessage,
    ConversableAgent,
    ProfileConfig,
    Resource,
    ResourceType,
    StructuredAgentMemoryFragment,
)
from dbgpt.agent.core.role import AgentRunMode
from dbgpt.agent.resource import BaseTool, ResourcePack, ToolPack
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt.util.configure import DynConfig

from ...core import ModelMessageRoleType
from .actions.react_action import ReActAction, Terminate

logger = logging.getLogger(__name__)


def _looks_like_llm_error(text: str) -> bool:
    """判断一段文本是否像是 LLM 服务错误（而非业务最终答案）。

    用于 ReActAgent.act() 的容错：模型偶尔把服务 500 错误文本当作回复，
    此时不应被当成最终答案接受。
    """
    lower = (text or "").lower()
    return any(
        k in lower
        for k in (
            "generate error",
            "error code",
            "waitlist",
            "failed to forward",
            "internal server error",
            "llm server",
        )
    )


_REACT_DEFAULT_GOAL = """Answer the following questions or solve the tasks by \
selecting the right ACTION from the ACTION SPACE as best as you can. 
# ACTION SPACE Simple Description #
{{ action_space_simple_desc }}
"""

_REACT_SYSTEM_TEMPLATE = """\
You are a {{ role }}, {% if name %}named {{ name }}. {% endif %}\
{{ goal }}
task. For each step, you must output an Action; it cannot be empty. The maximum number \
of steps you can take is {{ max_steps }}.
Do not output an empty string!
{{ action_space }}
# RESPONSE FORMAT # 
IMPORTANT:
- You must never answer directly outside the ReAct format.
- Every response must contain exactly one Action and one Action Input.
- If the task is complete, use exactly:
Thought: ...
Phase: 返回最终结果
Action: terminate
Action Input: {"result": "final answer"}
- Do not put the final answer as plain markdown outside Action Input.

For each task input, your response should contain:
1. One analysis of the task and the current environment, reasoning to determine the \
next action (prefix "Thought: ").
2. What this step is trying to do (prefix "Action Intention: "), short and \
user-facing.
3. Why this action is needed now (prefix "Action Reason: "), short and \
user-facing.
4. One action string in the ACTION SPACE (prefix "Action: "), should be one of \
[{{ action_space_names }}].
5. One action input (prefix "Action Input: "), empty if no input is required.
# EXAMPLE INTERACTION #
Thought: ...(Your analysis of the task and reasoning for the next action.)
Action Intention: ...(What this step will do, e.g. "探索数据结构")
Action Reason: ...(Why this action is needed now)
Action: ...
Action Input: ...
Observation: ...(This is output provided by the external environment or Action output, \
you are not allowed to generate it.)
{% if task_progress %}
{{ task_progress }}
You MUST NOT repeat any action already listed above as ✅ completed.
Pick the NEXT action that has NOT been done yet to make progress toward the final goal.
{% endif %}
Please Solve this task:
{{ question }}\
Please answer in the same language as the user's question.
The current time is: {{ now_time }}.
"""

# Not needed additional user prompt template
_REACT_USER_TEMPLATE = """"""


_REACT_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if thought %}Thought: {{ thought }} {% endif %}
{% if phase %}Phase: {{ phase }} {% endif %}
{% if action_intention %}Action Intention: {{ action_intention }} {% endif %}
{% if action_reason %}Action Reason: {{ action_reason }} {% endif %}
{% if action %}Action: {{ action }} {% endif %}
{% if action_input %}Action Input: {{ action_input }} {% endif %}
{% if observation %}Observation: {{ observation }} {% endif %}
"""


class ReActAgent(ConversableAgent):
    max_retry_count: int = 30
    run_mode: AgentRunMode = AgentRunMode.LOOP

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "ReAct",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_name",
        ),
        role=DynConfig(
            "ReActToolMaster",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_role",
        ),
        goal=DynConfig(
            _REACT_DEFAULT_GOAL,
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_goal",
        ),
        system_prompt_template=_REACT_SYSTEM_TEMPLATE,
        user_prompt_template=_REACT_USER_TEMPLATE,
        write_memory_template=_REACT_WRITE_MEMORY_TEMPLATE,
    )
    parser: ReActOutputParser = Field(default_factory=ReActOutputParser)

    def __init__(self, **kwargs):
        """Init indicator AssistantAgent."""
        super().__init__(**kwargs)

        self._init_actions([ReActAction, Terminate])

        # Auto-enable multi-layer context management if configured
        if (
            self.agent_context is not None
            and self.agent_context.enable_context_management
        ):
            self.init_context_management()

    async def _a_init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message, rely_messages)

        tool_packs = ToolPack.from_resource(self.resource)
        action_space = []
        action_space_names = []
        action_space_simple_desc = []
        if tool_packs:
            tool_pack = tool_packs[0]
            for tool in tool_pack.sub_resources:
                tool_desc, _ = await tool.get_prompt(lang=self.language)
                action_space_names.append(tool.name)
                action_space.append(tool_desc)
                if isinstance(tool, BaseTool):
                    tool_simple_desc = tool.description
                else:
                    tool_simple_desc = tool.get_prompt()
                action_space_simple_desc.append(f"{tool.name}: {tool_simple_desc}")
        else:
            for action in self.actions:
                action_space_names.append(action.name)
                action_space.append(action.get_action_description())
            # self.actions
        reply_message.context = {
            "max_steps": self.max_retry_count,
            "action_space": "\n".join(action_space),
            "action_space_names": ", ".join(action_space_names),
            "action_space_simple_desc": "\n".join(action_space_simple_desc),
        }
        return reply_message

    async def preload_resource(self) -> None:
        await super().preload_resource()
        self._check_and_add_terminate()

    def _check_and_add_terminate(self):
        if not self.resource:
            return
        _is_has_terminal = False

        def _has_terminal(r: Resource):
            nonlocal _is_has_terminal
            if r.type() == ResourceType.Tool and isinstance(r, Terminate):
                _is_has_terminal = True
            return r

        _has_add_terminal = False

        def _add_terminate(r: Resource):
            nonlocal _has_add_terminal
            if not _has_add_terminal and isinstance(r, ResourcePack):
                terminal = Terminate()
                r._resources[terminal.name] = terminal
                _has_add_terminal = True
            return r

        self.resource.apply(apply_func=_has_terminal)
        if not _is_has_terminal:
            # Add terminal action to the resource
            self.resource.apply(apply_pack_func=_add_terminate)

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load agent bind resource."""
        if self.resource:

            def _remove_tool(r: Resource):
                if r.type() == ResourceType.Tool:
                    return None
                return r

            # Remove all tools from the resource
            # We will handle tools separately
            new_resource = self.resource.apply(apply_func=_remove_tool)
            if new_resource:
                resource_prompt, resource_reference = await new_resource.get_prompt(
                    lang=self.language, question=question
                )
                return resource_prompt, resource_reference
        return None, None

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        return {
            "parser": self.parser,
        }

    async def act(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """Perform actions."""
        message_content = message.content
        if not message_content:
            raise ValueError("The response is empty.")
        try:
            steps = self.parser.parse_current_step(message_content)
            err_msg = None
            if not steps:
                # 模型输出无 Action: 的纯文本，无法确认是最终答案还是中途计划。
                # 不盲目当最终答案接受（否则"现在查询 errorcode..."这类计划文字会被
                # 误判为最终答案而早退）。统一要求 ReAct 格式：要么给出工具调用，
                # 要么用 Action: terminate 结束。
                if (
                    "Action:" not in message_content
                    and not _looks_like_llm_error(message_content)
                ):
                    return ActionOutput(
                        is_exe_success=False,
                        content=(
                            "你的回复缺少 ReAct 格式的 Action 行，无法确认是最终答案还是计划。"
                            "请严格按格式输出：\n"
                            "Thought: <你的分析>\n"
                            "Action: <工具名，或全部完成时用 terminate>\n"
                            "Action Input: <工具参数 JSON，terminate 时为 "
                            '{"result": "最终答案"}>。\n'
                            "需要查询/生成/渲染时就调用对应工具；只有全部目标完成后才用 "
                            "Action: terminate 结束。"
                        ),
                    )
                err_msg = (
                    "No correct response found. Please check your response, which must"
                    " be in the format indicated in the system prompt."
                )
            elif len(steps) != 1:
                err_msg = "Only one action is allowed each time."
            if err_msg:
                return ActionOutput(is_exe_success=False, content=err_msg)
            # 单个 step 但 action 为空且非 terminate：模型解析出了 step 却没给出
            # 实际的工具调用（如只有 Thought / Action Intention）。统一提示补全，
            # 不误当 terminate。
            if (
                steps
                and len(steps) == 1
                and not steps[0].action
                and not steps[0].is_terminal
            ):
                return ActionOutput(
                    is_exe_success=False,
                    content=(
                        "你的回复没有给出实际的工具调用（Action 为空）。请补全："
                        "Action: <工具名> 和 Action Input: {<参数>}，然后继续执行；"
                        "只有在真正完成后才用 Action: terminate 结束。"
                    ),
                )
        except Exception as e:
            logger.warning(f"review error: {e}")

        action_output = await super().act(
            message=message,
            sender=sender,
            reviewer=reviewer,
            is_retry_chat=is_retry_chat,
            last_speaker_name=last_speaker_name,
            **kwargs,
        )
        return action_output

    @property
    def memory_fragment_class(self) -> Type[AgentMemoryFragment]:
        """Return the memory fragment class."""
        return StructuredAgentMemoryFragment

    async def read_memories(
        self,
        observation: str,
    ) -> Union[str, List["AgentMessage"]]:
        # 【上下文读取点：从 ShortTermMemory 读取历史 ReAct step】
        # self.memory.read() 返回 ShortTermMemory._fragments（最近 8 个 fragment）
        # 每个 fragment 的 raw_observation 是 JSON，含 question/thought/action/observation
        # 这里把 JSON 解析回 List[AgentMessage]（Question→HUMAN, Thought/Action→AI, Observation→HUMAN）
        # 返回的列表在 base_agent.py L1405 被 extend 进 agent_messages
        memories = await self.memory.read(observation)
        not_json_memories = []
        messages = []
        structured_memories = []
        # Pair each parsed dict with its originating fragment so we can access
        # snapshot_path later.
        fragment_by_mem: dict = {}
        for m in memories:
            if m.raw_observation:
                try:
                    mem_dict = json.loads(m.raw_observation)
                    if isinstance(mem_dict, dict):
                        structured_memories.append(mem_dict)
                        fragment_by_mem[id(mem_dict)] = m
                    elif isinstance(mem_dict, list):
                        for item in mem_dict:
                            structured_memories.append(item)
                            fragment_by_mem[id(item)] = m
                    else:
                        raise ValueError("Invalid memory format.")
                except Exception:
                    not_json_memories.append(m.raw_observation)

        for mem_dict in structured_memories:
            fragment = fragment_by_mem.get(id(mem_dict))
            snapshot_path = getattr(fragment, "snapshot_path", None)

            question = mem_dict.get("question")
            thought = mem_dict.get("thought")
            phase = mem_dict.get("phase")
            action = mem_dict.get("action")
            action_input = mem_dict.get("action_input")
            observation = mem_dict.get("observation")
            if question:
                messages.append(
                    AgentMessage(
                        content=f"Question: {question}",
                        role=ModelMessageRoleType.HUMAN,
                    )
                )
            ai_content = []
            if thought:
                ai_content.append(f"Thought: {thought}")
            if phase:
                ai_content.append(f"Phase: {phase}")
            if action:
                ai_content.append(f"Action: {action}")
            if action_input:
                ai_content.append(f"Action Input: {action_input}")
            messages.append(
                AgentMessage(
                    content="\n".join(ai_content),
                    role=ModelMessageRoleType.AI,
                )
            )

            if observation:
                obs_context = (
                    {"snapshot_path": snapshot_path} if snapshot_path else None
                )
                obs_suffix = (
                    f"\n[Full detail available at: {snapshot_path}]"
                    if snapshot_path
                    else ""
                )
                messages.append(
                    AgentMessage(
                        content=f"Observation: {observation}{obs_suffix}",
                        role=ModelMessageRoleType.HUMAN,
                        context=obs_context,
                    )
                )

        if not messages and not_json_memories:
            messages.append(
                AgentMessage(
                    content="\n".join(not_json_memories),
                    role=ModelMessageRoleType.HUMAN,
                )
            )
        return messages
