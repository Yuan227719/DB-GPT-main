"""Base agent class for conversable agents.

本模块定义了 DB-GPT Agent 体系中所有可对话 Agent 的基类 `ConversableAgent`。

文件职责
---------
- 提供 Agent 通信的通用骨架：`send` / `receive` / `generate_reply` 三段式协议。
- 实现 ReAct（Thought → Action → Observation）的执行循环与重试机制。
- 统一管理 Agent 的上下文（AgentContext）、记忆（AgentMemory / GptsMemory /
  ShortTermMemory）、LLM 配置（LLMConfig / AIWrapper）、资源（Resource）与动作（Action）。
- 提供多层上下文管理（ContextManager）以应对长对话的预算控制与压缩。

核心类
------
- `ConversableAgent`：所有 Agent 的基类，继承自 `Role`（角色配置）与 `Agent`（通信协议接口）。
  子类（如 `ReActAgent`）通过覆写 `thinking` / `act` / `read_memories` / `write_memories`
  等钩子方法实现具体行为。

关键方法清单
------------
- `build`：Agent 构建入口，含"恢复点 #1"——从 gpts_messages 表恢复历史到 ShortTermMemory。
- `bind`：链式绑定资源 / 技能 / 动作 / LLM 配置 / 上下文 / 记忆。
- `generate_reply`：核心执行循环（@final 不可覆写），编排 thinking → review → act → verify。
- `thinking`：调用 LLM 推理（含 3 次自动重试与上下文溢出后的反应式压缩）。
- `act`：依次执行所有 Action，返回 ActionOutput。
- `_load_thinking_messages`：上下文合并关键，组装最终发给 LLM 的消息列表（含"消息 #1/#2/#3"）。
- `build_system_prompt`：构造系统提示词（支持 f-string / jinja2 模板）。

设计模式
--------
- **模板方法模式**：`generate_reply` 是固定骨架，子类覆写各步骤。
- **钩子方法**：`thinking` / `act` / `review` / `verify` / `correctness_check`
  / `prepare_act_param` / `_a_init_reply_message` / `adjust_final_message` 等均可被子类覆写。
- **责任链**：`act` 中多个 Action 串联执行，前一个的输出作为后一个的输入。
- **多层上下文管理**：`ContextManager` 在消息组装完成后进行预算控制与压缩（Layer 4 反应式压缩）。
"""

from __future__ import annotations  # 启用 PEP 563 延迟注解求值，便于类型前向引用

import asyncio  # 异步 IO 支持，用于协程调度
import json  # JSON 序列化 / 反序列化，用于消息持久化与上下文传递
import logging  # 日志记录
import time  # 时间相关操作，用于重试计时
from concurrent.futures import Executor, ThreadPoolExecutor  # 线程池执行器，用于阻塞任务异步化
from datetime import datetime  # 日期时间，用于资源变量生成
from typing import (  # 类型注解
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    cast,
    final,
)

from jinja2 import Template  # Jinja2 模板引擎，用于渲染系统提示词

from dbgpt._private.pydantic import ConfigDict, Field  # Pydantic 配置与字段
from dbgpt.core import (  # 核心抽象：LLM 客户端、消息角色类型、提示词模板
    LLMClient,
    ModelMessageRoleType,
    PromptTemplate,
)
from dbgpt.util.error_types import LLMChatError  # LLM 调用异常类型
from dbgpt.util.executor_utils import blocking_func_to_async  # 阻塞函数转异步工具
from dbgpt.util.tracer import SpanType, root_tracer  # 链路追踪
from dbgpt.util.utils import colored  # 终端彩色输出

from ..resource.base import Resource  # 资源基类（数据库、知识库等）
from ..util.conv_utils import parse_conv_id  # 会话 ID 解析
from ..util.llm.llm import LLMConfig, LLMStrategyType  # LLM 配置与策略类型
from ..util.llm.llm_client import AIWrapper  # LLM 客户端包装器
from .action.base import Action, ActionOutput  # 动作基类与动作输出
from .agent import (  # Agent 抽象：基类、上下文、消息、审查信息
    Agent,
    AgentContext,
    AgentMessage,
    AgentReviewInfo,
)
from .context import ContextBudgetConfig, ContextManager  # 多层上下文管理
from .context.manager import ContextStatusCallback  # 上下文状态回调
from .memory.agent_memory import AgentMemory  # Agent 记忆
from .memory.gpts.base import GptsMessage  # 持久化消息记录
from .memory.gpts.gpts_memory import GptsMemory  # 会话级记忆
from .profile.base import ProfileConfig  # 角色配置
from .role import AgentRunMode, Role  # 角色与运行模式

logger = logging.getLogger(__name__)  # 模块级日志器

# 运行中对话的实时步骤记录：conv_id -> {"steps": [...], "updated_at": ts}
# 供前端轮询"运行中"对话的实时进度（refresh 后仍能查看）。
# 由 API 层（_react_agent_stream）写入，结束清理。
_LIVE_AGENT_STEPS: Dict[str, Dict[str, Any]] = {}


def get_live_agent_steps(conv_id: str) -> Optional[Dict[str, Any]]:
    """返回某会话的实时运行状态（供 API 层暴露）。"""
    return _LIVE_AGENT_STEPS.get(conv_id)


