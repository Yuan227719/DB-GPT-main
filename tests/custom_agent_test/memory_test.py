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