class ConversableAgent(Role, Agent):
    """可对话 Agent 的基类，所有具体 Agent（如 ReActAgent）均继承自此类。

    继承关系
    --------
    - `Role`：提供角色配置（name / role / profile / language 等元信息）。
    - `Agent`：定义通信协议接口（send / receive / generate_reply 等）。

    职责
    ----
    - 实现 Agent 之间通信的通用骨架（send → receive → generate_reply → send）。
    - 在 `generate_reply` 中编排 ReAct 执行循环：thinking → review → act → verify → retry。
    - 统一管理上下文、记忆、LLM 配置、资源、动作等运行时依赖。
    - 提供多层上下文管理能力，应对长对话场景的预算控制与压缩。

    与子类的分工
    ------------
    - 基类提供"骨架"：`generate_reply`（@final 不可覆写）、`build`、`bind`、`send`/`receive`。
    - 子类（如 ReActAgent）覆写"钩子"：
      * `thinking`：自定义 LLM 推理逻辑（多数情况下复用基类）。
      * `act`：覆写动作执行（ReActAgent 通过 action_input 解析执行 SQL 等）。
      * `read_memories` / `write_memories`：自定义记忆读写策略。
      * `prepare_act_param` / `_a_init_reply_message`：注入自定义参数与初始化逻辑。
      * `correctness_check` / `review` / `verify`：自定义校验与审查逻辑。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)  # 允许任意类型字段（Pydantic 配置）

    agent_context: Optional[AgentContext] = Field(None, description="Agent context")  # Agent 运行上下文
    actions: List[Action] = Field(default_factory=list)  # Agent 拥有的动作列表
    resource: Optional[Resource] = Field(None, description="Resource")  # Agent 绑定的资源（数据库、知识库等）
    llm_config: Optional[LLMConfig] = None  # LLM 配置（模型、策略、客户端等）
    bind_prompt: Optional[PromptTemplate] = None  # 绑定的提示词模板（系统提示词来源之一）
    run_mode: Optional[AgentRunMode] = Field(default=None, description="Run mode")  # 运行模式（单次 / 循环）
    max_retry_count: int = 3  # 最大重试次数（ReAct 循环上限）
    max_timeout: int = 600  # 最大超时时间（秒），超过则终止循环
    llm_client: Optional[AIWrapper] = None  # LLM 客户端包装器（在 build 中初始化）
    # 确认当前Agent是否需要进行流式输出
    stream_out: bool = True
    # 确认当前Agent是否需要进行参考资源展示
    show_reference: bool = False

    # Multi-layer context management (initialized via enable_context_management())
    # 多层上下文管理器，通过 init_context_management() 初始化；用于预算控制与压缩
    _context_manager: Optional[ContextManager] = None

    executor: Executor = Field(
        default_factory=lambda: ThreadPoolExecutor(max_workers=1),  # 单线程池，避免并发问题
        description="Executor for running tasks",
    )

    def __init__(self, **kwargs):
        """创建一个新的 Agent 实例。

        通过显式调用两个父类的 __init__ 来初始化，避免多重继承带来的初始化冲突。
        - `Role.__init__`：初始化角色配置字段（name / role / profile 等）。
        - `Agent.__init__`：初始化通信协议相关字段。
        """
        Role.__init__(self, **kwargs)  # 初始化角色配置
        Agent.__init__(self)  # 初始化通信协议字段

    def init_context_management(
        self,
        config: Optional[ContextBudgetConfig] = None,
        model_name: Optional[str] = None,
        on_status_event: Optional[ContextStatusCallback] = None,
    ) -> None:
        """初始化多层上下文管理。

        必须在 Agent 完成全部配置（llm_client 已设置等）之后调用。

        Args:
            config: 预算配置。若为 None，则从 agent_context 派生。
            model_name: 模型名称，用于选择 tokenizer。
            on_status_event: 异步回调，携带上下文状态字典；调用方（如 SSE 层）可用于推送实时更新。
        """
        if config is None:  # 未提供配置时从 agent_context 派生
            ctx = self.agent_context
            if ctx is None:
                config = ContextBudgetConfig()  # 使用默认配置
            else:
                config = ContextBudgetConfig(
                    max_context_tokens=ctx.max_context_tokens,  # 最大上下文 token 数
                    warning_threshold=ctx.context_warning_threshold,  # 告警阈值
                    error_threshold=ctx.context_error_threshold,  # 错误阈值
                )
        llm_client = self.llm_client  # 获取 LLM 客户端（用于 tokenizer）
        # 通过 object.__setattr__ 绕过 Pydantic 对私有字段的校验
        object.__setattr__(
            self,
            "_context_manager",
            ContextManager(
                config=config,  # 预算配置
                model_name=model_name,  # 模型名称
                llm_client=llm_client,  # LLM 客户端
                on_status_event=on_status_event,  # 状态回调
            ),
        )
        logger.info("Context management enabled for agent %s", self.name)  # 记录日志

    def check_available(self) -> None:
        """检查 Agent 是否可用。

        在 `build` 阶段调用，确保所有必要依赖已就绪。

        Raises:
            ValueError: 当 Agent 不可用时抛出（缺少上下文 / 资源 / 动作 / LLM 配置等）。
        """
        self.identity_check()  # 身份检查（name / role 等）
        # check run context
        # 检查运行上下文
        if self.agent_context is None:
            raise ValueError(
                f"{self.name}[{self.role}] Missing context in which agent is running!"
            )

        # action check
        # 动作检查：如果声明了动作，需确保对应资源存在
        if self.actions and len(self.actions) > 0:
            for action in self.actions:
                if action.resource_need and (
                    not self.resource
                    or not self.resource.get_resource_by_type(action.resource_need)
                ):
                    raise ValueError(
                        f"{self.name}[{self.role}] Missing resources"
                        f"[{action.resource_need}] required for runtime！"
                    )
        else:
            # 没有声明动作时，非人类 / 非团队 Agent 必须有动作模块
            if not self.is_human and not self.is_team:
                raise ValueError(
                    f"This agent {self.name}[{self.role}] is missing action modules."
                )
        # llm check
        # LLM 配置检查：非人类 Agent 必须有 LLM 配置与客户端
        if not self.is_human and (
            self.llm_config is None or self.llm_config.llm_client is None
        ):
            raise ValueError(
                f"{self.name}[{self.role}] Model configuration is missing or model "
                "service is unavailable！"
            )

    @property
    def not_null_agent_context(self) -> AgentContext:
        """获取非空的 Agent 上下文。

        Returns:
            AgentContext: 当前 Agent 的上下文。

        Raises:
            ValueError: 当上下文未初始化时抛出。
        """
        if not self.agent_context:
            raise ValueError("Agent context is not initialized！")
        return self.agent_context

    @property
    def not_null_llm_config(self) -> LLMConfig:
        """获取非空的 LLM 配置。

        Returns:
            LLMConfig: 当前 Agent 的 LLM 配置。

        Raises:
            ValueError: 当 LLM 配置未初始化时抛出。
        """
        if not self.llm_config:
            raise ValueError("LLM config is not initialized！")
        return self.llm_config

    @property
    def not_null_llm_client(self) -> LLMClient:
        """获取非空的 LLM 客户端。

        Returns:
            LLMClient: 当前 Agent 的 LLM 客户端。

        Raises:
            ValueError: 当 LLM 客户端未初始化时抛出。
        """
        llm_client = self.not_null_llm_config.llm_client  # 从 LLM 配置获取客户端
        if not llm_client:
            raise ValueError("LLM client is not initialized！")
        return llm_client

    async def blocking_func_to_async(
        self, func: Callable[..., Any], *args, **kwargs
    ) -> Any:
        """在执行器中运行潜在的阻塞函数。

        若 func 是协程函数则直接 await；否则通过 executor 异步执行，避免阻塞事件循环。

        Args:
            func: 待执行的函数（同步或异步）。
            *args: 函数位置参数。
            **kwargs: 函数关键字参数。

        Returns:
            Any: 函数执行结果。
        """
        if not asyncio.iscoroutinefunction(func):
            # 同步函数：通过线程池异步执行
            return await blocking_func_to_async(self.executor, func, *args, **kwargs)
        # 异步函数：直接 await
        return await func(*args, **kwargs)

    async def preload_resource(self) -> None:
        """在 Agent 初始化前预加载资源。

        调用 Resource.preload_resource 进行预热（如建立数据库连接、加载知识库索引等）。
        """
        if self.resource:
            await self.resource.preload_resource()  # 预加载资源

    async def build(self, is_retry_chat: bool = False) -> "ConversableAgent":
        """构建 Agent，完成资源预加载、可用性检查、记忆初始化与历史恢复。

        本方法是 Agent 进入运行状态的入口，由上层调度（如 ManagerAgent / AWEL 流程）调用。
        关键副作用：
        - 初始化 LLM 客户端（AIWrapper）。
        - 初始化 AgentMemory（包含 importance_scorer / insight_extractor）。
        - 从 gpts_messages 表恢复历史到 ShortTermMemory（见"恢复点 #1"）。

        Args:
            is_retry_chat: 是否为重试对话（影响后续消息加载策略）。

        Returns:
            ConversableAgent: 构建完成后的 Agent（self）。
        """
        # Preload resources
        # 预加载资源（数据库连接、知识库索引等）
        await self.preload_resource()
        # Check if agent is available
        # 检查 Agent 是否可用（上下文 / 动作 / 资源 / LLM 配置）
        self.check_available()
        _language = self.not_null_agent_context.language  # 从上下文获取语言设置
        if _language:
            self.language = _language  # 同步语言到 Agent

        # Initialize resource loader
        # 为每个动作初始化资源加载器
        for action in self.actions:
            action.init_resource(self.resource)

        # Initialize LLM Server
        # 初始化 LLM 客户端与记忆（仅非人类 Agent 需要）
        if not self.is_human:
            if not self.llm_config or not self.llm_config.llm_client:
                raise ValueError("LLM client is not initialized！")
            # 用 AIWrapper 包装原始 llm_client，提供额外的流式输出 / 重试等能力
            self.llm_client = AIWrapper(llm_client=self.llm_config.llm_client)
            # 解析真实 conv_id（去掉 retry 后缀等）
            real_conv_id, _ = parse_conv_id(self.not_null_agent_context.conv_id)
            # 构造记忆会话 ID（conv_id + role + name），用于隔离不同 Agent 的记忆
            memory_session = f"{real_conv_id}_{self.role}_{self.name}"
            # 初始化 AgentMemory（含 importance_scorer / insight_extractor）
            self.memory.initialize(
                self.name,
                self.llm_config.llm_client,
                importance_scorer=self.memory_importance_scorer,
                insight_extractor=self.memory_insight_extractor,
                session_id=memory_session,
            )
            # Clone the memory structure
            # 【上下文恢复点 #1：从 gpts_messages 表恢复历史到 ShortTermMemory】
            # agent 每次 build 时，从 gpts_messages 表读取该 conv_id 的历史消息，
            # 通过 recovering_memory 写入 ShortTermMemory._fragments。
            # 这样 ShortTermMemory 在 read_memories 时就能读到历史 ReAct step。
            # ⚠️ 注意：这是 agent 内部的历史恢复，和 agentic_data_api.py 的
            # historical_dialogues 注入是两个独立路径，内容会重叠。
            # 克隆记忆结构（避免污染原始 memory 实例）
            self.memory = self.memory.structure_clone()
            # 从 gpts_messages 表读取该 conv_id 下本 role 的历史消息
            action_outputs = await self.memory.gpts_memory.get_agent_history_memory(
                real_conv_id, self.role
            )
            # 将历史消息恢复到 ShortTermMemory._fragments
            await self.recovering_memory(action_outputs)
        return self  # 返回构建完成的 Agent

    def bind(self, target: Any) -> "ConversableAgent":
        """链式绑定各类资源到 Agent。

        支持的绑定类型（按 isinstance 分发）：
        - `LLMConfig`：绑定 LLM 配置。
        - `GptsMemory`：**不支持**，抛出异常（请使用 AgentMemory）。
        - `AgentContext`：绑定运行上下文。
        - `Resource`：绑定资源（数据库、知识库等）。
        - `AgentMemory`：绑定记忆。
        - `ProfileConfig`：绑定角色配置。
        - `SkillBase`（含 FileBasedSkill 转换）：绑定技能，并采用其 prompt 模板。
        - `Action` 类或实例（含列表）：追加到动作列表。
        - `PromptTemplate`：绑定提示词模板。

        Args:
            target: 待绑定的对象。

        Returns:
            ConversableAgent: self（支持链式调用 `.bind(a).bind(b)`）。
        """
        # Support binding Skill instances so agents can receive skills via .bind(skill)
        # Allow binding of FileBasedSkill (Claude-style) by converting it to a
        # core Skill instance. This lets callers pass either a core Skill or a
        # file-based skill parser result.
        # 尝试导入 FileBasedSkill（Claude 风格的技能定义）
        try:
            from dbgpt.agent.claude_skill import FileBasedSkill
        except Exception:
            FileBasedSkill = None  # type: ignore  # 导入失败时置空

        # If a FileBasedSkill instance was provided, try to convert it into
        # a core Skill so downstream code can treat skills uniformly.
        # 若传入 FileBasedSkill，尝试转换为 core Skill 实例，统一后续处理
        if FileBasedSkill is not None and isinstance(target, FileBasedSkill):
            try:
                from dbgpt.agent.skill.base import Skill, SkillMetadata, SkillType

                meta = target.metadata  # 获取技能元数据
                skill_type_val = SkillType.Custom  # 默认技能类型
                if getattr(meta, "skill_type", None):
                    try:
                        skill_type_val = SkillType(meta.skill_type)  # 尝试解析技能类型
                    except Exception:
                        skill_type_val = SkillType.Custom  # 解析失败时回退到 Custom

                # 构造 core SkillMetadata
                core_meta = SkillMetadata(
                    name=meta.name,
                    description=meta.description,
                    version=getattr(meta, "version", "1.0.0") or "1.0.0",
                    author=getattr(meta, "author", None),
                    skill_type=skill_type_val,
                    tags=getattr(meta, "tags", []) or [],
                )

                # 优先尝试 get_prompt()，其次尝试 instructions 属性
                prompt_template = None
                if hasattr(target, "get_prompt"):
                    try:
                        prompt_template = target.get_prompt()
                    except Exception:
                        pass  # 忽略异常，后续回退
                if prompt_template is None and hasattr(target, "instructions"):
                    prompt_template = PromptTemplate.from_template(target.instructions)

                # 构造 core Skill 实例
                skill_obj = Skill(
                    metadata=core_meta,
                    prompt_template=prompt_template,
                    required_tools=getattr(meta, "required_tools", []) or [],
                    required_knowledge=getattr(meta, "required_knowledge", []) or [],
                    config=getattr(meta, "config", {}) or {},
                )

                # replace target with the constructed core Skill instance
                # 用构造的 core Skill 替换原 target
                target = skill_obj
            except Exception:
                # if conversion fails, continue and let subsequent checks handle it
                # 转换失败时忽略，交由后续 isinstance 检查处理
                pass

        try:
            # local import to avoid circular imports at module import time
            # 局部导入，避免模块导入时循环依赖
            from dbgpt.agent.skill.base import SkillBase

            is_skill = isinstance(target, SkillBase)
        except Exception:
            is_skill = False  # 判断失败时视为非技能
        if isinstance(target, LLMConfig):
            self.llm_config = target  # 绑定 LLM 配置
        elif isinstance(target, GptsMemory):
            raise ValueError("GptsMemory is not supported!Please Use Agent Memory")  # 不支持直接绑定 GptsMemory
        elif isinstance(target, AgentContext):
            self.agent_context = target  # 绑定运行上下文
        elif isinstance(target, Resource):
            self.resource = target  # 绑定资源
        elif isinstance(target, AgentMemory):
            self.memory = target  # 绑定记忆
        elif isinstance(target, ProfileConfig):
            self.profile = target  # 绑定角色配置
        elif is_skill:
            # Bind skill to agent and adopt skill's prompt template as bind_prompt
            # so the skill's instructions become the agent's system prompt.
            # 绑定技能：将技能的 prompt 模板作为 bind_prompt（系统提示词）
            self._skill = target
            try:
                prompt_template = getattr(target, "prompt_template", None)
                if prompt_template is not None:
                    self.bind_prompt = cast(Optional[PromptTemplate], prompt_template)
            except Exception:
                pass  # 忽略异常
        elif isinstance(target, type) and issubclass(target, Action):
            self.actions.append(target())  # Action 类：实例化后追加
        elif isinstance(target, Action):
            self.actions.append(target)  # Action 实例：直接追加
        elif isinstance(target, list) and all(
            [isinstance(item, type) and issubclass(item, Action) for item in target]
        ):
            for action in target:
                self.actions.append(action())  # Action 类列表：逐个实例化追加
        elif isinstance(target, list) and all(
            [isinstance(item, Action) for item in target]
        ):
            self.actions.extend(target)  # Action 实例列表：直接扩展
        elif isinstance(target, PromptTemplate):
            self.bind_prompt = target  # 绑定提示词模板

        return self  # 返回 self，支持链式调用

    async def send(
        self,
        message: AgentMessage,
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
        silent: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
    ) -> None:
        """向目标 Agent 发送消息。

        实际调用 `recipient.receive`，将消息传递给接收方。
        整个过程在 `root_tracer` 的 span 中执行，便于链路追踪。

        Args:
            message: 待发送的 Agent 消息。
            recipient: 接收方 Agent。
            reviewer: 审查 Agent（可选）。
            request_reply: 是否要求接收方回复（True 则触发接收方 generate_reply）。
            is_recovery: 是否为恢复模式（历史消息重放时不触发新回复）。
            silent: 是否静默（不打印日志）。
            is_retry_chat: 是否为重试对话。
            last_speaker_name: 最后一个发言者的名字（用于多 Agent 协作时定位上下文）。
            rely_messages: 依赖的历史消息列表（手动重试时加载的依赖消息）。
            historical_dialogues: 全量历史对话（来自 conversation service）。
        """
        with root_tracer.start_span(
            "agent.send",
            metadata={
                "sender": self.name,  # 发送者名称
                "recipient": recipient.name,  # 接收者名称
                "reviewer": reviewer.name if reviewer else None,  # 审查者名称
                "agent_message": json.dumps(message.to_dict(), ensure_ascii=False),  # 消息内容
                "request_reply": request_reply,  # 是否要求回复
                "is_recovery": is_recovery,  # 是否恢复模式
                "conv_uid": self.not_null_agent_context.conv_id,  # 会话 ID
            },
        ):
            # 调用接收方的 receive 方法
            await recipient.receive(
                message=message,
                sender=self,
                reviewer=reviewer,
                request_reply=request_reply,
                is_recovery=is_recovery,
                silent=silent,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
                historical_dialogues=historical_dialogues,
                rely_messages=rely_messages,
            )

    async def receive(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> None:
        """接收来自其他 Agent 的消息。

        流程：
        1. 调用 `_a_process_received_message` 处理消息（持久化到 gpts_memory + 打印）。
        2. 若 `request_reply` 为 True 且非人类 Agent，则调用 `generate_reply` 生成回复。
        3. 若生成了回复，则通过 `self.send` 发回给发送者。

        Args:
            message: 接收到的消息。
            sender: 发送方 Agent。
            reviewer: 审查 Agent（可选）。
            request_reply: 是否需要回复。
            silent: 是否静默。
            is_recovery: 是否恢复模式。
            is_retry_chat: 是否重试对话。
            last_speaker_name: 最后一个发言者名字。
            historical_dialogues: 全量历史对话。
            rely_messages: 依赖的历史消息。
        """
        with root_tracer.start_span(
            "agent.receive",
            metadata={
                "sender": sender.name,  # 发送者名称
                "recipient": self.name,  # 接收者（自己）名称
                "reviewer": reviewer.name if reviewer else None,  # 审查者名称
                "agent_message": json.dumps(message.to_dict(), ensure_ascii=False),  # 消息内容
                "request_reply": request_reply,  # 是否要求回复
                "silent": silent,  # 是否静默
                "is_recovery": is_recovery,  # 是否恢复模式
                "conv_uid": self.not_null_agent_context.conv_id,  # 会话 ID
                "is_human": self.is_human,  # 是否人类 Agent
            },
        ):
            # 处理接收到的消息（持久化 + 打印）
            await self._a_process_received_message(message, sender)
            # 若不需要回复或 request_reply 为 None，则直接返回
            if request_reply is False or request_reply is None:
                return

            # 非人类 Agent 才生成回复
            if not self.is_human:
                # 根据发送者是否为人类，传递不同参数
                if isinstance(sender, ConversableAgent) and sender.is_human:
                    # 发送者为人类：传递 last_speaker_name
                    reply = await self.generate_reply(
                        received_message=message,
                        sender=sender,
                        reviewer=reviewer,
                        is_retry_chat=is_retry_chat,
                        last_speaker_name=last_speaker_name,
                        historical_dialogues=historical_dialogues,
                        rely_messages=rely_messages,
                    )
                else:
                    # 发送者为 Agent：不传递 last_speaker_name
                    reply = await self.generate_reply(
                        received_message=message,
                        sender=sender,
                        reviewer=reviewer,
                        is_retry_chat=is_retry_chat,
                        historical_dialogues=historical_dialogues,
                        rely_messages=rely_messages,
                    )

                # 若生成了回复，则发回给发送者
                if reply is not None:
                    await self.send(reply, sender)

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """为 act 方法准备额外参数。

        钩子方法，子类可覆写以注入自定义参数（如历史对话、依赖消息等）。
        默认返回空字典。

        Args:
            received_message: 接收到的消息。
            sender: 发送方 Agent。
            rely_messages: 依赖的历史消息。
            **kwargs: 其他关键字参数。

        Returns:
            Dict[str, Any]: 传递给 act 方法的额外参数。
        """
        return {}  # 默认无额外参数

    @final
    async def generate_reply(
        self,
        received_message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> AgentMessage:
        """生成回复（核心执行循环，被 @final 修饰不可覆写）。

        本方法是 ReAct 执行循环的骨架，编排以下步骤（每轮重试都会执行）：
        1. **thinking**：调用 LLM 推理，生成回复内容。
        2. **review**：审查回复内容是否合法。
        3. **act**：执行动作（如 SQL 执行、代码运行等），返回 ActionOutput。
        4. **verify**：验证执行结果是否正确。
        5. 若验证失败且可重试，则写入记忆并进入下一轮重试。
        6. 全部完成后调用 `adjust_final_message` 进行最终调整。

        关键特性：
        - 最多重试 `max_retry_count` 次（默认 3 次）。
        - 超过 `max_timeout` 秒后终止。
        - 支持 LLM 上下文溢出后的反应式压缩（Layer 4）。
        - 支持流式输出（通过 `stream_callback`）。

        Args:
            received_message: 接收到的消息（用户问题或上游 Agent 输出）。
            sender: 发送方 Agent。
            reviewer: 审查 Agent（可选）。
            rely_messages: 依赖的历史消息（手动重试时加载）。
            historical_dialogues: 全量历史对话（来自 conversation service）。
            is_retry_chat: 是否为重试对话。
            last_speaker_name: 最后一个发言者名字。
            **kwargs: 其他参数（如 stream_callback）。

        Returns:
            AgentMessage: 生成的回复消息。
        """
        # 弹出流式回调（避免传递给下游方法）
        stream_callback = kwargs.pop("stream_callback", None)

        async def _emit_stream(event_type: str, payload: Dict[str, Any]) -> None:
            """发射流式事件给 stream_callback。

            Args:
                event_type: 事件类型（如 thinking_chunk / thinking / act）。
                payload: 事件负载。
            """
            if not stream_callback:  # 无回调时直接返回
                return
            try:
                if asyncio.iscoroutinefunction(stream_callback):
                    # 异步回调：直接 await
                    await stream_callback(event_type, payload)
                    return
                # 同步回调：调用并检查是否返回协程
                result = stream_callback(event_type, payload)
                if asyncio.iscoroutine(result):
                    await result  # 若返回协程则 await
            except Exception:
                logger.exception("stream_callback error")  # 记录异常但不中断主流程

        logger.info(
            f"generate agent reply!sender={sender}, rely_messages_len={rely_messages}"
        )
        # 启动根 span，记录整个 generate_reply 的链路追踪
        root_span = root_tracer.start_span(
            "agent.generate_reply",
            metadata={
                "sender": sender.name,  # 发送者名称
                "recipient": self.name,  # 接收者（自己）名称
                "reviewer": reviewer.name if reviewer else None,  # 审查者名称
                "received_message": json.dumps(received_message.to_dict()),  # 接收消息
                "conv_uid": self.not_null_agent_context.conv_id,  # 会话 ID
                "rely_messages": (
                    [msg.to_dict() for msg in rely_messages] if rely_messages else None
                ),  # 依赖消息
            },
        )
        reply_message = None  # 初始化回复消息

        try:
            with root_tracer.start_span(
                "agent.generate_reply._init_reply_message",
            ) as span:
                # initialize reply message
                # 初始化回复消息：优先调用异步版本 _a_init_reply_message
                a_reply_message: Optional[
                    AgentMessage
                ] = await self._a_init_reply_message(received_message=received_message)
                if a_reply_message:
                    reply_message = a_reply_message  # 异步版本返回非空时使用
                else:
                    # 异步版本返回 None 时，调用同步版本 _init_reply_message
                    reply_message = self._init_reply_message(
                        received_message=received_message
                    )
                span.metadata["reply_message"] = reply_message.to_dict()  # 记录到 span

            fail_reason = None  # 失败原因（重试时使用）
            current_retry_counter = 0  # 当前重试计数
            start_time = time.time()  # 记录开始时间
            is_success = True  # 是否成功
            observation = received_message.content or ""  # 初始 observation 为接收消息内容
            # 防循环：记录 (action, action_input) 出现次数，连续相同动作达阈值时注入干预
            action_history: Dict[Tuple[str, str], int] = {}
            _LOOP_WARN_THRESHOLD = 3
            # 是否已真正执行过数据查询（sql_query/code_interpreter/shell_interpreter）：
            # 用于防止模型只看了 schema 就过早 terminate
            _executed_data_query = False
            # 重试循环：最多 max_retry_count 次
            while current_retry_counter < self.max_retry_count:
                if current_retry_counter > 0:
                    # 非首轮：重新初始化 retry_message，并写入失败原因
                    a_reply_message: Optional[
                        AgentMessage
                    ] = await self._a_init_reply_message(
                        received_message=received_message,
                        rely_messages=rely_messages,
                    )
                    if a_reply_message:
                        retry_message = a_reply_message  # 异步版本
                    else:
                        retry_message = self._init_reply_message(
                            received_message=received_message,
                            rely_messages=rely_messages,
                        )

                    retry_message.rounds = reply_message.rounds + 1  # 递增轮次

                    retry_message.content = fail_reason or observation  # 内容为失败原因或 observation
                    retry_message.current_goal = received_message.current_goal  # 同步当前目标

                    # The current message is a self-optimized message that needs to be
                    # recorded.
                    # It is temporarily set to be initiated by the originating end to
                    # facilitate the organization of historical memory context.
                    # 当前消息是自优化消息，需要记录。
                    # 临时设置为由发起方发起，便于组织历史记忆上下文。
                    await sender.send(
                        retry_message, self, reviewer, request_reply=False
                    )
                    reply_message.rounds = retry_message.rounds + 1  # 更新 reply_message 轮次

                # In manual retry mode, load all messages of the last speaker as dependent messages # noqa
                # 手动重试模式下，加载最后一个发言者的所有消息作为依赖消息
                logger.info(
                    f"Depends on the number of historical messages:{len(rely_messages) if rely_messages else 0}！"  # noqa
                )
                # 加载思考消息（上下文合并核心，见 _load_thinking_messages）
                thinking_messages, resource_info = await self._load_thinking_messages(
                    received_message=received_message,
                    sender=sender,
                    observation=observation,
                    rely_messages=rely_messages,
                    historical_dialogues=historical_dialogues,
                    context=reply_message.get_dict_context(),
                    is_retry_chat=is_retry_chat,
                    current_retry_counter=current_retry_counter,
                )
                with root_tracer.start_span(
                    "agent.generate_reply.thinking",
                    metadata={
                        "thinking_messages": json.dumps(
                            [msg.to_dict() for msg in thinking_messages],
                            ensure_ascii=False,
                        )  # 记录思考消息
                    },
                ) as span:
                    # 1.Think about how to do things
                    # 1.思考阶段：调用 LLM 推理
                    async def _llm_stream_callback(payload: Dict[str, Any]) -> None:
                        """LLM 流式回调，转发为 thinking_chunk 事件。"""
                        await _emit_stream(
                            "thinking_chunk",
                            {
                                "round": current_retry_counter + 1,  # 当前轮次
                                "delta_text": payload.get("delta_text", ""),  # 增量文本
                                "delta_thinking": payload.get("delta_thinking", ""),  # 增量思考
                            },
                        )

                    try:
                        # 调用 thinking 方法进行 LLM 推理
                        llm_reply, model_name = await self.thinking(
                            thinking_messages,
                            sender,
                            stream_callback=_llm_stream_callback,
                        )
                    except LLMChatError as e:
                        # Layer 4: reactive compaction on context_too_long
                        # 第 4 层：上下文过长时的反应式压缩
                        _ctx_mgr: Optional[ContextManager] = getattr(
                            self, "_context_manager", None
                        )
                        err_str = str(e).lower()
                        # 检测是否为上下文过长错误
                        if _ctx_mgr and (
                            "context_too_long" in err_str
                            or "context_length_exceeded" in err_str
                            or "maximum context length" in err_str
                        ):
                            logger.warning(
                                "LLM context overflow detected — applying "
                                "reactive compaction (Layer 4)"
                            )
                            # 反应式压缩：截断 / 摘要历史消息
                            thinking_messages = await _ctx_mgr.reactive_compact(
                                thinking_messages
                            )
                            # 压缩后重新调用 thinking
                            llm_reply, model_name = await self.thinking(
                                thinking_messages,
                                sender,
                                stream_callback=_llm_stream_callback,
                            )
                        else:
                            raise  # 非上下文过长错误则重新抛出
                    reply_message.model_name = model_name  # 记录模型名称
                    reply_message.content = llm_reply  # 记录 LLM 回复
                    reply_message.resource_info = resource_info  # 记录资源信息
                    span.metadata["llm_reply"] = llm_reply  # 记录到 span
                    span.metadata["model_name"] = model_name
                    await _emit_stream(
                        "thinking",
                        {
                            "round": current_retry_counter + 1,  # 当前轮次
                            "llm_reply": llm_reply,  # LLM 回复
                            "model_name": model_name,  # 模型名称
                        },
                    )

                with root_tracer.start_span(
                    "agent.generate_reply.review",
                    metadata={"llm_reply": llm_reply, "censored": self.name},
                ) as span:
                    # 2.Review whether what is being done is legal
                    # 2.审查阶段：检查 LLM 回复是否合法
                    approve, comments = await self.review(llm_reply, self)
                    reply_message.review_info = AgentReviewInfo(
                        approve=approve,  # 是否通过
                        comments=comments,  # 审查意见
                    )
                    span.metadata["approve"] = approve
                    span.metadata["comments"] = comments

                # 准备 act 方法的额外参数
                act_extent_param = self.prepare_act_param(
                    received_message=received_message,
                    sender=sender,
                    rely_messages=rely_messages,
                    historical_dialogues=historical_dialogues,
                )
                with root_tracer.start_span(
                    "agent.generate_reply.act",
                    metadata={
                        "llm_reply": llm_reply,  # LLM 回复
                        "sender": sender.name,  # 发送者
                        "reviewer": reviewer.name if reviewer else None,  # 审查者
                        "act_extent_param": act_extent_param,  # 额外参数
                    },
                ) as span:
                    # 3.Act based on the results of your thinking
                    # 3.执行阶段：运行动作
                    act_out: ActionOutput = await self.act(
                        message=reply_message,
                        sender=sender,
                        reviewer=reviewer,
                        is_retry_chat=is_retry_chat,
                        last_speaker_name=last_speaker_name,
                        **act_extent_param,
                    )
                    if act_out:
                        reply_message.action_report = act_out  # 记录动作报告
                    span.metadata["action_report"] = (
                        act_out.to_dict() if act_out else None
                    )
                    await _emit_stream(
                        "act",
                        {
                            "round": current_retry_counter + 1,  # 当前轮次
                            "action_output": act_out.to_dict() if act_out else None,  # 动作输出
                        },
                    )

                with root_tracer.start_span(
                    "agent.generate_reply.verify",
                    metadata={
                        "llm_reply": llm_reply,  # LLM 回复
                        "sender": sender.name,  # 发送者
                        "reviewer": reviewer.name if reviewer else None,  # 审查者
                    },
                ) as span:
                    # 4.Reply information verification
                    # 4.验证阶段：检查执行结果
                    check_pass, reason = await self.verify(
                        reply_message, sender, reviewer
                    )
                    is_success = check_pass  # 更新成功标志
                    span.metadata["check_pass"] = check_pass
                    span.metadata["reason"] = reason

                question: str = received_message.content or ""  # 原始问题
                ai_message: str = llm_reply or ""  # AI 回复
                # 5.Optimize wrong answers myself
                # 5.自我优化：验证失败时记录失败记忆
                if not check_pass:
                    if not act_out.have_retry:
                        logger.warning("No retry available!")  # 无可用重试则退出
                        break
                    fail_reason = reason  # 记录失败原因
                    observation = fail_reason  # 更新 observation 为失败原因
                    # 写入失败记忆
                    await self.write_memories(
                        question=question,
                        ai_message=ai_message,
                        action_output=act_out,
                        check_pass=check_pass,
                        check_fail_reason=fail_reason,
                        current_retry_counter=current_retry_counter,
                    )
                else:
                    # Successful reply
                    # 成功回复：更新 observation 为动作观察结果
                    observation = act_out.observations
                    # 写入成功记忆
                    await self.write_memories(
                        question=question,
                        ai_message=ai_message,
                        action_output=act_out,
                        check_pass=check_pass,
                        current_retry_counter=current_retry_counter,
                    )
                    # 记录是否执行过数据查询（用于防过早 terminate）
                    _act_name = getattr(act_out, "action", None) or ""
                    if _act_name in ("sql_query", "code_interpreter", "shell_interpreter"):
                        _executed_data_query = True
                    # 非循环模式或动作终止时退出
                    if self.run_mode != AgentRunMode.LOOP or act_out.terminate:
                        # 防过早终止：模型常只看了表结构（get_table_schema）就 terminate，
                        # 或遇"表不存在"等错误就放弃。若轮次很少、从未真正查询数据、且
                        # 终止内容不像"反问澄清"也不像有数据的实质回答，则注入提示继续，
                        # 而不是直接结束。
                        _terminate_text = (act_out.content or "")[:300]
                        _is_clarify = any(
                            k in _terminate_text
                            for k in (
                                "请提供", "请确认", "请告知", "请给出", "请指定",
                                "please provide", "please confirm", "请说明",
                                "请告诉我具体的", "请输入",
                            )
                        )
                        # 模型终止内容像是在描述"报错/要修正重查/失败"（而非给出答案）
                        _is_err_retry = any(
                            k in _terminate_text
                            for k in (
                                "重新查询", "重新", "修正", "有误", "报错", "执行失败",
                                "表不存在", "failed", "error", "exception",
                                "OperationalError", "TypeError", "语法错误", "类型",
                            )
                        )
                        # 模型终止内容像是"探索式规划"（说要做但还没做，如"让我先查询/先看看"），
                        # 而非真正给出答案 —— 这类也是过早终止。
                        # 特别地，模型常"宣布要生成 HTML 报告/重新执行查询"后就结束，
                        # 但没有真正调用 code_interpreter / html_interpreter。
                        _is_planning = any(
                            k in _terminate_text
                            for k in (
                                "让我先", "我先", "首先", "需要了解", "需要先", "先看看",
                                "先查询", "先查", "查询一下", "了解一下", "探索", "让我来",
                                "我先看看", "先探索",
                                # 宣布要做但没执行
                                "让我生成", "我会生成", "现在生成", "生成HTML", "生成html",
                                "生成报告", "生成一份", "开始生成", "生成最终",
                                "让我重新", "我重新", "重新执行", "让我修正", "让我修复",
                                "让我再用", "让我换", "让我尝试",
                                "现在查询", "现在去", "接下来", "下一步", "让我继续",
                                "我现在要", "接下来我", "继续查询", "继续分析",
                                "现在使用", "已生成", "渲染报告", "HTML 报告", "html报告",
                                "报告已生成", "报告生成", "让我渲染", "进行渲染",
                            )
                        )
                        _rounds = current_retry_counter + 1
                        if (
                            not _is_clarify
                            and (
                                (not _executed_data_query and (_rounds <= 3 or _is_planning))
                                or (_rounds <= 6 and (_is_err_retry or _is_planning))
                            )
                        ):
                            logger.warning(
                                f"Agent {self.name} premature terminate at round "
                                f"{_rounds} (no-query={not _executed_data_query}, "
                                f"err={_is_err_retry}, plan={_is_planning}): "
                                f"{_terminate_text[:60]}"
                            )
                            observation = (
                                "⚠️ 你的回答还缺少实际数据分析就结束了。"
                                "请先通过 sql_query / code_interpreter 获取并分析真实数据，"
                                "修正遇到的报错后重试，最后用 terminate 返回完整总结 "
                                '{"result": "..."}。'
                            )
                        else:
                            logger.debug(f"Agent {self.name} reply success!{reply_message}")
                            break
                # 防循环：检测连续重复的 (action, action_input)，达阈值时注入干预消息
                try:
                    _act_name = getattr(act_out, "action", None) or ""
                    _act_input = getattr(act_out, "action_input", None) or ""
                    if _act_name:
                        _key = (str(_act_name), str(_act_input))
                        action_history[_key] = action_history.get(_key, 0) + 1
                        if action_history[_key] >= _LOOP_WARN_THRESHOLD:
                            _warn = (
                                "⚠️ 你已连续 %d 次执行相同操作（%s）且未获得有用结果。"
                                "请立即停止该操作，换用其他表/查询方式，"
                                "或直接基于已有信息给出最终答案。"
                            ) % (action_history[_key], _act_name)
                            observation = f"{_warn}\n{observation}"
                            logger.warning(_warn)
                            action_history[_key] = 0  # 重置，避免警告无限叠加
                except Exception:
                    logger.debug("loop detection skipped", exc_info=True)
                # 检查超时
                time_cost = time.time() - start_time
                if time_cost > self.max_timeout:
                    logger.warning(
                        f"Agent {self.name} run time out!{time_cost} > "
                        f"{self.max_timeout}"
                    )
                    break  # 超时则退出

                # Continue to run the next round
                # 继续下一轮
                current_retry_counter += 1
                # Send error messages and issue new problem-solving instructions
                # 发送错误消息并发出新的解题指令
                if current_retry_counter < self.max_retry_count:
                    await self.send(
                        reply_message, sender, reviewer, request_reply=False
                    )

            reply_message.success = is_success  # 设置最终成功标志
            # 6.final message adjustment
            # 6.最终消息调整
            await self.adjust_final_message(is_success, reply_message)
            return reply_message  # 返回回复消息

        except Exception as e:
            logger.exception("Generate reply exception!")  # 记录异常
            err_message = AgentMessage(content=str(e))  # 构造错误消息
            err_message.success = False  # 标记为失败
            return err_message
        finally:
            # 最终记录 reply_message 到 span，并结束 span
            if reply_message:
                root_span.metadata["reply_message"] = reply_message.to_dict()
            root_span.end()

    async def thinking(
        self,
        messages: List[AgentMessage],
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
        stream_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """思考阶段：调用 LLM 推理。

        钩子方法，子类可覆写以自定义 LLM 推理逻辑。
        本基类实现：自动重试 3 次以减少限流 / 网络波动导致的中断。

        Args:
            messages: 待推理的消息列表（已组装好的 thinking_messages）。
            sender: 发送方 Agent（用于传递 sender.role 给 LLM）。
            prompt: 额外的系统提示词（可选，拼接到消息列表前）。
            stream_callback: 流式回调（接收增量文本）。

        Returns:
            Tuple[Optional[str], Optional[str]]: (LLM 回复内容, 模型名称)。

        Raises:
            ValueError: 当 LLM 推理失败时抛出。
        """
        last_model = None  # 上次使用的模型（用于排除失败模型）
        last_err = None  # 上次错误信息
        retry_count = 0  # 重试计数
        # 将 AgentMessage 列表转换为 LLM 消息格式
        llm_messages = [message.to_llm_message() for message in messages]
        # LLM inference automatically retries 3 times to reduce interruption
        # probability caused by speed limit and network stability
        # LLM 推理自动重试 3 次，减少限流 / 网络稳定性导致的中断
        while retry_count < 3:
            # 选择 LLM 模型（排除上次失败的模型）
            llm_model = await self._a_select_llm_model(last_model)
            try:
                if prompt:
                    # 若提供了 prompt，则构造 system 消息拼接到列表前
                    llm_messages = _new_system_message(prompt) + llm_messages

                if not self.llm_client:
                    raise ValueError("LLM client is not initialized!")  # LLM 客户端未初始化
                # 调用 LLM 客户端创建回复
                response = await self.llm_client.create(
                    context=llm_messages[-1].pop("context", None),  # 从最后一条消息弹出 context
                    messages=llm_messages,  # 消息列表
                    llm_model=llm_model,  # 模型名称
                    max_new_tokens=self.not_null_agent_context.max_new_tokens,  # 最大生成 token 数
                    temperature=self.not_null_agent_context.temperature,  # 温度
                    verbose=self.not_null_agent_context.verbose,  # 是否打印详细日志
                    memory=self.memory.gpts_memory,  # 记忆（用于持久化）
                    conv_id=self.not_null_agent_context.conv_id,  # 会话 ID
                    sender=sender.role if sender else "?",  # 发送者角色
                    stream_out=self.stream_out,  # 是否流式输出
                    stream_callback=stream_callback,  # 流式回调
                )
                return response, llm_model  # 返回回复与模型名称
            except LLMChatError as e:
                logger.error(f"model:{llm_model} generate Failed!{str(e)}")  # 记录错误
                retry_count += 1  # 递增重试计数
                last_model = llm_model  # 记录失败模型（下次排除）
                last_err = str(e)  # 记录错误信息
                await asyncio.sleep(10)  # 等待 10 秒后重试

        # 3 次重试后仍失败
        if last_err:
            raise ValueError(last_err)  # 抛出最后一次错误
        else:
            raise ValueError("LLM model inference failed!")  # 通用失败信息

    async def review(self, message: Optional[str], censored: Agent) -> Tuple[bool, Any]:
        """审查阶段：检查 LLM 回复是否合法。

        钩子方法，子类可覆写以实现自定义审查逻辑（如敏感词检测、格式校验等）。
        默认实现：始终通过。

        Args:
            message: 待审查的消息内容（LLM 回复）。
            censored: 被审查的 Agent（通常是 self）。

        Returns:
            Tuple[bool, Any]: (是否通过, 审查意见)。
        """
        return True, None  # 默认通过，无意见

    async def act(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """执行阶段：依次执行所有 Action，返回 ActionOutput。

        多个 Action 串联执行（责任链模式），前一个 Action 的输出作为后一个的输入。
        钩子方法，子类（如 ReActAgent）可覆写以实现自定义执行逻辑。

        Args:
            message: 待执行的消息（含 LLM 回复内容）。
            sender: 发送方 Agent。
            reviewer: 审查 Agent。
            is_retry_chat: 是否为重试对话。
            last_speaker_name: 最后一个发言者名字。
            **kwargs: 额外参数（来自 prepare_act_param）。

        Returns:
            ActionOutput: 最后一个 Action 的输出。

        Raises:
            ValueError: 当消息内容为空或无 Action 返回值时抛出。
        """
        last_out: Optional[ActionOutput] = None  # 上一个 Action 的输出
        # 遍历所有 Action，依次执行
        for i, action in enumerate(self.actions):
            if not message:
                raise ValueError("The message content is empty!")  # 消息内容为空

            with root_tracer.start_span(
                "agent.act.run",
                metadata={
                    "message": message,  # 消息
                    "sender": sender.name if sender else None,  # 发送者
                    "recipient": self.name,  # 接收者
                    "reviewer": reviewer.name if reviewer else None,  # 审查者
                    "rely_action_out": last_out.to_dict() if last_out else None,  # 上一个输出
                    "conv_uid": self.not_null_agent_context.conv_id,  # 会话 ID
                    "action_index": i,  # 当前 Action 索引
                    "total_action": len(self.actions),  # Action 总数
                },
            ) as span:
                ai_message = message.content if message.content else ""  # 获取 AI 回复内容
                # 解析动作（根据 AI 回复内容选择实际执行的 Action）
                real_action = action.parse_action(
                    ai_message, default_action=action, **kwargs
                )
                if real_action is None:
                    continue  # 解析为空则跳过

                # 执行 Action
                last_out = await real_action.run(
                    ai_message=message.content if message.content else "",  # AI 回复
                    resource=None,  # 资源（已通过 action.init_resource 绑定）
                    rely_action_out=last_out,  # 依赖的上一个输出
                    **kwargs,
                )
                span.metadata["action_out"] = last_out.to_dict() if last_out else None  # 记录输出
        if not last_out:
            raise ValueError("Action should return value！")  # 无输出则抛出异常
        return last_out  # 返回最后一个 Action 的输出

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """正确性检查：验证 Agent 输出是否正确。

        钩子方法，子类可覆写以实现自定义校验逻辑（如 SQL 结果校验、代码运行结果校验等）。
        默认实现：始终通过。

        Args:
            message: 待校验的消息（含 LLM 回复与动作报告）。

        Returns:
            Tuple[bool, Optional[str]]: (是否通过, 失败原因)。
        """
        return True, None  # 默认通过，无失败原因

    async def verify(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:
        """验证阶段：检查执行结果是否正确。

        三步检查：
        1. 检查审查结果（review_info.approve）。
        2. 检查动作执行结果（is_exe_success / content 是否为空）。
        3. 调用 `correctness_check` 进行 Agent 输出正确性检查（子类可覆写）。

        Args:
            message: 待验证的消息（含审查信息与动作报告）。
            sender: 发送方 Agent。
            reviewer: 审查 Agent。
            **kwargs: 额外参数。

        Returns:
            Tuple[bool, Optional[str]]: (是否通过, 失败原因)。
        """
        # Check approval results
        # 1.检查审查结果：若未通过则返回失败
        if message.review_info and not message.review_info.approve:
            return False, message.review_info.comments

        # Check action run results
        # 2.检查动作执行结果
        action_output: Optional[ActionOutput] = message.action_report
        if action_output:
            if not action_output.is_exe_success:
                return False, action_output.content  # 执行失败：返回失败内容
            elif not action_output.content or len(action_output.content.strip()) < 1:
                # 执行成功但内容为空
                return (
                    False,
                    "The current execution result is empty. Please rethink the "
                    "question and background and generate a new answer.. ",
                )

        # agent output correctness check
        # 3.Agent 输出正确性检查（子类可覆写）
        return await self.correctness_check(message)

    async def initiate_chat(
        self,
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        message: Optional[str] = None,
        request_reply: bool = True,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        message_rounds: int = 0,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        **context,
    ):
        """向另一个 Agent 发起对话。

        这是 Agent 之间通信的入口方法，通常由 ManagerAgent 或上层调度调用。
        构造 AgentMessage 后通过 `self.send` 发送给接收方。

        Args:
            recipient: 接收方 Agent。
            reviewer: 审查 Agent。
            message: 消息内容（字符串）。
            request_reply: 是否要求回复。
            is_retry_chat: 是否为重试对话。
            last_speaker_name: 最后一个发言者名字。
            message_rounds: 消息轮次。
            historical_dialogues: 全量历史对话。
            rely_messages: 依赖的历史消息。
            **context: 额外上下文（作为消息的 context 字段）。
        """
        # 构造 Agent 消息
        agent_message = AgentMessage(
            content=message,  # 消息内容
            current_goal=message,  # 当前目标（与内容相同）
            rounds=message_rounds,  # 轮次
            context=context,  # 上下文
        )
        with root_tracer.start_span(
            "agent.initiate_chat",
            span_type=SpanType.AGENT,  # span 类型为 AGENT
            metadata={
                "sender": self.name,  # 发送者
                "recipient": recipient.name,  # 接收者
                "reviewer": reviewer.name if reviewer else None,  # 审查者
                "agent_message": json.dumps(
                    agent_message.to_dict(), ensure_ascii=False
                ),  # 消息内容
                "conv_uid": self.not_null_agent_context.conv_id,  # 会话 ID
            },
        ):
            # 发送消息给接收方
            await self.send(
                agent_message,
                recipient,
                reviewer,
                historical_dialogues=historical_dialogues,
                rely_messages=rely_messages,
                request_reply=request_reply,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
            )

    async def adjust_final_message(
        self,
        is_success: bool,
        reply_message: AgentMessage,
    ):
        """最终消息调整：在 reply 返回前进行最后的调整。

        钩子方法，子类可覆写以修改最终消息（如添加总结、修正格式等）。
        默认实现：原样返回。

        Args:
            is_success: 是否成功。
            reply_message: 待调整的回复消息。

        Returns:
            Tuple[bool, AgentMessage]: (是否成功, 调整后的消息)。
        """
        return is_success, reply_message  # 默认原样返回

    #######################################################################
    # Private Function Begin
    # 私有方法区域开始
    #######################################################################

    def _init_actions(self, actions: List[Type[Action]]):
        """初始化动作列表。

        将 Action 类列表转换为实例列表，并设置语言。

        Args:
            actions: Action 类列表。
        """
        self.actions = []  # 清空动作列表
        for idx, action in enumerate(actions):
            if issubclass(action, Action):
                # 实例化 Action 并设置语言
                self.actions.append(action(language=self.language))

    async def _a_append_message(
        self, message: AgentMessage, role, sender: Agent
    ) -> bool:
        """将消息追加到 GptsMemory（持久化）。

        将 AgentMessage 转换为 GptsMessage 并写入 gpts_memory，
        供后续 build() 恢复与历史查询使用。

        Args:
            message: 待持久化的 Agent 消息。
            role: 消息角色（如 HUMAN / AI）。
            sender: 发送方 Agent。

        Returns:
            bool: 是否成功（True）。
        """
        # 构造持久化的 GptsMessage
        gpts_message: GptsMessage = GptsMessage(
            conv_id=self.not_null_agent_context.conv_id,  # 会话 ID
            sender=sender.role,  # 发送者角色
            receiver=self.role,  # 接收者角色（自己）
            role=role,  # 消息角色
            rounds=message.rounds,  # 轮次
            is_success=message.success,  # 是否成功
            app_code=(
                sender.not_null_agent_context.gpts_app_code
                if isinstance(sender, ConversableAgent)
                else None
            ),  # 应用编码
            app_name=(
                sender.not_null_agent_context.gpts_app_name
                if isinstance(sender, ConversableAgent)
                else None
            ),  # 应用名称
            current_goal=message.current_goal,  # 当前目标
            content=message.content if message.content else "",  # 消息内容
            context=(
                json.dumps(message.context, ensure_ascii=False)
                if message.context
                else None
            ),  # 上下文（JSON）
            review_info=(
                json.dumps(message.review_info.to_dict(), ensure_ascii=False)
                if message.review_info
                else None
            ),  # 审查信息（JSON）
            action_report=(
                json.dumps(message.action_report.to_dict(), ensure_ascii=False)
                if message.action_report
                else None
            ),  # 动作报告（JSON）
            model_name=message.model_name,  # 模型名称
            resource_info=(
                json.dumps(message.resource_info) if message.resource_info else None
            ),  # 资源信息（JSON）
        )

        with root_tracer.start_span(
            "agent.save_message_to_memory",
            metadata={
                "gpts_message": gpts_message.to_dict(),  # 持久化的消息
                "conv_uid": self.not_null_agent_context.conv_id,  # 会话 ID
            },
        ):
            # 写入 gpts_memory（持久化到数据库）
            await self.memory.gpts_memory.append_message(
                self.not_null_agent_context.conv_id, gpts_message
            )
            return True  # 持久化成功

    def _print_received_message(self, message: AgentMessage, sender: Agent):
        """打印接收到的消息（终端彩色输出）。

        用于在终端显示 Agent 之间通信的消息内容、审查信息与动作报告。

        Args:
            message: 接收到的消息。
            sender: 发送方 Agent。
        """
        # print the message received
        # 打印分隔线
        print("\n", "-" * 80, flush=True, sep="")
        _print_name = self.name if self.name else self.role  # 接收者显示名
        print(
            colored(
                sender.name if sender.name else sender.role,  # 发送者显示名（黄色）
                "yellow",
            ),
            "(to",
            f"{_print_name})-[{message.model_name or ''}]:\n",  # 模型名称
            flush=True,
        )

        content = json.dumps(message.content, ensure_ascii=False)  # 消息内容
        if content is not None:
            print(content, flush=True)  # 打印内容

        review_info = message.review_info  # 审查信息
        if review_info:
            name = sender.name if sender.name else sender.role  # 发送者名
            pass_msg = "Pass" if review_info.approve else "Reject"  # 通过 / 拒绝
            review_msg = f"{pass_msg}({review_info.comments})"  # 审查意见
            approve_print = f">>>>>>>>{name} Review info: \n{review_msg}"
            print(colored(approve_print, "green"), flush=True)  # 绿色打印

        action_report = message.action_report  # 动作报告
        if action_report:
            name = sender.name if sender.name else sender.role  # 发送者名
            action_msg = (
                "execution succeeded"
                if action_report.is_exe_success
                else "execution failed"
            )  # 执行成功 / 失败
            action_report_msg = f"{action_msg},\n{action_report.content}"  # 报告内容
            action_print = f">>>>>>>>{name} Action report: \n{action_report_msg}"
            print(colored(action_print, "blue"), flush=True)  # 蓝色打印

        print("\n", "-" * 80, flush=True, sep="")  # 打印分隔线

    async def _a_process_received_message(self, message: AgentMessage, sender: Agent):
        """处理接收到的消息：持久化 + 打印。

        在 `receive` 方法中调用，是消息处理的入口。

        Args:
            message: 接收到的消息。
            sender: 发送方 Agent。

        Raises:
            ValueError: 当消息无法持久化时抛出。
        """
        # 持久化消息到 gpts_memory
        valid = await self._a_append_message(message, None, sender)
        if not valid:
            raise ValueError(
                "Received message can't be converted into a valid ChatCompletion"
                " message. Either content or function_call must be provided."
            )

        # 打印接收到的消息
        self._print_received_message(message, sender)

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """加载资源提示词。

        根据当前问题（observation）从绑定的 Resource 获取提示词与参考资源。
        用于在 `_load_thinking_messages` 中构造 system_prompt 和 user_prompt。

        Args:
            question: 当前问题（observation）。
            is_retry_chat: 是否为重试对话。

        Returns:
            Tuple[Optional[str], Optional[Dict]]: (资源提示词, 参考资源)。
            若无资源则返回 (None, None)。
        """
        if self.resource:
            # 调用资源的 get_prompt 方法，获取提示词与参考资源
            resource_prompt, resource_reference = await self.resource.get_prompt(
                lang=self.language, question=question
            )
            return resource_prompt, resource_reference  # 返回提示词与参考资源
        return None, None  # 无资源时返回 None

    async def generate_resource_variables(
        self, resource_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成资源变量。

        构造用于提示词模板渲染的变量字典，包含：
        - resource_prompt：资源提示词
        - out_schema：第一个 Action 的输出 schema
        - now_time：当前时间

        Args:
            resource_prompt: 资源提示词（可选）。

        Returns:
            Dict[str, Any]: 资源变量字典。
        """
        out_schema: Optional[str] = ""  # 输出 schema
        if self.actions and len(self.actions) > 0:
            out_schema = self.actions[0].ai_out_schema  # 取第一个 Action 的输出 schema
        if not resource_prompt:
            resource_prompt = ""  # 空提示词处理
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 当前时间
        return {
            "resource_prompt": resource_prompt,  # 资源提示词
            "out_schema": out_schema,  # 输出 schema
            "now_time": now_time,  # 当前时间
        }

    def _excluded_models(
        self,
        all_models: List[str],
        order_llms: Optional[List[str]] = None,
        excluded_models: Optional[List[str]] = None,
    ):
        """根据优先级与排除列表筛选可用模型。

        用于 `_a_select_llm_model` 中选择下一个可用的 LLM 模型。

        Args:
            all_models: 所有可用模型列表。
            order_llms: 优先级顺序（按顺序选择，优先级高的优先）。
            excluded_models: 需排除的模型列表（如上次失败的模型）。

        Returns:
            List[str]: 可用模型列表。
        """
        if not order_llms:
            order_llms = []  # 无优先级时置空
        if not excluded_models:
            excluded_models = []  # 无排除项时置空
        can_uses = []  # 可用模型列表
        if order_llms and len(order_llms) > 0:
            # 有优先级：按优先级顺序筛选
            for llm_name in order_llms:
                if llm_name in all_models and (
                    not excluded_models or llm_name not in excluded_models
                ):
                    can_uses.append(llm_name)  # 加入可用列表
        else:
            # 无优先级：遍历所有模型筛选
            for llm_name in all_models:
                if not excluded_models or llm_name not in excluded_models:
                    can_uses.append(llm_name)  # 加入可用列表

        return can_uses  # 返回可用模型列表

    def convert_to_agent_message(
        self,
        gpts_messages: List[GptsMessage],
        is_rery_chat: bool = False,
    ) -> Optional[List[AgentMessage]]:
        """将 GptsMessage 列表转换为 AgentMessage 列表。

        用于历史消息恢复时的格式转换。

        Args:
            gpts_messages: 持久化的 GptsMessage 列表。
            is_rery_chat: 是否为重试对话（参数名拼写有误，保留原样）。

        Returns:
            Optional[List[AgentMessage]]: 转换后的 AgentMessage 列表；输入为空时返回 None。
        """
        oai_messages: List[AgentMessage] = []  # 转换后的消息列表
        # Based on the current agent, all messages received are user, and all messages
        # sent are assistant.
        # 基于当前 Agent，接收到的消息为 user，发送的消息为 assistant
        if not gpts_messages:
            return None  # 输入为空时返回 None
        for item in gpts_messages:
            # Message conversion, priority is given to converting execution results,
            # and only model output results will be used if not.
            # 消息转换：优先转换执行结果，无执行结果时使用模型输出
            content = item.content  # 消息内容
            oai_messages.append(
                AgentMessage(
                    content=content,  # 内容
                    context=(
                        json.loads(item.context) if item.context is not None else None
                    ),  # 上下文（JSON 反序列化）
                    action_report=(
                        ActionOutput.from_dict(json.loads(item.action_report))
                        if item.action_report
                        else None
                    ),  # 动作报告（反序列化）
                    name=item.sender,  # 发送者名
                    rounds=item.rounds,  # 轮次
                    model_name=item.model_name,  # 模型名称
                    success=item.is_success,  # 是否成功
                )
            )
        return oai_messages  # 返回转换后的列表

    async def _a_select_llm_model(
        self, excluded_models: Optional[List[str]] = None
    ) -> str:
        """异步选择 LLM 模型。

        根据策略（Priority / Default）与排除列表选择下一个可用的 LLM 模型。
        若无可用模型则回退到 "deepseek-chat"。

        Args:
            excluded_models: 需排除的模型列表（如上次失败的模型）。

        Returns:
            str: 选中的模型名称。

        Raises:
            ValueError: 当获取模型列表失败时抛出。
        """
        logger.info(f"_a_select_llm_model:{excluded_models}")  # 记录排除列表
        try:
            # 获取 LLM 客户端支持的所有模型
            all_models = await self.not_null_llm_client.models()
            all_model_names = [item.model for item in all_models]  # 提取模型名称列表
            # TODO Currently only two strategies, priority and default, are implemented.
            # TODO 当前仅实现 Priority 与 Default 两种策略
            if self.not_null_llm_config.llm_strategy == LLMStrategyType.Priority:
                # Priority 策略：按优先级顺序选择
                priority: List[str] = []
                strategy_context = self.not_null_llm_config.strategy_context
                if strategy_context is not None:
                    priority = json.loads(strategy_context)  # type: ignore  # 解析优先级列表
                can_uses = self._excluded_models(
                    all_model_names, priority, excluded_models
                )
            else:
                # Default 策略：无优先级，直接筛选
                can_uses = self._excluded_models(all_model_names, None, excluded_models)
            if can_uses and len(can_uses) > 0:
                return can_uses[0]  # 返回第一个可用模型
            else:
                return "deepseek-chat"  # 无可用模型时回退
        except Exception as e:
            logger.error(f"{self.role} get next llm failed!{str(e)}")  # 记录错误
            raise ValueError(f"Failed to allocate model service,{str(e)}!")  # 抛出异常

    def _init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        """从接收到的消息初始化回复消息（同步版本）。

        当 `_a_init_reply_message` 返回 None 时调用。
        构造一个新的 AgentMessage，轮次 +1，内容与目标继承自接收消息。

        Args:
            received_message: 接收到的消息。
            rely_messages: 依赖的历史消息（本基类实现未使用）。

        Returns:
            AgentMessage: 初始化的回复消息。
        """
        return AgentMessage(
            content=received_message.content,  # 继承内容
            current_goal=received_message.current_goal,  # 继承当前目标
            context=received_message.context,  # 继承上下文
            rounds=received_message.rounds + 1,  # 轮次 +1
        )

    async def _a_init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> Optional[AgentMessage]:
        """从接收到的消息初始化回复消息（异步版本）。

        钩子方法，子类可覆写以实现自定义初始化逻辑。
        若返回非 None，则不会调用同步版本 `_init_reply_message`。

        Args:
            received_message: 接收到的消息。
            rely_messages: 依赖的历史消息。

        Returns:
            Optional[AgentMessage]: 初始化的回复消息；返回 None 时使用同步版本。
        """
        return None  # 默认返回 None，交由同步版本处理

    def _convert_to_ai_message(
        self,
        gpts_messages: List[GptsMessage],
        is_rery_chat: bool = False,
    ) -> List[AgentMessage]:
        """将 GptsMessage 列表转换为 AI 消息列表（带角色判断）。

        与 `convert_to_agent_message` 不同，本方法会根据 sender/receiver 推断角色：
        - 接收者为当前 Agent → HUMAN（用户）
        - 发送者为当前 Agent → AI（助手）
        - 其他 → 跳过

        Args:
            gpts_messages: 持久化的 GptsMessage 列表。
            is_rery_chat: 是否为重试对话（参数名拼写有误，保留原样）。
                重试模式下使用 action_out.content（不论是否成功）；
                非重试模式下仅在执行成功时使用 action_out.content。

        Returns:
            List[AgentMessage]: 转换后的消息列表。
        """
        oai_messages: List[AgentMessage] = []  # 转换后的消息列表
        # Based on the current agent, all messages received are user, and all messages
        # sent are assistant.
        # 基于当前 Agent，接收到的消息为 user，发送的消息为 assistant
        for item in gpts_messages:
            if item.role:
                role = item.role  # 已有角色则直接使用
            else:
                # 无角色时根据 sender/receiver 推断
                if item.receiver == self.role:
                    role = ModelMessageRoleType.HUMAN  # 接收者为当前 Agent → HUMAN
                elif item.sender == self.role:
                    role = ModelMessageRoleType.AI  # 发送者为当前 Agent → AI
                else:
                    continue  # 其他情况跳过

            # Message conversion, priority is given to converting execution results,
            # and only model output results will be used if not.
            # 消息转换：优先转换执行结果，无执行结果时使用模型输出
            content = item.content  # 默认使用原始内容
            if item.action_report:
                action_out = ActionOutput.from_dict(json.loads(item.action_report))
                if is_rery_chat:
                    # 重试模式：不论执行是否成功，都使用 action_out.content
                    if action_out is not None and action_out.content:
                        content = action_out.content
                else:
                    # 非重试模式：仅执行成功时使用 action_out.content
                    if (
                        action_out is not None
                        and action_out.is_exe_success
                        and action_out.content is not None
                    ):
                        content = action_out.content
            oai_messages.append(
                AgentMessage(
                    content=content,  # 内容
                    role=role,  # 角色
                    context=(
                        json.loads(item.context) if item.context is not None else None
                    ),  # 上下文（JSON 反序列化）
                )
            )
        return oai_messages  # 返回转换后的列表

    async def build_system_prompt(
        self,
        question: Optional[str] = None,
        most_recent_memories: Optional[str] = None,
        resource_vars: Optional[Dict] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
    ):
        """构造系统提示词。

        优先使用 `bind_prompt`（绑定的提示词模板）渲染系统提示词：
        - 支持 f-string 与 jinja2 两种模板格式。
        - 使用 _SafeDict 容忍缺失的占位符（返回空字符串）。

        若 `bind_prompt` 渲染失败或不存在，则回退到 `build_prompt`（由 Role 提供）。

        Args:
            question: 当前问题。
            most_recent_memories: 最近的记忆（字符串形式）。
            resource_vars: 资源变量字典。
            context: 上下文字典。
            is_retry_chat: 是否为重试对话。

        Returns:
            str: 构造好的系统提示词。
        """
        system_prompt = None  # 初始化系统提示词
        if self.bind_prompt:
            # 定义 _SafeDict：访问缺失的 key 时返回空字符串，避免 KeyError
            class _SafeDict(dict):
                def __missing__(self, key):
                    return ""

            prompt_param = {}  # 提示词参数
            if resource_vars:
                prompt_param.update(resource_vars)  # 合并资源变量
            if context:
                prompt_param.update(context)  # 合并上下文
            if self.bind_prompt.template_format == "f-string":
                # f-string 格式：直接 format
                system_prompt = self.bind_prompt.format(**prompt_param)
            elif self.bind_prompt.template_format == "jinja2":
                # jinja2 格式：使用 Template 渲染
                system_prompt = Template(self.bind_prompt.template).render(prompt_param)
            else:
                logger.warning("Bind prompt template not exsit or  format not support!")  # 不支持的格式
        if not system_prompt:
            # bind_prompt 渲染失败或不存在：回退到 build_prompt
            param: Dict = context if context else {}
            system_prompt = await self.build_prompt(
                question=question,
                is_system=True,  # 标记为系统提示词
                most_recent_memories=most_recent_memories,
                resource_vars=resource_vars,
                is_retry_chat=is_retry_chat,
                **param,
            )
        return system_prompt  # 返回系统提示词

    async def _load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: Agent,
        observation: Optional[str] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
        current_retry_counter: Optional[int] = None,
    ) -> Tuple[List[AgentMessage], Optional[Dict]]:
        """加载思考消息（上下文合并核心方法）。

        本方法是上下文加载链路的最后一步，负责组装最终发给 LLM 的消息列表。
        被 `generate_reply` 在每轮重试时调用。

        上下文加载链路：
            build（恢复点 #1：从 gpts_messages 恢复到 ShortTermMemory）
              ↓
            generate_reply（调用 _load_thinking_messages）
              ↓
            _load_thinking_messages（上下文合并核心）
              ├─ read_memories（上下文读取点 #2：从 ShortTermMemory 读取历史）
              ├─ build_system_prompt（构造消息 #1：system_prompt）
              ├─ historical_dialogues（消息 #2：全量会话历史）
              ├─ memory_list（消息 #3：最近 ReAct step）
              ├─ manage_context（多层上下文管理：压缩）
              └─ build_prompt（消息 #4：user_prompt）

        Args:
            received_message: 接收到的消息。
            sender: 发送方 Agent。
            observation: 当前观察（默认为 received_message.content）。
            rely_messages: 依赖的历史消息。
            historical_dialogues: 全量历史对话。
            context: 上下文字典。
            is_retry_chat: 是否为重试对话。
            current_retry_counter: 当前重试计数。

        Returns:
            Tuple[List[AgentMessage], Optional[Dict]]: (思考消息列表, 资源参考信息)。
        """
        # ─────────────────────────────────────────────────────────────
        # 【上下文合并核心：最终 agent_messages 的组装顺序】
        # 最终发给 LLM 的消息列表顺序：
        #   1. system_prompt          （含 database_context / knowledge_context 等）
        #   2. historical_dialogues   （来自 agentic_data_api.py 全量加载的会话历史）
        #   3. memory_list            （来自 ShortTermMemory.read，最近 10 个 ReAct step）
        #   4. user_prompt            （当前轮 Observation，含向量库检索的表结构）
        # ⚠️ historical_dialogues 和 memory_list 内容重叠：
        #    两者都来自 gpts_messages 表，只是读取路径不同
        # ─────────────────────────────────────────────────────────────
        question = received_message.content  # 提取问题内容
        observation = observation or question  # observation 默认为问题内容
        if not question:
            raise ValueError("The received message content is empty!")  # 问题为空则抛出
        most_recent_memories = ""  # 最近的记忆（字符串形式）
        memory_list = []  # 记忆列表（AgentMessage 形式）
        # 【上下文读取点 #2：从 ShortTermMemory 读取历史 ReAct step】
        # ReActAgent.read_memories 把 ShortTermMemory._fragments 解析成
        # List[AgentMessage]（Question/Thought/Action/Observation 格式）
        # 这些 fragment 是 build() 时从 gpts_messages 表恢复的（见 L219-229）
        # 从 ShortTermMemory 读取历史记忆
        memories = await self.read_memories(observation)
        if isinstance(memories, list):
            memory_list = memories  # 列表形式：存入 memory_list
        else:
            most_recent_memories = memories  # 字符串形式：存入 most_recent_memories
        has_memories = True if memories else False  # 是否有记忆
        reply_message_str = ""  # 依赖消息拼接字符串
        if context is None:
            context = {}  # 初始化上下文
        # Inject task progress summary so the LLM always knows what has been done
        # regardless of how many memory fragments have been evicted from the buffer.
        # 注入任务进度摘要，让 LLM 始终知道已完成的工作，
        # 不论多少记忆片段已从缓冲区被淘汰
        task_progress = self.task_progress_summary
        if task_progress:
            context["task_progress"] = task_progress  # 注入任务进度
        if rely_messages:
            copied_rely_messages = [m.copy() for m in rely_messages]  # 复制依赖消息（避免污染原消息）
            # When directly relying on historical messages, use the execution result
            # content as a dependency
            # 当直接依赖历史消息时，使用执行结果内容作为依赖
            for message in copied_rely_messages:
                action_report: Optional[ActionOutput] = message.action_report
                if action_report:
                    # TODO: Modify in-place, need to be optimized
                    # TODO: 原地修改，待优化
                    message.content = action_report.content  # 用执行结果内容替换消息内容
                if message.name != self.role:
                    # TODO, use name
                    # TODO, 使用 name
                    # Rely messages are not from the current agent
                    # 依赖消息不是来自当前 Agent
                    if message.role == ModelMessageRoleType.HUMAN:
                        reply_message_str += f"Question: {message.content}\n"  # 拼接问题
                    elif message.role == ModelMessageRoleType.AI:
                        reply_message_str += f"Observation: {message.content}\n"  # 拼接观察
        if reply_message_str:
            most_recent_memories += "\n" + reply_message_str  # 合并依赖消息到记忆
        try:
            # Load the resource prompt according to the current observation
            # 根据当前 observation 加载资源提示词
            resource_prompt_str, resource_references = await self.load_resource(
                observation, is_retry_chat=is_retry_chat
            )
        except Exception as e:
            logger.exception(f"Load resource error！{str(e)}")  # 记录异常
            raise ValueError(f"Load resource error！{str(e)}")  # 抛出异常

        # 生成资源变量（含 resource_prompt / out_schema / now_time）
        resource_vars = await self.generate_resource_variables(resource_prompt_str)

        # 构造系统提示词（消息 #1）
        system_prompt = await self.build_system_prompt(
            question=question,
            most_recent_memories=most_recent_memories,
            resource_vars=resource_vars,
            context=context,
            is_retry_chat=is_retry_chat,
        )
        # 构造用户提示词（消息 #4）
        user_prompt = await self.build_prompt(
            question=question,
            is_system=False,  # 标记为非系统提示词
            most_recent_memories=most_recent_memories,
            resource_vars=resource_vars,
            **context,
        )

        agent_messages = []  # 最终的消息列表
        # ─────────────────────────────────────────────────────────────
        # 【消息 #1：system_prompt】
        # 含 database_context / knowledge_context / skills_context 等
        # ─────────────────────────────────────────────────────────────
        if system_prompt:
            agent_messages.append(
                AgentMessage(
                    content=system_prompt,  # 系统提示词内容
                    role=ModelMessageRoleType.SYSTEM,  # 角色为 SYSTEM
                )
            )
        # ─────────────────────────────────────────────────────────────
        # 【消息 #2：historical_dialogues】
        # 来自 agentic_data_api.py 全量加载的会话历史（conversation service）
        # 按偶数位=user、奇数位=AI 交替插入
        # ⚠️ 与下面的 memory_list 内容重叠（都来自 gpts_messages 表）
        # ─────────────────────────────────────────────────────────────
        if historical_dialogues:
            for i, message in enumerate(historical_dialogues):
                # 尊重已设置的 role（如 API 层从 view 提取的 AI 回复）；仅在未设置时
                # 按奇偶位置兜底，避免 view 缺 final_content 时历史不交替导致误标。
                if message.role is None:
                    message.role = (
                        ModelMessageRoleType.HUMAN
                        if i % 2 == 0
                        else ModelMessageRoleType.AI
                    )
                agent_messages.append(message)

        # ─────────────────────────────────────────────────────────────
        # 【消息 #3：memory_list】
        # 来自 ShortTermMemory.read，最近 10 个 ReAct step（Question/Thought/Action/Observation）
        # 这些 fragment 是 build() 时从 gpts_messages 表恢复的
        # ⚠️ 与上面的 historical_dialogues 内容重叠
        # ─────────────────────────────────────────────────────────────
        if memory_list:
            agent_messages.extend(memory_list)  # 扩展记忆列表到消息列表

        # Multi-layer context management: compress if budget exceeded
        # 多层上下文管理：超过预算时压缩
        ctx_mgr: Optional[ContextManager] = getattr(self, "_context_manager", None)
        if ctx_mgr is not None:
            # 调用 ContextManager 进行预算控制与压缩
            agent_messages = await ctx_mgr.manage_context(
                messages=agent_messages,
                current_round=current_retry_counter or 0,  # 当前轮次
                task_progress=task_progress,  # 任务进度
            )

        # Current user input information
        # 当前用户输入信息（消息 #4）
        if not user_prompt and (not memory_list or not current_retry_counter):
            # The user prompt is empty, and the current retry count is 0 or the memory
            # is empty
            # user_prompt 为空，且当前重试计数为 0 或记忆为空
            user_prompt = f"Observation: {observation}"  # 使用 observation 作为 user_prompt
        if user_prompt:
            agent_messages.append(
                AgentMessage(
                    content=user_prompt,  # 用户提示词内容
                    role=ModelMessageRoleType.HUMAN,  # 角色为 HUMAN
                )
            )
        return agent_messages, resource_references  # 返回消息列表与资源参考


def _new_system_message(content):
    """构造系统消息字典。

    模块级辅助函数，用于在 `thinking` 方法中拼接额外的系统提示词。

    Args:
        content: 系统消息内容。

    Returns:
        List[Dict]: 包含单条系统消息的列表。
    """
    return [{"content": content, "role": ModelMessageRoleType.SYSTEM}]


def _is_list_of_type(lst: List[Any], type_cls: type) -> bool:
    """判断列表中所有元素是否均为指定类型。

    模块级辅助函数。

    Args:
        lst: 待判断的列表。
        type_cls: 目标类型。

    Returns:
        bool: 所有元素均为指定类型时返回 True。
    """
    return all(isinstance(item, type_cls) for item in lst)
