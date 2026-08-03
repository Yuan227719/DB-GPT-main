"""agentic_data_api.py —— DB-GPT v0.8.1 ReAct Agent 核心 API 入口。

本文件是 DB-GPT 智能体数据 API 的总入口，注册了以下 FastAPI 路由：

技能管理类:
    - GET    /v1/skills/list            列出全部技能
    - GET    /v1/skills/detail          查看某个技能详情（文件树 + SKILL.md）
    - POST   /v1/skills/upload           上传技能压缩包/单文件
    - POST   /v1/skills/import_github   从 GitHub / skills.sh 导入技能

会话与共享类:
    - POST   /v1/chat/react-agent       ReAct Agent 主入口（SSE 流）
    - POST   /v1/chat/share              创建会话分享链接
    - GET    /v1/chat/share/{token}     公开访问分享会话（无需鉴权）
    - DELETE /v1/chat/share/{token}     撤销分享链接

文件下载类:
    - GET    /v1/agent/files/download    下载 agent 工具生成的产物文件
    - GET    /v1/agent/skills/download   将整个技能目录打包成 zip 下载

核心设计：
    1. ReAct Agent 通过 SSE（Server-Sent Events）流式返回思考、动作、观测结果，
       前端按 step.card / plan.update / context.status / final / done 等事件渲染。
    2. Agent 工具（@tool 装饰）在本文件内部闭包定义，捕获 react_state 字典
       在多轮对话间传递会话状态（已加载技能、生成图片、todo 列表等）。
    3. 上下文注入点 #1-#4 是关键钩子位置（向量库检索、AgentMemory、用户消息
       拼接、历史对话加载），由先前会话留下，禁止修改或删除。
    4. 工具执行结果通过 chunks 协议返回，前端按 output_type 分发渲染
       （text/markdown/code/json/table/chart/image/html）。

依赖关系：
    上游：dbgpt-app 的 FastAPI 主应用、dbgpt_app.openapi.api_view_model
    下游：dbgpt-core（agent/messaging/storage）、dbgpt-ext（datasource、sandbox）、
          dbgpt-serve（conversation/datasource/agent）、dbgpt-sandbox（shell 执行）
"""

# === 标准库导入 ===
import io  # 内存字节流（zip 打包下载使用）
import json  # JSON 序列化/反序列化
import logging  # 日志
import os  # 操作系统路径
import re  # 正则
import shutil  # 高级文件操作（拷贝、删除目录树）
import tempfile  # 临时目录
import uuid  # 唯一 ID
import zipfile  # zip 压缩/解压
from pathlib import Path, PurePosixPath, PureWindowsPath  # 跨平台路径处理
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional, Tuple  # 类型注解
from urllib.parse import urlparse  # URL 解析（GitHub 导入用）

# === 第三方框架导入 ===
from fastapi import APIRouter, Body, Depends, File, Query, Request, UploadFile  # FastAPI 路由与依赖注入
from fastapi.responses import StreamingResponse  # SSE / 流式响应

# === DB-GPT 内部包导入 ===
from dbgpt._private.config import Config  # 全局配置
from dbgpt._private.pydantic import BaseModel as _BaseModel  # 内部 pydantic 别名
from dbgpt.agent.core.context import ContextBudgetConfig  # 上下文预算配置
from dbgpt.agent.resource.tool.base import tool  # @tool 装饰器
from dbgpt.agent.skill.manage import get_skill_manager  # 技能管理器
from dbgpt.component import ComponentType  # 组件类型枚举
from dbgpt.configs.model_config import SKILLS_DIR, resolve_root_path  # 技能目录与根路径解析
from dbgpt.core import PromptTemplate  # Prompt 模板
from dbgpt.model.cluster import WorkerManagerFactory  # LLM Worker 工厂
from dbgpt_app.openapi.api_view_model import (  # 视图模型
    ConversationVo,
    Result,
)
from dbgpt_serve.datasource.manages import ConnectorManager  # 数据源连接器管理器
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers  # 鉴权依赖

# === 模块级对象 ===
router = APIRouter()  # 本文件的 APIRouter 实例，由上层 include
CFG = Config()  # 全局配置单例
logger = logging.getLogger(__name__)  # 本模块 logger

if TYPE_CHECKING:  # 仅类型检查时导入，避免运行时循环依赖
    from dbgpt.agent.core.memory.gpts import GptsMemory
    from dbgpt.agent.resource.connector.manager import ConnectorManager
    from dbgpt.agent.resource.tool.base import BaseTool

# 进程级缓存：conv_id -> GptsMemory，跨 HTTP 请求复用 Agent 记忆
REACT_AGENT_MEMORY_CACHE: Dict[str, "GptsMemory"] = {}

# 默认技能目录（来自全局配置）
DEFAULT_SKILLS_DIR = SKILLS_DIR
# 自动数据标记正则：捕获 ###KEY_START###...###KEY_END### 块并提取键值
AUTO_DATA_MARKER_PATTERN = re.compile(
    r"###([A-Z0-9_]+)_START###\s*(.*?)\s*###\1_END###", re.DOTALL
)


def _validate_upload_filename(filename: str) -> str:
    """校验上传文件名，防止路径穿越攻击。

    安全检查：
      - 拒绝空字节（NULL byte）注入
      - 拒绝绝对路径（POSIX 或 Windows 形式）
      - 拒绝多段路径（如 a/b）
      - 拒绝 `.` / `..` 这种特殊名称

    Args:
        filename: 待校验的原始文件名

    Returns:
        校验通过后的文件名（原样返回，仅做安全校验）

    Raises:
        ValueError: 文件名包含上述任一危险特征时抛出
    """
    # 空字节检查：某些客户端可能注入 \\x00 截断后缀
    if "\x00" in filename:
        raise ValueError("filename must not contain null bytes")

    # 同时按 POSIX 与 Windows 规则解析路径
    posix_path = PurePosixPath(filename)
    windows_path = PureWindowsPath(filename)
    # 任一形式为绝对路径，或路径含多段，或是 . / ..，均拒绝
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or len(posix_path.parts) != 1
        or len(windows_path.parts) != 1
        or filename in {"", ".", ".."}
    ):
        raise ValueError("filename must be a plain file name")
    return filename


async def _resolve_model_context_tokens(
    llm_client: Any, model_name: Optional[str]
) -> Optional[int]:
    """从运行时模型元数据解析模型的上下文窗口大小。

    通过 LLM 客户端调用 `get_model_metadata` 拉取模型的 context_length，
    用于动态规划上下文预算。失败时返回 None（调用方将走默认值）。

    Args:
        llm_client: 已初始化的 LLM 客户端
        model_name: 模型名称（如 gpt-4o、deepseek-chat 等）

    Returns:
        模型上下文 token 数（正整数），或 None 表示无法获取
    """
    if not llm_client or not model_name:
        return None

    try:
        # 拉取模型元数据，提取 context_length
        metadata = await llm_client.get_model_metadata(model_name)
        context_length = getattr(metadata, "context_length", None)
        if isinstance(context_length, int) and context_length > 0:
            return context_length
    except Exception:
        # 元数据获取失败不影响主流程，记录调试日志即可
        logger.debug(
            "Failed to resolve context window for model %s", model_name, exc_info=True
        )
    return None


async def _load_context_budget_config(
    llm_client: Any = None,
    model_name: Optional[str] = None,
) -> ContextBudgetConfig:
    """从应用 TOML 配置构建上下文预算配置对象。

    读取 `configs/*.toml` 中 `[service.web.agent_context]` 段下的字段，
    与默认 ContextBudgetConfig 合并，得到当前请求实际使用的预算：
      - max_context_tokens:           上下文总 token 上限
      - warning_threshold / error_threshold / critical_threshold: 各级阈值
      - reserved_tokens:               给系统 prompt 预留的 token 数
      - min_keep_recent_rounds:        至少保留多少轮近期对话
      - max_compact_failures:          压缩失败的最大容忍次数
      - max_observation_age_rounds:    观察结果最多保留多少轮
      - truncated_observation_max_chars: 截断后单条观察的最大字符数
      - min_keep_tokens:              压缩后至少保留的 token 数

    Args:
        llm_client: 可选，传入则尝试从模型元数据读取 context_length
        model_name: 可选，模型名

    Returns:
        ContextBudgetConfig 实例（解析失败时返回默认实例）
    """
    defaults = ContextBudgetConfig()  # 默认预算

    def _value(agent_context: Any, field_name: str, default: Any) -> Any:
        """从 agent_context 安全读取字段，缺失则返回 default。"""
        if agent_context is None:
            return default
        value = getattr(agent_context, field_name, default)
        return default if value is None else value

    try:
        # 解析 app_config -> service.web.agent_context 链
        app_config = CFG.SYSTEM_APP.config.configs.get("app_config")
        web_config = getattr(getattr(app_config, "service", None), "web", None)
        agent_context = getattr(web_config, "agent_context", None)
        max_context_tokens = _value(
            agent_context, "max_context_tokens", defaults.max_context_tokens
        )
        # 构造最终的预算配置对象
        return ContextBudgetConfig(
            max_context_tokens=max_context_tokens,
            warning_threshold=_value(
                agent_context, "warning_threshold", defaults.warning_threshold
            ),
            error_threshold=_value(
                agent_context, "error_threshold", defaults.error_threshold
            ),
            critical_threshold=_value(
                agent_context, "critical_threshold", defaults.critical_threshold
            ),
            reserved_tokens=_value(
                agent_context, "reserved_tokens", defaults.reserved_tokens
            ),
            min_keep_recent_rounds=_value(
                agent_context,
                "min_keep_recent_rounds",
                defaults.min_keep_recent_rounds,
            ),
            max_compact_failures=_value(
                agent_context,
                "max_compact_failures",
                defaults.max_compact_failures,
            ),
            max_observation_age_rounds=_value(
                agent_context,
                "max_observation_age_rounds",
                defaults.max_observation_age_rounds,
            ),
            truncated_observation_max_chars=(
                _value(
                    agent_context,
                    "truncated_observation_max_chars",
                    defaults.truncated_observation_max_chars,
                )
            ),
            min_keep_tokens=_value(
                agent_context,
                "min_keep_tokens",
                defaults.min_keep_tokens,
            ),
        )
    except Exception:
        # 任何解析异常都退回默认值，避免影响主流程
        logger.debug(
            "Failed to load agent context config; using defaults", exc_info=True
        )
        return defaults


def _extract_auto_data_markers(text: str) -> tuple[str, Dict[str, str]]:
    """从脚本输出文本中提取 `###KEY_START###...###KEY_END###` 标记块。

    技能脚本可以通过特殊标记把结构化数据（如计算结果、图表路径）回传给
    agent。本函数将所有匹配的标记块从原文本中剥离，并返回
    (清理后的文本, 提取出的键值字典)。

    Marker format:
        ###KEY_START###...###KEY_END###

    Args:
        text: 脚本输出的原始文本

    Returns:
        Tuple[清理后的文本, {KEY: VALUE}]
    """
    # 无内容或不含标记时直接返回
    if not text or "###" not in text:
        return text, {}

    extracted: Dict[str, str] = {}

    def _replace(match: re.Match) -> str:
        """将匹配到的标记块从原文本中删除，并把内容存入 extracted。"""
        key = match.group(1)
        value = match.group(2).strip()
        if value:
            extracted[key] = value
        return ""

    # 执行替换
    cleaned = AUTO_DATA_MARKER_PATTERN.sub(_replace, text)
    # 多余空行压缩成单个空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, extracted


def _parse_connector_ids(ext_info: Optional[Dict[str, Any]]) -> List[str]:
    """从前端 ext_info 中提取用户选中的 connector ID 列表。

    支持两种字段格式（向后兼容）：
      - `ext_info.connector_ids` —— ID 字符串列表（推荐）
      - `ext_info.connector_id`   —— 单个 ID 字符串（旧版兼容）

    Args:
        ext_info: 前端请求中携带的扩展信息字典

    Returns:
        connector_id 字符串列表，找不到时返回空列表
    """
    if not ext_info or not isinstance(ext_info, dict):
        return []
    # 优先读列表形式的 connector_ids
    raw_ids = ext_info.get("connector_ids")
    if isinstance(raw_ids, list):
        return [cid for cid in raw_ids if isinstance(cid, str) and cid]
    # 兼容旧版单 ID 字段
    legacy = ext_info.get("connector_id")
    if isinstance(legacy, str) and legacy:
        return [legacy]
    return []


def _select_connector_tools(
    connector_ids: List[str],
    connector_manager: Optional["ConnectorManager"],
) -> Tuple[List["BaseTool"], List[str]]:
    """将 connector_ids 解析为可直接注入 ToolPack 的扁平 BaseTool 列表。

    每个 connector 在内部是一个 MCPToolPack，包含多个 BaseTool
    （每个 MCP server tool 一个）。这里做扁平化处理，让外层 ToolPack
    能直接组合它们，避免嵌套 ResourcePack 时被当成单个 dict 项插入
    导致带前缀的工具名无法被外层 ToolPack 查到。

    Args:
        connector_ids: 用户在前端选中的 connector ID 列表
        connector_manager: ConnectorManager 实例（可为 None）

    Returns:
        (tools, missing_ids)
          - tools: 扁平的 BaseTool 列表（每个 BaseTool 是单个 MCP 工具，
                   其 server URL 已在闭包中捕获）
          - missing_ids: 无法解析的 ID 列表（如对话过程中被删除）
    """
    from dbgpt.agent.resource.tool.base import BaseTool

    tools: List["BaseTool"] = []
    missing_ids: List[str] = []
    # 没有管理器或没选中任何 connector 时直接返回空列表
    if connector_manager is None or not connector_ids:
        return tools, missing_ids
    for cid in connector_ids:
        pack = connector_manager.get_connector_tools(cid)
        if pack is None:
            # 该 connector 已不在运行（如对话中被删）
            missing_ids.append(cid)
            continue
        # 扁平化：从 pack.sub_resources 中取出 BaseTool 实例
        for sub_tool in pack.sub_resources:
            if isinstance(sub_tool, BaseTool):
                tools.append(sub_tool)
    return tools, missing_ids


async def _execute_skill_script_impl(
    skill_name: str, script_name: str, args: dict
) -> str:
    """执行技能中定义的内联脚本（实现函数）。

    通过 SkillManager.execute_script 调用技能声明的 inline script。
    供模块级 @tool 装饰的 execute_skill_script 复用。

    Args:
        skill_name: 技能名
        script_name: 技能内脚本的标识
        args: 传给脚本的参数

    Returns:
        脚本执行的字符串结果
    """
    skill_manager = get_skill_manager(CFG.SYSTEM_APP)
    result = await skill_manager.execute_script(skill_name, script_name, args)
    return result


# === 模块级 @tool 工具：可被 LLM Agent 直接调用 ===
# 这三个工具在模块级别注册，作为默认可用工具集的一部分。
# 注意：内部闭包版本的 execute_skill_script_file 在 _react_agent_stream 内
# 重新定义，提供更丰富的图片后处理 / react_state 同步能力。

@tool(
    description='执行技能中的脚本。参数: {"skill_name": "技能名称", '
    '"script_name": "脚本名称", "args": {参数}}'
)
async def execute_skill_script(skill_name: str, script_name: str, args: dict) -> str:
    """执行技能中声明的 inline 脚本（模块级工具版本）。

    仅供 LLM Agent 调用，实际逻辑委托给 `_execute_skill_script_impl`。
    """
    return await _execute_skill_script_impl(skill_name, script_name, args)


@tool(
    description="获取技能资源文件内容。"
    "根据路径读取技能中的参考文档、配置文件等非脚本资源。"
    '参数: {"skill_name": "技能名称", "resource_path": "资源路径"}'
    "\\n示例:"
    '\\n- 读取参考文档: {"skill_name": "my-skill", '
    '"resource_path": "references/analysis_framework.md"}'
    "\n注意: 执行脚本请使用 shell_interpreter 工具"
)
async def get_skill_resource(
    skill_name: str, resource_path: str, args: Optional[dict] = None
) -> str:
    """读取技能目录下的非脚本资源文件内容（如参考文档、模板等）。

    Args:
        skill_name: 技能名
        resource_path: 资源在技能内的相对路径（如 references/xxx.md）
        args: 可选参数（透传给 SkillManager）

    Returns:
        资源文件内容字符串；失败时返回 JSON 错误对象
    """
    from dbgpt.agent.skill.manage import get_skill_manager

    try:
        sm = get_skill_manager(CFG.SYSTEM_APP)
        result = await sm.get_skill_resource(skill_name, resource_path, args or {})
        return result
    except Exception as e:
        # 异常时返回结构化错误 JSON 给 LLM
        import json

        return json.dumps(
            {"error": True, "message": f"Error: {str(e)}"},
            ensure_ascii=False,
        )


@tool(
    description="执行技能scripts目录下的脚本文件。参数: "
    '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
)
async def execute_skill_script_file(
    skill_name: str, script_file_name: str, args: Optional[dict] = None
) -> str:
    """执行技能 `scripts/` 目录下的脚本文件（模块级工具版本）。

    注意：_react_agent_stream 内部还定义了一个同名闭包版本，会附加
    图片后处理、auto_data 提取、react_state 同步等增强逻辑。LLM 在
    ReAct 流程中实际调用的是闭包版本。

    Args:
        skill_name: 技能名
        script_file_name: scripts 目录下的脚本文件名
        args: 脚本参数

    Returns:
        执行结果字符串（通常是 chunks JSON）；失败时返回错误 chunks
    """
    from dbgpt.agent.skill.manage import get_skill_manager

    try:
        sm = get_skill_manager(CFG.SYSTEM_APP)
        result = await sm.execute_skill_script_file(
            skill_name, script_file_name, args or {}
        )
        return result
    except Exception as e:
        # 异常时返回标准 chunks 错误格式，便于前端降级渲染
        import json

        return json.dumps(
            {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
            ensure_ascii=False,
        )


@router.get("/v1/skills/list", response_model=Result)
async def list_skills(
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """列出技能目录下所有可用技能。

    遍历 DEFAULT_SKILLS_DIR，递归加载所有技能，返回每个技能的元数据：
      - id:        技能唯一标识（= name）
      - name:      技能显示名
      - description: 简短描述
      - version:   版本号
      - author:    作者
      - skill_type:类型（如 data_analysis / chat / coding）
      - tags:      标签列表
      - type:      'official'（claude/ 目录下）或 'personal'（user/ 目录下）
      - file_path: 相对于 skills_dir 的路径

    Args:
        user_token: 由 `get_user_from_headers` 注入的用户身份信息（鉴权）

    Returns:
        Result 包装的技能列表；失败时返回 E5001 错误码
    """
    from dbgpt.agent.skill.loader import SkillLoader

    skills_data = []
    skills_dir = DEFAULT_SKILLS_DIR
    skills_dir_resolved = Path(skills_dir).expanduser().resolve()

    try:
        loader = SkillLoader()
        # 递归加载整个 skills_dir
        skills = loader.load_skills_from_directory(skills_dir, recursive=True)

        for skill in skills:
            if not skill or not skill.metadata:
                # 跳过无效技能
                continue

            metadata = skill.metadata
            # 优先用 metadata.file_path，没有则退回 skill._config
            file_path = getattr(metadata, "file_path", None) or ""
            if not file_path and hasattr(skill, "_config"):
                file_path = skill._config.get("file_path", "")

            # 把绝对路径转成相对 skills_dir 的路径，便于前端展示
            if file_path:
                try:
                    file_path = str(
                        Path(file_path)
                        .expanduser()
                        .resolve()
                        .relative_to(skills_dir_resolved)
                    )
                except Exception:
                    pass

            # 根据所在目录判断 official / personal
            skill_type_category = "official"
            if "user/" in file_path or "/user/" in file_path:
                skill_type_category = "personal"
            elif "claude/" in file_path or "/claude/" in file_path:
                skill_type_category = "official"

            # 取 skill_type 字段（可能是枚举，取 .value）
            skill_type_val = metadata.skill_type
            if hasattr(skill_type_val, "value"):
                skill_type_val = skill_type_val.value

            skill_info = {
                "id": metadata.name,
                "name": metadata.name,
                "description": metadata.description or "",
                "version": getattr(metadata, "version", "1.0.0") or "1.0.0",
                "author": getattr(metadata, "author", None),
                "skill_type": skill_type_val,
                "tags": getattr(metadata, "tags", []) or [],
                "type": skill_type_category,
                "file_path": file_path,
            }
            skills_data.append(skill_info)

        # 排序：official 在前，然后按名字升序
        skills_data.sort(key=lambda x: (0 if x["type"] == "official" else 1, x["name"]))

        return Result.succ(skills_data)
    except Exception as e:
        logger.exception("Failed to load skills from directory")
        return Result.failed(code="E5001", msg=f"Failed to load skills: {str(e)}")


@router.get("/v1/skills/detail", response_model=Result)
async def skill_detail(
    skill_name: str = Query("", description="Skill name"),
    file_path: str = Query("", description="Skill file path"),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """查看指定技能的详情：文件树 + SKILL.md 内容 + 元数据。

    安全策略：
      - file_path 必须是相对路径（绝对路径会被尝试转相对）
      - 解析后的目标必须位于 skills_dir 内部，否则拒绝

    Args:
        skill_name: 可选，技能名
        file_path: 必填，技能在 skills_dir 下的相对路径
        user_token: 鉴权用户

    Returns:
        Result 包装的详情对象，含 tree / frontmatter / instructions /
        raw_content / content_type / metadata 等字段。
    """
    if not file_path:
        # file_path 是必填字段
        return Result.failed(code="E4001", msg="file_path is required")

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()

    # 始终把 file_path 视为相对 skills_dir 的路径
    # 兼容历史绝对路径写法：先尝试转成相对路径
    fp = Path(file_path).expanduser()
    if fp.is_absolute():
        try:
            fp = fp.resolve().relative_to(skills_dir)
        except Exception:
            return Result.failed(code="E4002", msg="Invalid skill file path")
    target = (skills_dir / fp).resolve()

    # 安全检查：target 必须位于 skills_dir 内部（防止越界访问）
    try:
        target.relative_to(skills_dir)
    except Exception:
        return Result.failed(code="E4002", msg="Invalid skill file path")

    if not target.exists():
        return Result.failed(code="E4040", msg="Skill file not found")

    # 如果指向文件，root_dir 是其父目录；指向目录，root_dir 是自身
    root_dir = target if target.is_dir() else target.parent

    def build_tree(path: Path, base: Path) -> Dict[str, Any]:
        """递归构建技能目录的文件树结构（前端 AntD Tree 用）。"""
        rel = path.relative_to(base)
        node: Dict[str, Any] = {
            "title": path.name,
            "key": str(rel),
        }
        if path.is_dir():
            # 排除隐藏文件；目录在前、文件在后，按名字升序
            children = sorted(
                [p for p in path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            node["children"] = [build_tree(child, base) for child in children]
        return node

    tree = build_tree(root_dir, root_dir)

    # 尝试读取 SKILL.md：优先级 SKILL.md > 直接读取目标文件
    skill_md_path = root_dir / "SKILL.md"
    frontmatter = ""
    instructions = ""
    raw_content = ""
    content_type = ""

    if skill_md_path.exists():
        # 解析 SKILL.md：把 frontmatter 和正文分离
        raw_content = skill_md_path.read_text(encoding="utf-8")
        content_type = "skill_md"
        content = raw_content.strip()
        if content.startswith("---"):
            # 切出 frontmatter 与 body
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                instructions = parts[2].strip()
            else:
                instructions = content
        else:
            instructions = content
    elif target.is_file():
        # 直接读取目标文件（非 SKILL.md 的情况）
        raw_content = target.read_text(encoding="utf-8")
        suffix = target.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            content_type = "yaml"
            frontmatter = raw_content
        elif suffix == ".json":
            content_type = "json"
            frontmatter = raw_content
        else:
            content_type = "text"
            instructions = raw_content

    # 再尝试用 SkillLoader 加载元数据（更权威）
    metadata: Dict[str, Any] = {}
    try:
        from dbgpt.agent.skill.loader import SkillLoader

        loader = SkillLoader()
        skill = loader.load_skill_from_file(str(target))
        if skill and getattr(skill, "metadata", None):
            try:
                # 优先用 metadata.to_dict() 拿到完整字典
                metadata = skill.metadata.to_dict()  # type: ignore[attr-defined]
            except Exception:
                # 退化：手工按字段读取
                metadata = {
                    "name": getattr(skill.metadata, "name", ""),
                    "description": getattr(skill.metadata, "description", ""),
                    "version": getattr(skill.metadata, "version", ""),
                    "author": getattr(skill.metadata, "author", ""),
                    "skill_type": getattr(skill.metadata, "skill_type", ""),
                    "tags": getattr(skill.metadata, "tags", []) or [],
                }
    except Exception:
        metadata = {}

    # 如果没有 frontmatter，从 metadata 兜底拼一段
    if not frontmatter and metadata:
        frontmatter = "\n".join(
            [
                f"name: {metadata.get('name', '')}",
                f"description: {metadata.get('description', '')}",
                f"version: {metadata.get('version', '')}",
                f"author: {metadata.get('author', '')}",
                f"skill_type: {metadata.get('skill_type', '')}",
            ]
        ).strip()

    # 把绝对路径转成相对路径，便于前端展示
    display_path = str(target)
    display_root = str(root_dir)
    try:
        display_path = str(target.relative_to(skills_dir))
        display_root = str(root_dir.relative_to(skills_dir))
    except Exception:
        pass

    return Result.succ(
        {
            "skill_name": skill_name or metadata.get("name", ""),
            "file_path": display_path,
            "root_dir": display_root,
            "tree": tree,
            "frontmatter": frontmatter,
            "instructions": instructions,
            "raw_content": raw_content,
            "content_type": content_type,
            "metadata": metadata,
        }
    )


def _install_skill_from_dir(src_dir: Path, skill_name: str, user_dir: Path) -> str:
    """把已解压的技能目录拷贝到 user_dir 下。

    安装流程：
      1. 删除 user_dir/<skill_name> 旧副本
      2. 整树拷贝 src_dir -> user_dir/<skill_name>
      3. 返回相对 skills_dir 的路径（即 user/<skill_name>）

    Args:
        src_dir: 源目录（已解压到本地）
        skill_name: 在 user_dir 下使用的目录名
        user_dir: skills/user/ 目录

    Returns:
        安装目录相对于 skills_dir 的路径字符串
    """
    dest = user_dir / skill_name
    if dest.exists():
        # 同名旧技能直接覆盖
        shutil.rmtree(dest)
    shutil.copytree(src_dir, dest)
    # user_dir 的父目录就是 skills_dir
    return str(dest.relative_to(user_dir.parent))


@router.post("/v1/skills/upload", response_model=Result)
async def skill_upload(
    file: UploadFile = File(...),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """上传技能包（.zip / .skill）或单文件，安装到 skills/user/ 下。

    流程：
      1. 校验文件名（防路径穿越）
      2. 写入 pilot/tmp/ 临时目录
      3. 若是压缩包：用 `_extract_skill_from_zip` 解压并安装
         若是单文件：直接放到 skills/user/<stem>/SKILL.md 或同名文件
      4. 返回相对路径供前端展示

    Args:
        file: 上传的文件对象
        user_token: 鉴权用户

    Returns:
        Result 包含 file_path / tmp_path / message；失败时返回相应错误码
    """
    if not file.filename:
        # 文件必须有文件名
        return Result.failed(code="E4001", msg="No file provided")

    # 准备临时上传目录与用户技能目录
    upload_dir = Path(resolve_root_path("pilot/tmp") or "pilot/tmp").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    user_dir = skills_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 文件名安全校验
        filename = _validate_upload_filename(file.filename)
    except ValueError as exc:
        return Result.failed(code="E4002", msg=str(exc))

    suffix = Path(filename).suffix.lower()
    stem = Path(filename).stem

    try:
        # 读取上传内容
        content_bytes = await file.read()

        # 先落盘到 tmp 临时目录（保留原文件名）
        tmp_file = upload_dir / filename
        tmp_file.write_bytes(content_bytes)

        # 判断是否为压缩包：.zip 直接认为是；.skill 用 zipfile 检测
        is_archive = False
        if suffix == ".zip":
            is_archive = True
        elif suffix == ".skill":
            buf = io.BytesIO(content_bytes)
            is_archive = zipfile.is_zipfile(buf)

        if is_archive:
            # 复用 GitHub 导入使用的 `_extract_skill_from_zip`，避免早期
            # inline extractall 写法的嵌套目录 bug。
            # strict=False：上传的包可能尚未包含 SKILL.md（用户草稿）
            tmp_zip = upload_dir / f"{uuid.uuid4().hex}.zip"
            tmp_zip.write_bytes(content_bytes)
            try:
                with tempfile.TemporaryDirectory(dir=upload_dir) as tmp_extract:
                    dest_in_tmp = Path(tmp_extract) / "skill"
                    try:
                        dest_name = _extract_skill_from_zip(
                            tmp_zip, subpath=None, dest_dir=dest_in_tmp, strict=False
                        )
                    except ValueError as exc:
                        # 解压失败：返回错误信息（如多个候选子目录）
                        return Result.failed(code="E4002", msg=str(exc))

                    # 把解压后的目录安装到 skills/user/
                    rel_path = _install_skill_from_dir(dest_in_tmp, dest_name, user_dir)
            finally:
                # 临时 zip 文件清理
                tmp_zip.unlink(missing_ok=True)

        else:
            # 单文件：放到 skills/user/<stem>/ 目录下
            # .md 和 .skill 后缀的文件统一改名为 SKILL.md
            dest = user_dir / stem
            dest.mkdir(parents=True, exist_ok=True)

            if suffix in (".md", ".skill"):
                target_name = "SKILL.md"
            else:
                target_name = filename
            target_file = dest / target_name

            target_file.write_bytes(content_bytes)

            # 返回相对路径
            rel_path = str(dest.relative_to(skills_dir))

        return Result.succ(
            {
                "file_path": rel_path,
                "tmp_path": str(tmp_file),
                "message": f"Skill uploaded successfully: {rel_path}",
            }
        )
    except Exception as e:
        logger.exception("Failed to upload skill")
        return Result.failed(code="E5002", msg=f"Upload failed: {str(e)}")


def _parse_github_url(
    github_url: str,
) -> "tuple[str, str, str, Optional[str]]":
    """解析 GitHub 或 skills.sh URL 为 (owner, repo, branch, subdir)。

    支持的格式：
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/<branch>[/optional/sub/dir]
      - https://github.com/owner/repo/blob/<branch>/path/to/FILE.md
      - https://skills.sh/owner/repo
      - https://skills.sh/owner/repo[/skill-name]

    Args:
        github_url: 待解析的 URL 字符串

    Returns:
        Tuple(owner, repo, branch, subdir)
          - owner / repo  一定有值
          - branch        总是 str，默认 "main"
          - subdir        Optional[str]，无子路径时为 None

    Raises:
        ValueError: URL 不是 GitHub / skills.sh 时抛出
    """
    parsed = urlparse(github_url)
    # 判定域名
    is_skills_sh = parsed.netloc in ("skills.sh", "www.skills.sh")
    is_github = parsed.netloc in ("github.com", "www.github.com")

    if not is_github and not is_skills_sh:
        raise ValueError(f"Not a GitHub URL: {github_url!r}")

    # 切分 path
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot extract owner/repo from URL: {github_url!r}")

    owner, repo = parts[0], parts[1]
    # 兼容 git clone 写法：去掉 .git 后缀
    if repo.endswith(".git"):
        repo = repo[:-4]

    branch: str = "main"
    subdir: Optional[str] = None

    if is_skills_sh:
        # skills.sh: /owner/repo[/skill-name[/more]]
        # owner/repo 之后的部分全部作为子路径
        if len(parts) >= 3:
            subdir = "/".join(parts[2:])
    else:
        # GitHub
        if len(parts) >= 4 and parts[2] == "tree":
            # /owner/repo/tree/<branch>[/path/to/subdir]
            branch = parts[3]
            if len(parts) >= 5:
                subdir = "/".join(parts[4:])
        elif len(parts) >= 4 and parts[2] == "blob":
            # /owner/repo/blob/<branch>/path/to/FILE.md
            # 注意：最后一段是文件名，要去掉
            branch = parts[3]
            if len(parts) >= 6:
                # 保留除最后一个文件名外的所有路径段
                subdir = "/".join(parts[4:-1])
            # 若只有 5 段：blob/<branch>/filename，无 subdir

    return owner, repo, branch, subdir


def _construct_download_url(owner: str, repo: str, branch: str) -> str:
    """根据 owner / repo / branch 拼出 GitHub 仓库 zip 下载 URL。

    Args:
        owner: 仓库 owner / 组织名
        repo: 仓库名
        branch: 分支名

    Returns:
        指向该分支 zip 归档的下载 URL
    """
    return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"


def _is_macos_junk(name: str) -> bool:
    """判断压缩包内的某条目是否是 macOS 元数据垃圾文件。

    macOS 在 Finder 压缩时会附加 `__MACOSX/` 目录和 `._xxx` 元数据文件，
    这些不应被当作技能文件处理，否则会导致目录结构判定出错。

    Args:
        name: 压缩包内的成员名（如 `repo-main/__MACOSX/._skill`）

    Returns:
        True 表示应被过滤掉
    """
    parts = name.split("/")
    return any(p == "__MACOSX" or p.startswith("._") for p in parts)


def _extract_skill_from_zip(
    zip_path: "Path",
    subpath: "Optional[str]",
    dest_dir: "Path",
    strict: bool = True,
) -> str:
    """从 ZIP 归档中解压技能到 dest_dir。

    典型场景：
      - GitHub 仓库 zip 总有一个顶级目录（如 `repo-main/`），本函数会
        自动剥掉该顶级目录，让里面的文件直接落到 dest_dir 下
      - 当指定 subpath 时，只解压 `{顶级目录}/{subpath}/` 下的内容
        （同样剥掉前缀）
      - 自动过滤 macOS 元数据（`__MACOSX/` 与 `._*` 文件），避免它们
        干扰目录结构判定

    Args:
        zip_path: ZIP 文件路径
        subpath: 归档内（剥掉顶级目录后）的子目录路径；
                 传 None 表示使用归档根
        dest_dir: 解压目标目录；若存在会被清空后重建
        strict: True 时若找不到 SKILL.md 抛 ValueError；
                False 时跳过 SKILL.md 校验（用于上传草稿包）

    Returns:
        技能名（来自 subpath 最后一段或顶级目录名）

    Raises:
        ValueError: 归档包含路径穿越序列
        ValueError: strict=True 且找不到 SKILL.md
        ValueError: 顶级目录下有多个候选技能但未指定 subpath
                    （错误消息列出可选子目录）
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        all_names = zf.namelist()

        # 安全检查：拒绝任何包含路径穿越（..）的成员
        for name in all_names:
            normalized = os.path.normpath(name)
            if normalized.startswith("..") or ".." in normalized.split(os.sep):
                raise ValueError(f"Unsafe path in archive: {name!r}")

        # 过滤掉 macOS 垃圾文件
        valid_names = [n for n in all_names if not _is_macos_junk(n)]

        # 探测唯一的顶级目录（GitHub zip 必有一个，如 `repo-main`）
        top_dirs = {n.split("/")[0] for n in valid_names if "/" in n}
        archive_root: Optional[str] = top_dirs.pop() if len(top_dirs) == 1 else None

        # 计算 archive 内对应 dest_dir 的前缀
        if subpath:
            skill_prefix = (
                f"{archive_root}/{subpath}/" if archive_root else f"{subpath}/"
            )
            skill_name = subpath.split("/")[-1]
        else:
            skill_prefix = f"{archive_root}/" if archive_root else ""
            skill_name = archive_root or dest_dir.name

        # 检查所选前缀下是否存在 SKILL.md
        skill_md_entry = next(
            (n for n in valid_names if n == skill_prefix + "SKILL.md"),
            None,
        )

        if skill_md_entry is None and not subpath:
            # 根下没有 SKILL.md：扫描一层子目录
            subdirs_with_skill = []
            for name in valid_names:
                if not name.startswith(skill_prefix):
                    continue
                rel = name[len(skill_prefix) :]
                parts = rel.split("/")
                # 形如 `subdir/SKILL.md` 的成员：记录 subdir
                if len(parts) == 2 and parts[1] == "SKILL.md":
                    subdirs_with_skill.append(parts[0])

            if len(subdirs_with_skill) > 1:
                # 多个候选技能：要求用户明确指定 subpath
                raise ValueError(
                    "Multiple skills found. Specify a subpath. "
                    "Available: " + ", ".join(sorted(subdirs_with_skill))
                )

            # 恰好一个子目录有 SKILL.md：自动选用它
            if len(subdirs_with_skill) == 1:
                only_subdir = subdirs_with_skill[0]
                skill_prefix = f"{skill_prefix}{only_subdir}/"
                skill_name = only_subdir
                skill_md_entry = skill_prefix + "SKILL.md"

        if strict and skill_md_entry is None:
            # 严格模式：必须有 SKILL.md
            raise ValueError(
                "No SKILL.md found in the archive"
                + (f" under '{subpath}'" if subpath else "")
                + ". Make sure the skill directory contains a SKILL.md file."
            )

        # 准备 dest_dir：先清空再创建
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 逐个解压有效成员（不使用 extractall，更安全）
        for member in valid_names:
            if not member.startswith(skill_prefix) or member == skill_prefix:
                # 不在目标前缀下：跳过
                continue
            rel = member[len(skill_prefix) :]
            if not rel:
                continue
            target = dest_dir / rel
            if member.endswith("/"):
                # 目录条目：mkdir
                target.mkdir(parents=True, exist_ok=True)
            else:
                # 文件条目：先建父目录，再写文件
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))

    return skill_name


@router.post("/v1/skills/import_github", response_model=Result)
async def skill_import_from_github_v2(
    request: Request,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """从 GitHub / skills.sh URL 导入技能。

    接受前端 `{"url": "..."}` 请求体，下载仓库 zip、解压技能、安装到
    `skills/user/<name>/`，返回相对路径。

    关键行为：
      - 接受原始 JSON 体（不使用 Pydantic 模型）
      - 分支回退：先试 `main`，404 再试 `master`
      - 下载大小限制 50 MB
      - 解压与安装复用 `_extract_skill_from_zip` 与 `_install_skill_from_dir`

    错误码：
      - E4001: URL 为空
      - E4003: URL 非 GitHub / skills.sh 或格式错误
      - E4004: 解压后找不到 SKILL.md
      - E4005: 下载失败或超大小限制
      - E5002: 服务器内部异常
    """
    import httpx

    # --- 1. 解析 JSON body，提取 url ---
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return Result.failed(code="E4001", msg="URL must not be empty")

    # --- 2. 解析 URL，分离 owner / repo / branch / subpath ---
    try:
        owner, repo, branch, subpath = _parse_github_url(url)
    except ValueError as exc:
        return Result.failed(code="E4003", msg=str(exc))

    # --- 3. 准备目录 ---
    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    user_dir = skills_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    upload_dir = Path(resolve_root_path("pilot/tmp") or "pilot/tmp").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    # --- 4. 下载 zip（含 main→master 分支回退） ---
    zip_path: Optional[Path] = None
    tmp_dir_obj = None  # TemporaryDirectory 句柄，需要在 finally 中清理

    try:
        zip_url = _construct_download_url(owner, repo, branch)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(120.0),
        ) as client:
            response = await client.get(zip_url)

            # 分支回退：main 返回 404 时尝试 master
            if response.status_code == 404 and branch == "main":
                fallback_branch = "master"
                fallback_url = _construct_download_url(owner, repo, fallback_branch)
                response = await client.get(fallback_url)
                if response.status_code == 200:
                    branch = fallback_branch
                    zip_url = fallback_url

            if response.status_code != 200:
                # 下载失败
                return Result.failed(
                    code="E4005",
                    msg=(
                        f"Failed to download {zip_url!r}: HTTP {response.status_code}"
                    ),
                )

            content_bytes = response.content

        # --- 5. 大小限制检查（50 MB） ---
        if len(content_bytes) > 50 * 1024 * 1024:
            return Result.failed(
                code="E4005",
                msg=(
                    f"Download size {len(content_bytes) // (1024 * 1024)} MB "
                    "exceeds the 50 MB limit"
                ),
            )

        # --- 6. 保存原始 zip 到 tmp 目录 ---
        zip_filename = f"{repo}-{branch}.zip"
        zip_path = upload_dir / zip_filename
        zip_path.write_bytes(content_bytes)

        # --- 7. 解压到临时目录，再安装到 skills/user/ ---
        tmp_dir_obj = tempfile.TemporaryDirectory(dir=upload_dir)
        dest_dir_in_temp = Path(tmp_dir_obj.name) / "skill"
        dest_dir_in_temp.mkdir(parents=True, exist_ok=True)

        try:
            skill_name = _extract_skill_from_zip(zip_path, subpath, dest_dir_in_temp)
        except ValueError as exc:
            # 把 SKILL.md 缺失错误单独编码为 E4004
            err_msg = str(exc)
            if "SKILL.md" in err_msg:
                return Result.failed(code="E4004", msg=err_msg)
            return Result.failed(code="E4003", msg=err_msg)

        rel_path = _install_skill_from_dir(dest_dir_in_temp, skill_name, user_dir)

        return Result.succ(
            {
                "file_path": rel_path,
                "message": f"Skill imported successfully from GitHub: {rel_path}",
            }
        )

    except httpx.RequestError as exc:
        # 网络层异常（连接超时、DNS 失败等）
        logger.exception("Network error while downloading skill from GitHub")
        return Result.failed(
            code="E4005", msg=f"Network error downloading skill: {str(exc)}"
        )
    except Exception as exc:
        # 其他未预期异常
        logger.exception("Failed to import skill from GitHub (v2)")
        return Result.failed(code="E5002", msg=f"Import failed: {str(exc)}")
    finally:
        # 最终清理：删除临时 zip 文件
        if zip_path is not None:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
        # 最终清理：清理临时解压目录
        if tmp_dir_obj is not None:
            try:
                tmp_dir_obj.cleanup()
            except Exception:
                pass


def _sse_event(payload: Dict[str, Any]) -> str:
    """把字典序列化为 SSE 单事件字符串。

    SSE 事件格式：`data: <json>\\n\\n`，前端 EventSource 会自动解析。
    ensure_ascii=False 保留中文，避免前端二次解码。

    Args:
        payload: 任意可 JSON 序列化的事件字典

    Returns:
        形如 `data: {...}\\n\\n` 的字符串
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _react_agent_stream(
    dialogue: ConversationVo,
) -> AsyncGenerator[str, None]:
    """ReAct Agent 的 SSE 流式主处理函数。

    这是整个文件的核心函数（约 3300 行），完成以下工作：
      1. 解析 dialogue.ext_info 中的 file_path / skill_name / knowledge_space /
         database_name / connector_ids
      2. 加载技能、业务工具、知识库、数据库 connector
      3. 【上下文注入点 #1】向量库检索 top-20 表结构
      4. 定义一堆 @tool 闭包工具（select_skill / load_skill / sql_query /
         code_interpreter / shell_interpreter / html_interpreter 等），
         这些工具捕获 react_state 在多轮间共享状态
      5. 创建 LLM 客户端、AgentMemory（【注入点 #2】）、AgentContext
      6. 把 user_input 与 db_summary_context 拼接（【注入点 #3】）
      7. 从 conversation service 全量加载历史对话（【注入点 #4】）
      8. 启动 agent 任务，主循环从 stream_queue 取事件转 SSE：
         - thinking / thinking_chunk：缓冲思考内容
         - act：创建 step.card，输出 code/markdown/text/observation
         - todowrite：发射 plan.update，前端渲染任务计划卡片
         - context.status：转发上下文管理状态
      9. agent 完成后从 terminate action 提取 final_content，写入 chat_history
      10. 发射 final 与 done 事件

    Args:
        dialogue: ConversationVo，含 conv_uid / user_input / model_name / ext_info 等

    Yields:
        SSE 事件字符串（字符串形式 `data: {...}\\n\\n`）
    """
    import asyncio

    # 延迟导入 agent 相关模块（避免顶层导入循环依赖）
    from dbgpt.agent import AgentContext, AgentMemory, AgentMessage
    from dbgpt.agent.claude_skill import get_registry, load_skills_from_dir
    from dbgpt.agent.core.memory.gpts import (
        DefaultGptsPlansMemory,
        GptsMemory,
    )
    from dbgpt.agent.expand.actions.react_action import Terminate
    from dbgpt.agent.expand.react_agent import ReActAgent
    from dbgpt.agent.resource import ToolPack, tool
    from dbgpt.agent.resource.base import AgentResource, ResourceType
    from dbgpt.agent.resource.manage import get_resource_manager
    from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
    from dbgpt.agent.util.react_parser import ReActOutputParser
    from dbgpt.core import StorageConversation
    from dbgpt.model.cluster.client import DefaultLLMClient
    from dbgpt.util.code.server import get_code_server
    from dbgpt_serve.agent.agents.db_gpts_memory import MetaDbGptsMessageMemory
    from dbgpt_serve.conversation.serve import Serve as ConversationServe

    # step 是 build_step 使用的全局序号，每次创建新 step 自增
    step = 0
    # 用户的原始问题文本
    user_input = dialogue.user_input
    if not isinstance(user_input, str):
        # 兜底类型转换
        user_input = str(user_input or "")

    # 从 ext_info 解析各种上下文标识
    file_path = None  # 上传文件路径
    knowledge_space = None  # 知识库名
    skill_name = None  # 预选技能名
    database_name = None  # 数据库名
    if dialogue.ext_info and isinstance(dialogue.ext_info, dict):
        file_path = dialogue.ext_info.get("file_path")
        skill_name = dialogue.ext_info.get("skill_name")
        # 知识库字段名兼容多种写法
        knowledge_space = (
            dialogue.ext_info.get("knowledge_space")
            or dialogue.ext_info.get("knowledge_space_name")
            or dialogue.ext_info.get("knowledge_space_id")
        )
        database_name = dialogue.ext_info.get("database_name")

    # Connector 选择（Task C）：仅注入用户在前端选中的 connector
    connector_ids: List[str] = _parse_connector_ids(dialogue.ext_info)

    # === SSE 事件辅助函数：所有闭包共享 step / round_step_map 等状态 ===

    def build_step(title: str, detail: str, phase: str = None):
        """创建一个新的 step 卡片，发射 step.start 事件并返回 (step_id, event_str)。

        Args:
            title: 卡片标题（如 "Load Skill" / "code_interpreter"）
            detail: 副标题/描述
            phase: 可选阶段名（如 "加载技能"），前端用于分组
        """
        nonlocal step
        step += 1
        step_id = f"step-{step}"
        event_data = {
            "type": "step.start",
            "step": step,
            "id": step_id,
            "title": title,
            "detail": detail,
        }
        if phase:
            event_data["phase"] = phase
        return step_id, _sse_event(event_data)

    def step_output(detail: str):
        """发射 step.output 事件（向当前 step 追加纯文本输出）。"""
        return _sse_event({"type": "step.output", "step": step, "detail": detail})

    def step_chunk(step_id: str, output_type: str, content: Any):
        """发射 step.chunk 事件（向指定 step 发送一个分块内容）。

        Args:
            step_id: 目标 step 的 ID
            output_type: 内容类型（text/markdown/code/json/table/chart/image/html）
            content: 内容载荷
        """
        return _sse_event(
            {
                "type": "step.chunk",
                "id": step_id,
                "output_type": output_type,
                "content": content,
            }
        )

    def step_done(step_id: str, status: str = "done"):
        """发射 step.done 事件，标记该 step 完成（或失败）。"""
        return _sse_event({"type": "step.done", "id": step_id, "status": status})

    def step_meta(
        step_id: str,
        thought: Optional[str],
        action: Optional[str],
        action_input: Optional[str],
        title: Optional[str] = None,
        action_intention: Optional[str] = None,
        action_reason: Optional[str] = None,
        todo_meta: Optional[Dict[str, Any]] = None,
    ):
        """发射 step.meta 事件，附加思考、动作、动作输入、todo 元信息等。

        前端用 step.meta 渲染 Thought/Action/Action Input 卡片细节。
        """
        payload = {
            "type": "step.meta",
            "id": step_id,
            "thought": thought,
            "action_intention": action_intention,
            "action_reason": action_reason,
            "action": action,
            "action_input": action_input,
            "title": title,
        }
        if todo_meta:
            payload["todo_meta"] = todo_meta
        return _sse_event(payload)

    def chunk_text(text: str, max_len: int = 800) -> List[str]:
        """把长文本按 max_len 切分成多块，便于 SSE 分块传输。

        Args:
            text: 原始文本
            max_len: 单块最大字符数

        Returns:
            字符串列表；空文本返回空列表
        """
        if not text:
            return []
        chunks: List[str] = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + max_len])
            start += max_len
        return chunks

    def emit_tool_chunks(step_id: str, content: Any) -> List[str]:
        """把工具执行结果（chunks JSON 或纯文本）解析成 SSE chunk 事件列表。

        约定工具返回 `{"chunks": [{"output_type": ..., "content": ...}, ...]}`
        格式，本函数负责把每个 chunk 按类型分发为 step.chunk SSE 事件：
          - code / markdown：整块发送（不切分，避免破坏代码/MD 结构）
          - text：按 800 字符切分多次发送
          - 其他（json/table/chart/image/html）：原样整块发送

        Args:
            step_id: 目标 step ID
            content: 工具返回的内容（字符串或已解析对象）

        Returns:
            SSE 事件字符串列表（已格式化好可直接 yield）
        """
        raw_chunks: List[str] = []
        if content is None:
            return raw_chunks
        # 尝试 JSON 解析
        parsed = None
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = None
        # 标准 chunks 协议路径
        if isinstance(parsed, dict) and isinstance(parsed.get("chunks"), list):
            for item in parsed["chunks"]:
                if not isinstance(item, dict):
                    continue
                output_type = item.get("output_type") or "text"
                payload = item.get("content")
                if output_type in ["code", "markdown"] and isinstance(payload, str):
                    # code / markdown 必须整块发，不能切分
                    raw_chunks.append(step_chunk(step_id, output_type, payload))
                elif output_type in ["text"] and isinstance(payload, str):
                    # text 切成 800 字符的分块
                    for chunk in chunk_text(payload, max_len=800):
                        raw_chunks.append(step_chunk(step_id, output_type, chunk))
                else:
                    # 其他类型：原样整块发
                    raw_chunks.append(step_chunk(step_id, output_type, payload))
            return raw_chunks
        # 兜底：纯文本字符串按 800 字符切分
        if isinstance(content, str) and content:
            for chunk in chunk_text(content, max_len=800):
                raw_chunks.append(step_chunk(step_id, "text", chunk))
        return raw_chunks

    def normalize_display_text(value: Optional[str]) -> Optional[str]:
        """规范化模型给出的展示文本（action_intention / action_reason）。

        - 合并空白
        - 去掉 `phase:` / `status:` / `状态:` 等前缀
        - 去掉首尾标点
        - 空字符串返回 None
        """
        if not value:
            return None

        text = re.sub(r"\s+", " ", value).strip()
        # 去掉常见前缀
        text = re.sub(
            r"^(phase|status|状态|action\s+intention|action\s+reason)\s*:\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        # 去掉首尾的中英文标点
        text = text.strip(" .,:;，。；：")
        if not text:
            return None
        return text

    def summarize_thought(
        thought: Optional[str], action: Optional[str] = None
    ) -> Optional[str]:
        """当模型未给出简短 status 时的兜底压缩器。

        把 LLM 的长 thought 文本压缩成简短的中文状态描述，规则：
          - 去掉 "thought:" / "phase:" 等前缀
          - 在 action / observation / 下一步 等关键词处截断
          - 去掉常见口头前缀（"我需要"、"let me" 等）
          - 根据 action 类型给出标准中文描述

        Args:
            thought: 模型给出的 thought 文本
            action: 当前 action 名称，用于按动作类型给标准描述

        Returns:
            压缩后的短状态字符串，或 None
        """
        if not thought:
            return None

        text = re.sub(r"\s+", " ", thought).strip()
        # 去掉 thought/phase 前缀
        text = re.sub(r"^(thought|phase)\s*:\s*", "", text, flags=re.I).strip()
        if not text:
            return None

        # 在这些关键词处截断（保留前面的部分）
        split_markers = [
            r"\baction\b\s*:",
            r"\bobservation\b\s*:",
            r"\bphase\b\s*:",
            r"\bnow i need to\b",
            r"\bnext,?\b",
            r"\bthen\b",
            r"现在需要",
            r"下一步",
            r"接下来",
            r"然后",
        ]
        marker_pattern = "|".join(split_markers)
        text = re.split(marker_pattern, text, maxsplit=1, flags=re.I)[0].strip(
            " .,:;，。；："
        )

        # 去掉常见口头前缀
        prefixes = [
            "the user wants me to ",
            "i need to ",
            "i should ",
            "let me ",
            "i will ",
            "现在我需要",
            "我需要",
            "接下来我需要",
            "让我",
            "现在开始",
            "好的，",
            "好，",
        ]
        lowered = text.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix.lower()):
                text = text[len(prefix) :].strip(" .,:;，。；：")
                lowered = text.lower()
                break

        # 按 action 给出标准中文状态
        action_lower = (action or "").lower()
        if action_lower == "sql_query":
            return "正在查询数据库信息"
        if action_lower == "code_interpreter":
            return "正在生成分析代码"
        if action_lower == "html_interpreter":
            return "正在生成并渲染 HTML 报告"
        if action_lower == "todowrite":
            return "正在更新任务计划"
        if action_lower in {"execute_skill_script", "execute_skill_script_file"}:
            return "正在执行分析脚本"

        return text

    skills_dir = DEFAULT_SKILLS_DIR  # 技能根目录
    registry = get_registry()  # 获取技能注册表单例

    # Step 1: 预加载所有技能到 registry（递归扫描 skills_dir）
    load_skills_from_dir(skills_dir, recursive=True)
    all_skills = registry.list_skills()

    # Step 2: 从 ResourceManager 收集已注册的业务工具
    # 这些工具由其他模块注册（如 datasource、自定义 @tool），将和文件内
    # 定义的闭包工具一起放进 ToolPack
    rm = get_resource_manager(CFG.SYSTEM_APP)
    business_tools: List[Any] = []
    try:
        # 直接读内部字典，跳过 API 调用减少开销
        tool_resources = rm._type_to_resources.get("tool", [])
        for reg_resource in tool_resources:
            if reg_resource.resource_instance is not None:
                business_tools.append(reg_resource.resource_instance)
    except Exception:
        # 没有业务工具也能继续，使用空列表
        pass  # If no business tools, continue with empty list

    # Step 3: 如果指定了 knowledge_space，加载知识库 retriever 资源
    knowledge_resources: List[Any] = []
    knowledge_context = ""  # 会拼到 system prompt 里
    if knowledge_space:
        try:
            from dbgpt_serve.agent.resource.knowledge import (
                KnowledgeSpaceRetrieverResource,
            )

            # 构造知识库检索资源，top_k=4 控制召回数量
            knowledge_resource = KnowledgeSpaceRetrieverResource(
                name=f"knowledge_space_{knowledge_space}",
                space_name=knowledge_space,
                top_k=4,
                system_app=CFG.SYSTEM_APP,
            )
            knowledge_resources.append(knowledge_resource)
            # 拼一段提示给 LLM，告诉它有 knowledge_retrieve 工具可用
            knowledge_context = f"""
## Knowledge Base
- Knowledge space: {knowledge_resource.retriever_name or knowledge_space}
- Description: {knowledge_resource.retriever_desc or "Knowledge retrieval available"}
- You can use the 'knowledge_retrieve' tool to search this knowledge base.
"""
            logger.info(
                f"Loaded knowledge space resource: {knowledge_space} "
                f"(name: {knowledge_resource.retriever_name})"
            )
        except Exception as e:
            # 知识库加载失败不致命：把警告塞进 prompt 让 LLM 知道
            logger.warning(f"Failed to load knowledge space resource: {e}", exc_info=e)
            knowledge_context = f"""
## Knowledge Base
- Warning: Failed to load knowledge space '{knowledge_space}'. Error: {str(e)}
"""

    # Step 4: 加载数据库 connector 与向量库表结构检索
    # ─────────────────────────────────────────────────────────────
    # 【上下文注入点 #1：向量库表结构检索】
    # 每次请求只要 database_name 非空就会执行：
    #   1. get_table_info_no_throw() — Trino 下返回空（MetaData.reflect 被 patch 成 no-op）
    #   2. get_db_summary(top_k=20) — 向量库检索 top-20 张表，拼到 db_summary_context
    #   3. db_summary_context 在 L3658-3662 被拼进 user message
    # ⚠️ 重复风险：每个新问题都会重新检索 top-20 表，导致上下文里反复出现表结构
    # ─────────────────────────────────────────────────────────────
    database_connector = None
    database_context = ""  # 注入到 system prompt 的 {database_context} 占位符
    # db_summary_context 最终会拼到 user message 里（见 L3658-3662）
    db_summary_context = ""
    if database_name:
        try:
            # 取数据库连接器（从 ConnectorManager 单例）
            local_db_manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
            database_connector = local_db_manager.get_connector(database_name)
            # 列出所有表名
            table_names = list(database_connector.get_table_names())
            # 尝试获取表结构（DDL）
            table_info = database_connector.get_table_info_no_throw()
            # Trino 等不 reflect 的 connector 会返回空，走向量库补
            # ⚠️ 只要 table_info 为空，每个新问题都会重新跑 get_db_summary
            if not table_info or not table_info.strip():
                try:
                    from dbgpt_serve.datasource.service.db_summary_client import (
                        DBSummaryClient,
                    )

                    summary_client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
                    # 向量库检索：top_k=20 张与 user_input 最相关的表
                    # 字段检索在 DBSchemaRetriever._retrieve_field 里全量返回
                    table_infos = summary_client.get_db_summary(
                        database_name,
                        user_input,
                        20,
                    )
                    if table_infos:
                        # 把检索到的表结构拼到 db_summary_context，
                        # 后续会在注入点 #3 拼到 user message 末尾
                        db_summary_context = (
                            "\n\n## 相关表结构（来自向量库检索）\n"
                            + "\n\n".join(table_infos)
                        )
                        logger.info(
                            f"Retrieved {len(table_infos)} table summaries "
                            f"from vector store for db={database_name}"
                        )
                except Exception as se:
                    # 向量库检索失败仅记日志，不影响主流程
                    logger.warning(
                        f"Failed to retrieve db summary from vector store: {se}",
                        exc_info=se,
                    )
            # database_context 注入到 system prompt 的 {database_context} 占位符
            database_context = f"""
## 数据库信息
- 数据库名: {database_name}
- 可用表: {", ".join(table_names)}
- 表结构:
{table_info}
- 使用 'sql_query' 工具执行 SQL 查询
- **只允许 SELECT 查询，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE**
"""
            logger.info(
                f"Loaded database connector: {database_name} "
                f"(tables: {', '.join(table_names)})"
            )
        except Exception as e:
            # 数据库加载失败：把警告塞进 prompt，LLM 会告知用户
            logger.warning(f"Failed to load database connector: {e}", exc_info=e)
            database_context = f"""
## 数据库
- 警告: 加载数据库 '{database_name}' 失败。错误: {str(e)}
"""

    # react_state 是贯穿整个 ReAct 流程的会话级状态字典。
    # 闭包工具通过捕获此字典在多轮对话间共享状态：
    #   - matched / skill_prompt：当前选中的技能及其 prompt 模板
    #   - file_path：用户上传的文件路径
    #   - conv_id：当前会话 ID
    #   - generated_images / image_url_map：本轮生成的图片 URL 列表与映射
    #   - ratio_data / auto_data：脚本计算结果，供 html_interpreter 模板替换
    react_state: Dict[str, Any] = {
        "skills_loaded": True,  # Skills are pre-loaded now
        "matched": None,
        "skill_prompt": None,
        "file_path": file_path,
    }

    # 如果用户在 ext_info 指定了 skill_name，预先匹配技能
    pre_matched_skill = None
    if skill_name:
        pre_matched_skill = registry.get_skill(skill_name)
        if not pre_matched_skill:
            # 大小写不敏感匹配
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    pre_matched_skill = registry.get_skill(s.name)
                    break
        if pre_matched_skill:
            # 把预选技能信息塞进 react_state
            react_state["matched"] = pre_matched_skill
            react_state["skill_prompt"] = pre_matched_skill.get_prompt()
            logger.info(f"Pre-selected skill from ext_info: {skill_name}")

    # 根据是否预选技能构造 skills_context：
    #   预选时只显示该技能，未预选时显示全部技能列表
    if pre_matched_skill:
        # User specified a skill: show only the selected skill
        skills_context = (
            f"- {pre_matched_skill.metadata.name}: "
            f"{pre_matched_skill.metadata.description}"
        )
    else:
        # User did not specify a skill: show all available skills
        skills_context = (
            "\n".join([f"- {s.name}: {s.description}" for s in all_skills])
            if all_skills
            else "No skills available."
        )

    def _mentions_excel(text: str) -> bool:
        """判断用户输入是否提及 Excel 类文件，用于自动选择 Excel 技能。"""
        lowered = text.lower()
        keywords = [
            "excel",
            "xlsx",
            "xls",
            "spreadsheet",
            "workbook",
            "sheet",
            "工作表",
            "表格",
            "电子表格",
        ]
        return any(keyword in lowered for keyword in keywords)

    def _is_excel_skill(meta) -> bool:
        """判断某技能的 metadata 是否表明它是 Excel 类技能。

        通过 name / description / tags 三处匹配关键字。
        """
        name = (meta.name or "").lower()
        desc = (meta.description or "").lower()
        tags = [tag.lower() for tag in (meta.tags or [])]
        return any(
            token in name or token in desc or token in tags
            for token in ["excel", "xlsx", "xls", "spreadsheet"]
        )

    @tool(
        description="Select the most relevant skill based on user query from the "
        "available skills list in system prompt."
    )
    def select_skill(query: str) -> str:
        """根据用户 query 从 system prompt 列出的技能中匹配最相关的一个。

        如果用户已上传文件（file_path 非空），在匹配时附加 Excel 关键词，
        优先匹配 Excel 类技能。若匹配到 Excel 技能但用户既没提 Excel 也没
        上传文件，则视为误匹配，丢弃。

        Args:
            query: 用户问题或意图文本

        Returns:
            chunks JSON：匹配成功时返回技能名 + 描述，失败时返回提示文本
        """
        match_input = query or ""
        # 上传了文件就强制往 Excel 方向走
        if react_state.get("file_path"):
            match_input = f"{match_input} excel xlsx spreadsheet file"
        matched = registry.match_skill(match_input)
        if (
            matched
            and _is_excel_skill(matched.metadata)
            and not (_mentions_excel(query) or react_state.get("file_path"))
        ):
            # 误匹配 Excel 技能：丢弃
            matched = None
        # 把匹配结果写回 react_state，供后续闭包工具读取
        react_state["matched"] = matched
        if matched:
            detail = (
                f"Matched: {matched.metadata.name} - {matched.metadata.description}"
            )
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": detail}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": "No skill matched; proceed without skill",
                    }
                ]
            },
            ensure_ascii=False,
        )

    @tool(
        description="Load skill content by skill name and file path. "
        "Returns the SKILL.md content of the specified skill. "
        '参数: {"skill_name": "技能名称", "file_path": "技能文件路径"}'
    )
    def load_skill(skill_name: str, file_path: str) -> str:
        """根据技能名 + 文件路径加载技能的 SKILL.md 内容。

        Args:
            skill_name: 技能名
            file_path: 技能文件路径（仅用于回显，不参与查找）

        Returns:
            chunks JSON，含技能名、路径、技能正文（markdown 类型）
        """
        from dbgpt.agent.claude_skill import get_registry

        # 优先精确匹配
        registry = get_registry()
        matched = registry.get_skill(skill_name)

        # 失败时尝试大小写不敏感匹配
        if not matched:
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    matched = registry.get_skill(s.name)
                    break

        if not matched:
            # 技能不存在：返回错误提示
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Skill '{skill_name}' not found",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # 同步更新 react_state，让后续工具感知当前技能
        react_state["matched"] = matched
        react_state["skill_prompt"] = matched.get_prompt()

        # 构造返回内容：技能名 / 路径 / 分隔线 / 技能正文
        chunks = [
            {
                "output_type": "text",
                "content": f"Skill: {matched.metadata.name}",
            },
            {
                "output_type": "text",
                "content": f"File path: {file_path}",
            },
            {"output_type": "text", "content": "---"},
        ]

        # 优先用 instructions（SKILL.md 正文），其次 prompt_template
        if matched.instructions:
            chunks.append({"output_type": "markdown", "content": matched.instructions})
        elif matched.prompt_template:
            prompt_text = (
                matched.prompt_template.template
                if hasattr(matched.prompt_template, "template")
                else str(matched.prompt_template)
            )
            chunks.append({"output_type": "markdown", "content": prompt_text})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Load uploaded file info if provided.")
    def load_file() -> str:
        """返回用户上传文件路径信息（若无文件则返回提示）。"""
        if not react_state.get("file_path"):
            # 没有上传文件
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file uploaded"}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {"output_type": "text", "content": react_state["file_path"]},
                    {
                        "output_type": "text",
                        "content": "File path provided by user upload",
                    },
                ]
            },
            ensure_ascii=False,
        )

    @tool(description="Execute quick analysis on uploaded Excel/CSV file.")
    async def execute_analysis() -> str:
        """对用户上传的 Excel/CSV 文件执行快速概览分析。

        生成 pandas 摘要代码并在 code_server 中执行，返回：
          - code：执行的 Python 代码
          - json：shape / columns / dtypes / head(5)
          - table：head(5) 表格
          - chart：取第一个数值列做简单折线图
        """
        matched = react_state.get("matched")
        if not react_state.get("file_path"):
            # 没有文件可分析
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file to analyze"}]},
                ensure_ascii=False,
            )
        if matched and not _is_excel_skill(matched.metadata):
            # 用户选了非 Excel 类技能，跳过 Excel 分析
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Selected skill is not for Excel analysis",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        # 通过 code_server 执行 pandas 摘要脚本
        code_server = await get_code_server(CFG.SYSTEM_APP)
        analysis_code = """
import json
import pandas as pd

file_path = r"{file_path}"
if file_path.lower().endswith((".xls", ".xlsx")):
    df = pd.read_excel(file_path)
else:
    df = pd.read_csv(file_path)
summary = {{
    "shape": list(df.shape),
    "columns": list(df.columns),
    "dtypes": {{col: str(dtype) for col, dtype in df.dtypes.items()}},
    "head": df.head(5).to_dict(orient="records"),
}}
print(json.dumps(summary, ensure_ascii=False))
""".format(file_path=react_state["file_path"])
        result = await code_server.exec(analysis_code, "python")
        output_text = (
            result.output.decode("utf-8") if isinstance(result.output, bytes) else ""
        )
        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": analysis_code.strip()}
        ]
        if output_text:
            try:
                # 解析脚本输出，构造 table / chart chunks
                summary = json.loads(output_text)
                chunks.append({"output_type": "json", "content": summary})
                head_rows = summary.get("head")
                columns = summary.get("columns")
                if isinstance(head_rows, list) and isinstance(columns, list):
                    # table chunk：AntD Table 列定义 + 数据行
                    chunks.append(
                        {
                            "output_type": "table",
                            "content": {
                                "columns": [
                                    {"title": col, "dataIndex": col, "key": col}
                                    for col in columns
                                ],
                                "rows": head_rows,
                            },
                        }
                    )
                # 找出数值列，取第一个做简单折线图
                numeric_columns = [
                    col
                    for col, dtype in (summary.get("dtypes") or {}).items()
                    if "int" in dtype or "float" in dtype
                ]
                if numeric_columns and isinstance(head_rows, list):
                    series_col = numeric_columns[0]
                    data = [
                        {"x": idx + 1, "y": row.get(series_col)}
                        for idx, row in enumerate(head_rows)
                        if row.get(series_col) is not None
                    ]
                    if data:
                        chunks.append(
                            {
                                "output_type": "chart",
                                "content": {
                                    "data": data,
                                    "xField": "x",
                                    "yField": "y",
                                },
                            }
                        )
            except Exception:
                # 解析失败：把原始输出作为文本返回
                chunks.append({"output_type": "text", "content": output_text})
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Resolve required tools for the selected skill.")
    def load_tools() -> str:
        """加载当前技能 metadata 中声明的 required_tools 列表。

        通过 ResourceManager.build_resource_by_type 逐个构造工具资源。
        成功/失败的列表都会以 chunks 形式返回给 LLM。
        """
        matched = react_state.get("matched")
        rm = get_resource_manager(CFG.SYSTEM_APP)
        required_tools = matched.metadata.required_tools if matched else []
        if not required_tools:
            # 技能没有声明 required_tools
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No required tools specified",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        loaded = []
        failed = []
        # 逐个加载
        for tool_name in required_tools:
            try:
                rm.build_resource_by_type(
                    ResourceType.Tool.value,
                    AgentResource(type=ResourceType.Tool.value, value=tool_name),
                )
                loaded.append(tool_name)
            except Exception as e:
                failed.append(f"{tool_name} ({e})")
        chunks = []
        if loaded:
            chunks.append(
                {"output_type": "text", "content": f"Loaded: {', '.join(loaded)}"}
            )
        if failed:
            chunks.append(
                {"output_type": "text", "content": f"Failed: {', '.join(failed)}"}
            )
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Execute a tool by name with JSON args.")
    async def execute_tool(tool_name: str, args: dict) -> str:
        """根据工具名 + JSON args 执行一个工具。

        优先通过 ResourceManager 查找；失败时回退到 ConnectorManager 的
        active packs。同时支持写操作的用户确认流程：
          - 通过 ConnectorManager 的 confirmation interceptor 判断是否需要确认
          - 注册 confirm_id 并等待用户在前端确认（300 秒超时）
          - 用户拒绝时返回取消提示

        Args:
            tool_name: 工具名
            args: 工具参数（dict）

        Returns:
            chunks JSON：成功时返回结果文本，失败时返回错误信息
        """
        try:
            from dbgpt.agent.resource.connector.confirmation import (
                _PENDING_CONFIRMATIONS,
            )
            from dbgpt.agent.resource.connector.manager import (
                ConnectorManager as _ConnectorManager,
            )

            _cm = CFG.SYSTEM_APP.get_component(
                "connector_manager", _ConnectorManager, default_component=None
            )
            if _cm is not None:
                # 写操作确认拦截器
                _interceptor = _cm.get_confirmation_interceptor()
                _registry = _cm.get_confirmation_registry()
                if _interceptor.should_confirm(tool_name, args):
                    # 需要用户确认：注册 confirm_id 并等待
                    import asyncio as _asyncio
                    import uuid as _uuid

                    _confirm_id = str(_uuid.uuid4())
                    _registry.register(_confirm_id)
                    _PENDING_CONFIRMATIONS[_confirm_id] = {
                        "confirm_id": _confirm_id,
                        "tool_name": tool_name,
                        "args_summary": _interceptor._summarize_args(args),
                        "message": f"即将执行写操作 {tool_name}，是否确认？",
                        "timeout": 300,
                    }
                    try:
                        # 等待用户响应（最长 300 秒）
                        _approved = await _asyncio.wait_for(
                            _registry.wait_for(_confirm_id), timeout=300
                        )
                    except _asyncio.TimeoutError:
                        _approved = False
                    finally:
                        _PENDING_CONFIRMATIONS.pop(_confirm_id, None)
                    if not _approved:
                        # 用户拒绝或超时
                        return json.dumps(
                            {
                                "chunks": [
                                    {
                                        "output_type": "text",
                                        "content": "用户拒绝了此操作，工具执行已取消。",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
        except Exception:
            # 拦截器异常不影响工具执行本身
            pass

        # 主路径：通过 ResourceManager 查找工具
        rm = get_resource_manager(CFG.SYSTEM_APP)
        try:
            # Primary path: lookup via ResourceManager (lazy-registered business tools)
            tool_resource = rm.build_resource_by_type(
                ResourceType.Tool.value,
                AgentResource(type=ResourceType.Tool.value, value=tool_name),
            )
            tool_pack = ToolPack([tool_resource])
            result = await tool_pack.async_execute(resource_name=tool_name, **args)
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": str(result)}]},
                ensure_ascii=False,
            )
        except Exception as primary_exc:
            # 回退路径：ResourceManager 找不到时，查 ConnectorManager 的活跃 packs
            # 这处理 LLM 把 MCP connector 工具误路由到 execute_tool 的情况
            # Fallback: if ResourceManager doesn't have the tool, try
            # ConnectorManager active packs.  This handles the case where LLM
            # mistakenly routes an MCP connector tool through execute_tool
            # instead of calling it directly.
            try:
                from dbgpt.agent.resource.connector.manager import (
                    ConnectorManager as _ConnectorManager,
                )

                _cm = CFG.SYSTEM_APP.get_component(
                    "connector_manager",
                    _ConnectorManager,
                    default_component=None,
                )
                if _cm is not None:
                    for _cid, _pack in _cm._active_packs.items():
                        if tool_name in _pack._resources:
                            result = await _pack.async_execute(
                                resource_name=tool_name, **args
                            )
                            logger.info(
                                "execute_tool dispatched '%s' via "
                                "ConnectorManager fallback (connector=%s). "
                                "Prefer direct Action call for connector "
                                "tools.",
                                tool_name,
                                _cid,
                            )
                            return json.dumps(
                                {
                                    "chunks": [
                                        {
                                            "output_type": "text",
                                            "content": str(result),
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            )
            except Exception as fallback_exc:
                # 回退也失败：把双重错误信息返回给 LLM
                logger.warning(
                    "execute_tool fallback to ConnectorManager failed for '%s': %s",
                    tool_name,
                    fallback_exc,
                )
                # When fallback found the tool but execution failed, surface
                # that error to the LLM (more actionable than the
                # ResourceManager primary error)
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Tool execute failed: {fallback_exc} "
                                    f"(primary lookup error: {primary_exc})"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            # 两条路径都没找到：用主路径的错误信息
            # Both lookups returned None — primary path's tool-not-found error wins
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Tool execute failed: {primary_exc}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description="Retrieve relevant information from the knowledge base. "
        "Use this tool when the user question involves content that may be "
        'in the knowledge base. Parameters: {{"query": "search query"}}'
    )
    async def knowledge_retrieve(query: str) -> str:
        """从知识库检索与 query 相关的内容。

        Args:
            query: 检索查询字符串

        Returns:
            chunks JSON：成功时含 text(命中数量) + markdown(检索片段)；
            失败时返回错误信息
        """
        if not knowledge_resources:
            # 未配置知识库
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No knowledge base available",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        resource = knowledge_resources[0]
        try:
            # 调用 retriever 检索
            chunks = await resource.retrieve(query)
            if chunks:
                # 取前 5 条结果，编号展示
                content = "\n".join(
                    [f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks[:5])]
                )
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Retrieved {len(chunks)} relevant documents"
                                ),
                            },
                            {"output_type": "markdown", "content": content},
                        ]
                    },
                    ensure_ascii=False,
                )
            else:
                # 无命中
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": "No relevant information found",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Knowledge retrieval failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description=(
            "对用户选择的数据库执行 SQL 查询（仅支持 SELECT）。"
            '参数: {"sql": "SELECT 语句"}'
        )
    )
    def sql_query(sql: str) -> str:
        """对用户选中的数据库执行只读 SQL（仅 SELECT）。

        安全策略：
          - 拒绝 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE/GRANT/REVOKE
          - 截断到前 50 行，避免结果过大撑爆 LLM 上下文

        Args:
            sql: SQL 语句字符串

        Returns:
            chunks JSON：成功时返回 markdown 表格；失败时返回错误文本
        """
        if database_connector is None:
            # 未选择数据库
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # 预处理 SQL：去尾分号、取大写
        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper().lstrip()
        # 危险关键字白名单
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
        ]
        for kw in forbidden:
            if sql_upper.startswith(kw):
                # 命中危险关键字：拒绝执行
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"安全限制: 不允许执行 {kw} 语句，"
                                    f"仅支持 SELECT 查询。"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            # 实际执行 SQL
            result = database_connector.run(sql_stripped)
            if not result:
                # 空结果
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ]
                    },
                    ensure_ascii=False,
                )

            # result[0] = column names, result[1:] = data rows
            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = result[1:]

            # 构造 markdown 表格
            header = "| " + " | ".join(col_names) + " |"
            separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
            md_rows = []
            # 截断到前 50 行
            for row in rows[:50]:
                md_rows.append("| " + " | ".join(str(v) for v in row) + " |")
            table = "\n".join([header, separator] + md_rows)
            if len(rows) > 50:
                table += f"\n\n（仅显示前 50 行，共 {len(rows)} 行）"

            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
        except Exception as e:
            # SQL 执行异常
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"SQL 执行失败: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    def _try_repair_truncated_code(raw_code: str) -> Optional[str]:
        """尝试修复被 LLM token 上限截断的代码。

        常见症状：字符串字面量未闭合、括号/小括号未配对。
        策略：
          1. 逐步移除尾部若干行（最多 10 行），找到干净截断点
          2. 闭合所有未匹配的括号
          3. 重新 compile；通过则返回修复后的代码

        Args:
            raw_code: 原始（可能截断的）Python 代码

        Returns:
            修复后的代码字符串；无法修复时返回 None
        """

        lines = raw_code.split("\n")
        # Try progressively removing trailing lines (up to 10) to find a
        # clean cut-off point.
        for trim in range(1, min(11, len(lines))):
            candidate_lines = lines[: len(lines) - trim]
            if not candidate_lines:
                continue
            candidate = "\n".join(candidate_lines)

            # Strip any trailing incomplete string by trying to tokenize
            # and removing broken tail tokens.
            # Close unmatched brackets/parens/braces
            open_chars = {"(": ")", "[": "]", "{": "}"}
            close_chars = set(open_chars.values())
            stack: list = []
            for ch in candidate:
                if ch in open_chars:
                    stack.append(open_chars[ch])
                elif ch in close_chars:
                    if stack and stack[-1] == ch:
                        stack.pop()

            # Append closing chars in reverse order
            if stack:
                candidate += "\n" + "".join(reversed(stack))

            try:
                # 通过 compile 验证修复后的代码语法合法
                compile(candidate, "<repair>", "exec")
                return candidate
            except SyntaxError:
                continue
        return None

    @tool(
        description="Execute Python code for data analysis and computation. "
        "Supports pandas, numpy, matplotlib, json, os, etc. "
        "Use this tool when you need to run Python code to process data, "
        "generate charts, or perform calculations. "
        'Parameters: {{"code": "python code string"}}'
    )
    async def code_interpreter(code: str) -> str:
        """执行任意 Python 代码并返回 stdout/stderr。

        使用项目 Python 解释器在子进程中执行，pandas/numpy 等已安装包都可用。
        关键约束：每次调用相互独立，变量不持久化。每个代码片段必须自己加载数据。
        """
        import asyncio
        import shutil
        import sys
        import uuid

        from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH

        if not code or not code.strip():
            # 空代码直接返回提示
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No code provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # 使用持久化工作目录 pilot/tmp/{conv_id}，文件跨调用可复用
        # Use persistent work dir under pilot/tmp/{conv_id} so files
        # survive across calls and can be referenced later (e.g. in HTML).
        cid = react_state.get("conv_id") or "default"
        work_dir = os.path.join(PILOT_PATH, "tmp", cid)
        os.makedirs(work_dir, exist_ok=True)

        # 记录本次运行前已存在的图片，用于区分本次新生成的图片
        # Collect image files that existed BEFORE this run
        IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        pre_existing_images: set = set()
        for root, _dirs, files in os.walk(work_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    pre_existing_images.add(os.path.join(root, f))

        # 构造前导代码：导入常用库 + 设置工作目录常量
        preamble_lines = [
            "import json",
            "import os",
            "import pandas as pd",
            "import numpy as np",
            f'PLOT_DIR = r"{work_dir}"',
            "os.makedirs(PLOT_DIR, exist_ok=True)",
        ]
        fp = react_state.get("file_path")
        if fp:
            # 把上传文件路径暴露为 FILE_PATH 常量
            preamble_lines.append(f'FILE_PATH = r"{fp}"')
        preamble = "\n".join(preamble_lines) + "\n"
        full_code = preamble + code

        try:
            # 先 compile 检查语法
            compile(full_code, "<code_interpreter>", "exec")
        except SyntaxError as se:
            # 语法错误：可能是 LLM 输出被 token 上限截断，尝试自动修复
            # Attempt auto-repair for truncated code (common with long LLM
            # outputs that hit the token limit).
            repaired = _try_repair_truncated_code(full_code)
            if repaired is not None:
                logger.warning(
                    "code_interpreter: auto-repaired truncated code "
                    f"(original SyntaxError: {se.msg} line {se.lineno})"
                )
                full_code = repaired
                # 修复后从 full_code 中剥出 code 部分用于展示
                code = full_code[len(preamble) :]
            else:
                # 修复失败：把错误返回给 LLM，提示它重新生成
                error_msg = (
                    f"SyntaxError before execution: {se.msg} "
                    f"(line {se.lineno})\n"
                    "Please regenerate complete, syntactically valid Python "
                    "code. Keep code under 80 lines and split long tasks "
                    "into multiple code_interpreter calls."
                )
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "code", "content": code.strip()},
                            {"output_type": "text", "content": error_msg},
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            # 把完整代码写到 _run.py，然后子进程执行
            tmp_path = os.path.join(work_dir, "_run.py")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                tmp.write(full_code)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            # 60 秒超时
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output_text = stdout.decode("utf-8", errors="replace")
            error_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and error_text:
                # 非零退出：把 stderr 拼到 stdout 后
                output_text = (
                    output_text + "\n[ERROR]\n" + error_text
                    if output_text
                    else error_text
                )
        except asyncio.TimeoutError:
            output_text = "Execution timed out (60s limit)"
        except Exception as e:
            output_text = f"Execution error: {e}"

        # 构造 chunks：第一个永远是 code（前端左侧代码栏）
        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            clean_output = output_text.strip()
            # 截断到 2000 字符，避免撑爆 LLM 上下文
            max_out_len = 2000
            if len(clean_output) > max_out_len:
                truncation_notice = (
                    f"\n\n... [Output truncated, length: {len(clean_output)} chars."
                    f" Only showing first {max_out_len} chars."
                    f" If you generated HTML, the file is saved.]"
                )
                clean_output = clean_output[:max_out_len] + truncation_notice
            chunks.append({"output_type": "text", "content": clean_output})
        else:
            # 无输出：提示 LLM 加 print
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output — add print() to see results)",
                }
            )

        # 扫描工作目录，把本次新生成的图片拷贝到静态目录并构造 image chunks
        # Scan work_dir recursively for NEW image files generated by this run
        try:
            os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    full_path = os.path.join(root, fname)
                    # 只处理本次新生成的图片（不在 pre_existing_images 中）
                    if ext in IMAGE_EXTS and full_path not in pre_existing_images:
                        # 用 uuid 前缀重命名，避免冲突
                        unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                        dest = os.path.join(STATIC_MESSAGE_IMG_PATH, unique_name)
                        shutil.copy2(full_path, dest)
                        img_url = f"/images/{unique_name}"
                        chunks.append(
                            {
                                "output_type": "image",
                                "content": img_url,
                            }
                        )
                        # 把生成的图片 URL 记到 react_state，
                        # 供 html_interpreter 后续引用
                        # Track generated images in react_state for
                        # html_interpreter to reference later
                        react_state.setdefault("generated_images", []).append(img_url)
        except Exception:
            # 图片扫描失败不影响主流程
            pass

        # 清理临时脚本文件，保留 work_dir 持久化
        # Clean up the temp script file but keep work_dir for persistence
        try:
            script_path = os.path.join(work_dir, "_run.py")
            if os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass

        # 末尾追加一张本轮所有生成图片的清单，方便 LLM 在生成 HTML 时引用
        # Append a summary of ALL generated images so far, so the LLM
        # has a clear reference when generating HTML later.
        all_images = react_state.get("generated_images", [])
        if all_images:
            img_summary = "已生成的图片URL（在生成HTML时请使用这些URL）:\n" + "\n".join(
                f"  - {url}" for url in all_images
            )
            chunks.append({"output_type": "text", "content": img_summary})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="Execute shell/bash commands in a sandboxed environment. "
        "Use this tool when you need to run shell commands such as ls, cat, "
        "grep, curl, apt, pip, git, or any other CLI tool. "
        "The sandbox provides resource limits (256MB memory, 30s timeout) "
        "and process isolation. "
        'Parameters: {"code": "shell command(s) to execute"}'
    )
    async def shell_interpreter(code: str) -> str:
        """在沙箱中执行 shell/bash 命令。

        使用 dbgpt-sandbox 的 LocalRuntime 执行 bash 脚本：
          - 内存上限 256MB
          - 超时 30 秒
          - 进程树管理（超时/出错时清理）
          - 安全校验（拦截 `rm -rf /` 等危险模式）
        每次调用相互独立，不保留状态。
        """
        import uuid

        if not code or not code.strip():
            # 空命令直接返回
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No command provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            from dbgpt_sandbox.sandbox.execution_layer.base import (
                ExecutionStatus,
                SessionConfig,
            )
            from dbgpt_sandbox.sandbox.execution_layer.local_runtime import (
                LocalRuntime,
            )
        except ImportError:
            # 沙箱未安装：返回安装提示
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "code", "content": code.strip()},
                        {
                            "output_type": "text",
                            "content": (
                                "Error: dbgpt-sandbox package is not installed. "
                                "Please install it with: pip install dbgpt-sandbox"
                            ),
                        },
                    ]
                },
                ensure_ascii=False,
            )

        # 创建 sandbox 会话
        session_id = f"bash_{uuid.uuid4().hex[:12]}"
        runtime = LocalRuntime()

        from dbgpt.configs.model_config import ROOT_PATH

        # 工作目录设为项目根目录
        sandbox_work_dir = ROOT_PATH
        os.makedirs(sandbox_work_dir, exist_ok=True)

        # 沙箱配置：bash、256MB、30s 超时
        config = SessionConfig(
            language="bash",
            working_dir=sandbox_work_dir,
            max_memory=256 * 1024 * 1024,  # 256MB
            timeout=30,
        )

        output_text = ""
        try:
            session = await runtime.create_session(session_id, config)
            result = await session.execute(code)

            # 根据执行状态组装输出
            if result.status == ExecutionStatus.SUCCESS:
                output_text = result.output or ""
            elif result.status == ExecutionStatus.TIMEOUT:
                output_text = f"Execution timed out ({config.timeout}s limit)"
            else:
                # 其他失败：把 output + error 拼起来
                output_text = result.error or "Unknown execution error"
                if result.output:
                    output_text = result.output + "\n[ERROR]\n" + output_text
        except Exception as e:
            output_text = f"Sandbox execution error: {e}"
        finally:
            # 销毁会话释放资源
            try:
                await runtime.destroy_session(session_id)
            except Exception:
                pass

        # 第一个 chunk 永远是执行的代码
        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            chunks.append({"output_type": "text", "content": output_text.strip()})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output)",
                }
            )

        # ── 安全网后处理：技能脚本执行兜底 ──
        # 即便 prompt 要求用 execute_skill_script_file，LLM 仍可能用
        # shell_interpreter 跑技能脚本。这里捕获关键副作用（ratio_data、
        # images）写入 react_state，保证 html_interpreter 仍能引用。
        # ── Safety-net post-processing for skill script execution ──
        # If the LLM used shell_interpreter to run a skill script despite
        # the prompt requesting execute_skill_script_file, we still capture
        # critical side-effects (ratio_data, images) into react_state.
        _code_lower = code.strip().lower()
        _is_skill_script = "skills/" in _code_lower and ".py" in _code_lower
        if _is_skill_script and output_text.strip():
            import shutil

            from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

            # 1) 捕获 calculate_ratios.py 的输出作为 ratio_data
            # 1) Capture calculate_ratios.py output as ratio_data
            if "calculate_ratios" in _code_lower:
                try:
                    ratio_data = json.loads(output_text.strip())
                    if isinstance(ratio_data, dict):
                        react_state["ratio_data"] = ratio_data
                        logger.info(
                            "shell_interpreter: captured %d ratio_data keys",
                            len(ratio_data),
                        )
                except Exception:
                    pass

            # 2) 捕获 generate_charts.py 的输出：找出图片路径，
            #    拷贝到静态目录，行为与 execute_skill_script_file 一致
            # 2) Capture generate_charts.py output — look for image paths
            #    and copy them to static dir, same as execute_skill_script_file
            if "generate_charts" in _code_lower:
                try:
                    os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                    # 优先解析 JSON 输出找图片路径
                    # Try to parse JSON output for image paths
                    try:
                        chart_output = json.loads(output_text.strip())
                        if isinstance(chart_output, dict):
                            # 可能是 {"charts": {...}} 或扁平 dict
                            # Might be {"charts": {...}} or flat dict
                            chart_map = chart_output.get("charts", chart_output)
                            for name, abs_path in chart_map.items():
                                if isinstance(abs_path, str) and os.path.isfile(
                                    abs_path
                                ):
                                    ext = os.path.splitext(abs_path)[1].lower()
                                    if ext in IMAGE_EXTS:
                                        # 拷贝到静态目录并记到 image_url_map
                                        unique_name = (
                                            f"{uuid.uuid4().hex[:8]}_"
                                            f"{os.path.basename(abs_path)}"
                                        )
                                        dest = os.path.join(
                                            STATIC_MESSAGE_IMG_PATH, unique_name
                                        )
                                        shutil.copy2(abs_path, dest)
                                        img_url = f"/images/{unique_name}"
                                        react_state.setdefault(
                                            "generated_images", []
                                        ).append(img_url)
                                        orig_stem = os.path.splitext(
                                            os.path.basename(abs_path)
                                        )[0].lower()
                                        react_state.setdefault("image_url_map", {})[
                                            orig_stem
                                        ] = img_url
                    except (json.JSONDecodeError, TypeError):
                        pass
                    # 兜底：扫描输出目录，找新增的 .png 等图片
                    # Also scan the output dir for any new .png files
                    cid = react_state.get("conv_id") or "default"
                    from dbgpt.configs.model_config import PILOT_PATH

                    out_dir = os.path.join(PILOT_PATH, "tmp", cid)
                    if os.path.isdir(out_dir):
                        for fname in os.listdir(out_dir):
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in IMAGE_EXTS:
                                abs_path = os.path.join(out_dir, fname)
                                orig_stem = os.path.splitext(fname)[0].lower()
                                # 跳过已记录的
                                if orig_stem not in react_state.get(
                                    "image_url_map", {}
                                ):
                                    unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                                    dest = os.path.join(
                                        STATIC_MESSAGE_IMG_PATH, unique_name
                                    )
                                    shutil.copy2(abs_path, dest)
                                    img_url = f"/images/{unique_name}"
                                    react_state.setdefault(
                                        "generated_images", []
                                    ).append(img_url)
                                    react_state.setdefault("image_url_map", {})[
                                        orig_stem
                                    ] = img_url
                    # 追加图片 URL 清单，供 LLM 引用
                    # Append image URL summary for LLM reference
                    all_images = react_state.get("generated_images", [])
                    if all_images:
                        img_summary = (
                            "\u5df2\u751f\u6210\u7684\u56fe\u7247URL\uff08\u5728\u751f\u6210HTML\u62a5\u544a\u65f6\u8bf7\u4f7f\u7528\u8fd9\u4e9bURL\uff09:\n"
                            + "\n".join(f"  - {url}" for url in all_images)
                        )
                        chunks.append({"output_type": "text", "content": img_summary})
                    logger.info(
                        "shell_interpreter: captured %d images for skill script",
                        len(react_state.get("image_url_map", {})),
                    )
                except Exception as e:
                    # 后处理失败不影响已生成的 chunks
                    logger.warning(
                        "shell_interpreter: image post-processing failed: %s", e
                    )

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(  # 使用 @tool 装饰器注册为 agent 可调用的工具
        description="执行技能scripts目录下的脚本文件。参数: "  # 工具描述（LLM 据此决定是否调用）
        '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
    )
    async def execute_skill_script_file(  # 闭包版同名工具，比模块级版本增强：图片后处理 + auto_data 提取
        skill_name: str, script_file_name: str, args: Optional[dict] = None
    ) -> str:
        """Execute a script file from a skill's scripts directory.

        After execution, any new image files (.png, .jpg, etc.) generated
        by the script are automatically copied to the static images directory
        and their URLs are returned in the output chunks.
        """
        import shutil  # 用于拷贝生成的图片文件到静态目录
        import uuid  # 用于生成唯一文件名前缀，避免图片重名

        from dbgpt.agent.skill.manage import get_skill_manager  # 技能管理器（用于执行脚本）
        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH  # 静态图片服务目录

        try:
            from dbgpt.configs.model_config import PILOT_PATH  # DB-GPT 根路径

            sm = get_skill_manager(CFG.SYSTEM_APP)  # 获取全局技能管理器实例
            cid = react_state.get("conv_id") or "default"  # 当前会话 ID
            out_dir = os.path.join(PILOT_PATH, "tmp", cid)  # 每个会话独立输出目录
            os.makedirs(out_dir, exist_ok=True)  # 确保输出目录存在
            # Auto-inject the correct file path from react_state into args.
            # The LLM sometimes corrupts the uploaded file path (e.g. changing
            # 'dbgpt-app' to 'dbgpt_app'), so we override any file-path-like
            # keys in args with the known-good path from react_state.
            real_file_path = react_state.get("file_path")  # 从会话状态读取真实上传路径
            if real_file_path and args:  # 如果有真实路径且 LLM 传了参数
                _FILE_PATH_KEYS = {  # 所有可能的文件路径参数键名
                    "input_file",
                    "file_path",
                    "data_path",
                    "csv_path",
                    "excel_path",
                    "data_file",
                }
                for key in list(args.keys()):  # 遍历 LLM 传入的参数键
                    if key in _FILE_PATH_KEYS:  # 如果是文件路径类参数
                        args[key] = real_file_path  # 强制覆盖为会话状态中的真实路径
            result_str = await sm.execute_skill_script_file(  # 调用技能管理器执行脚本
                skill_name,
                script_file_name,
                args or {},
                output_dir=out_dir,  # 脚本输出文件落到会话独立目录
            )

            # Read script source code and prepend as a 'code' chunk
            # so the frontend can display it in the left pane.
            try:  # 尝试读取脚本源码（前端左面板展示用）
                _skill_path = sm._get_skill_path(skill_name)  # 获取技能根目录
                _sf = script_file_name.lstrip("/\\")  # 去掉前导斜杠
                if _sf.startswith("scripts/") or _sf.startswith("scripts\\"):  # 如果带了 scripts/ 前缀
                    _sf = _sf[8:]  # 去掉 scripts/ 前缀
                _script_abs = os.path.join(_skill_path, "scripts", _sf)  # 拼出脚本绝对路径
                with open(_script_abs, "r", encoding="utf-8") as _f:  # 读取脚本源码
                    _script_source = _f.read()
            except Exception:  # 读取失败时回退为 None
                _script_source = None

            # Post-process: copy image files to static dir and replace
            # absolute paths with /images/ URLs.
            try:  # 后处理：拷贝图片 + 替换路径 + 提取 auto_data
                result_obj = json.loads(result_str)  # 解析脚本返回的 JSON
                chunks = result_obj.get("chunks", [])  # 取出 chunks 列表
                # Prepend script source code as a 'code' chunk
                if _script_source:  # 如果成功读到脚本源码
                    chunks.insert(  # 把源码插入到 chunks 最前面作为 code 块
                        0,
                        {
                            "output_type": "code",
                            "content": _script_source,
                        },
                    )
                os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)  # 确保静态图片目录存在
                IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}  # 支持的图片扩展名
                for chunk in chunks:  # 遍历每个 chunk
                    if chunk.get("output_type") == "image":  # 如果是图片类型
                        abs_path = chunk["content"]  # 取出图片绝对路径
                        if os.path.isabs(abs_path) and os.path.isfile(abs_path):  # 校验是存在的绝对路径文件
                            ext = os.path.splitext(abs_path)[1].lower()  # 取扩展名
                            if ext in IMAGE_EXTS:  # 是支持的图片扩展名
                                unique_name = (  # 生成唯一文件名：8 位 hex + 原文件名
                                    f"{uuid.uuid4().hex[:8]}_"
                                    f"{os.path.basename(abs_path)}"
                                )
                                dest = os.path.join(  # 目标路径 = 静态目录 + 唯一文件名
                                    STATIC_MESSAGE_IMG_PATH, unique_name
                                )
                                shutil.copy2(abs_path, dest)  # 拷贝（保留元数据）
                                img_url = f"/images/{unique_name}"  # 构造可访问的 URL
                                chunk["content"] = img_url  # 把 chunk 内容替换为 URL
                                react_state.setdefault("generated_images", []).append(  # 记录到会话状态
                                    img_url
                                )
                                # Also store a map: original filename (no ext)
                                # -> served URL for template placeholder
                                # resolution.
                                orig_stem = os.path.splitext(  # 取原始文件名（不含扩展名）
                                    os.path.basename(abs_path)
                                )[0].lower()
                                react_state.setdefault("image_url_map", {})[  # 建立 stem -> URL 映射
                                    orig_stem
                                ] = img_url

                # Append image URL summary for LLM reference
                all_images = react_state.get("generated_images", [])  # 取出会话内已生成的全部图片
                if all_images:  # 如果有图片
                    img_summary = (  # 拼一份图片清单文本，供 LLM 在后续生成 HTML 时引用
                        "已生成的图片URL（在生成HTML报告时请使用这些URL）:\n"
                        + "\n".join(f"  - {url}" for url in all_images)
                    )
                    chunks.append({"output_type": "text", "content": img_summary})  # 追加为 text chunk
                auto_data = react_state.get("auto_data")  # 取出会话状态中的 auto_data
                if not isinstance(auto_data, dict):  # 如果还不是 dict（首次或脏数据）
                    auto_data = {}  # 初始化为空 dict
                    react_state["auto_data"] = auto_data  # 写回会话状态
                filtered_chunks = []  # 过滤后的 chunks（去掉 auto_data 标记文本）
                for chunk in chunks:  # 遍历所有 chunk
                    if chunk.get("output_type") != "text":  # 非 text 直接保留
                        filtered_chunks.append(chunk)
                        continue
                    content = chunk.get("content") or ""  # 取 text 内容
                    cleaned, extracted = _extract_auto_data_markers(content)  # 提取 [[AUTO_DATA:KEY]]=value 标记
                    if extracted:  # 如果提取到 auto_data
                        auto_data.update(extracted)  # 合并到会话状态
                        logger.info(  # 记录提取到的键
                            "execute_skill_script_file: captured auto_data keys=%s",
                            sorted(extracted.keys()),
                        )
                    if cleaned:  # 如果清理后还有文本
                        chunk["content"] = cleaned  # 用清理后的内容替换
                        filtered_chunks.append(chunk)
                    elif not extracted:  # 既无清理文本又无提取内容（纯空 chunk）
                        filtered_chunks.append(chunk)  # 保留原 chunk
                chunks = filtered_chunks  # 用过滤结果替换

                # Compatibility path for existing financial-report skill.
                if script_file_name == "calculate_ratios.py":  # 财报技能兼容路径
                    for chunk in chunks:  # 遍历 chunks 寻找 text 内容
                        if chunk.get("output_type") == "text":
                            try:
                                ratio_data = json.loads(chunk["content"])  # 尝试解析为 JSON
                                react_state["ratio_data"] = ratio_data  # 保存到 ratio_data 字段
                            except Exception:  # 非 JSON 直接跳过
                                pass
                return json.dumps({"chunks": chunks}, ensure_ascii=False)  # 返回 JSON 字符串
            except (json.JSONDecodeError, KeyError):  # JSON 解析失败或字段缺失
                return result_str  # 直接返回原始字符串（不做后处理）
        except Exception as e:  # 顶层异常兜底
            return json.dumps(  # 返回错误 chunk
                {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
                ensure_ascii=False,
            )

    @tool(  # @tool 装饰器：注册为 agent 可调用的 HTML 渲染工具
        description="将 HTML 渲染为可交互的网页报告，这是向用户展示网页报告的唯一方式。"  # 工具说明（向 LLM 描述）
        "【默认用法】直接传入完整的 HTML 字符串："
        '{"html": "<html>...</html>", "title": "报告标题"}。'
        "你需要自己生成完整的 HTML 代码"
        "（包含 <!DOCTYPE html>、<html>、<head>、<body> 等），"
        "然后传给 html 参数即可。"
        "HTML 可以很长，没有长度限制，不需要分段传入。"
        "【禁止】不要用 code_interpreter 写 HTML 再 print，"
        "不要用 code_interpreter 把 HTML 写入文件再读取，"
        "直接把 HTML 传给本工具即可。"
        "【技能模式 - 仅在使用技能时可选】如果正在使用技能（skill），可以用模板模式："
        '{"template_path": "技能名/templates/模板.html", '
        '"data": {"KEY": "值"}, "title": "标题"}。'
        '也可以用文件模式：{"file_path": "/path/to/report.html"}'
    )
    async def html_interpreter(  # 闭包版 HTML 渲染工具，支持 3 种输入模式
        html: str = "",
        title: str = "Report",
        file_path: str = "",
        template_path: str = "",
        data: dict | str = None,
    ) -> str:
        """Render HTML as an interactive web report.

        Default usage: pass a complete HTML string via the `html` parameter.
        The HTML can be arbitrarily long — no length limit, no chunking needed.

        Skill template mode (optional): pass `template_path` (relative to skills
        dir) plus a `data` dict whose keys match {{PLACEHOLDER}} tokens in the
        template. The backend reads the template and performs all replacements.

        Legacy fallback: `file_path` reads HTML from a file on disk.
        """
        import re  # 正则表达式，用于占位符替换与图片路径修正

        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH  # 静态图片目录

        # ── Mode 1: template_path + data ──────────────────────────────
        # 模式 1：技能模板模式（template_path + data）
        if template_path and template_path.strip():  # 如果传了 template_path
            tp = template_path.strip()  # 去除前后空白
            skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()  # 技能根目录绝对路径
            target = (skills_dir / tp).resolve()  # 拼出模板文件绝对路径
            # Security: must be under skills_dir
            # 安全检查：模板路径必须在 skills_dir 之下，防止路径穿越
            try:
                target.relative_to(skills_dir)  # 如果能算出相对路径说明在 skills_dir 下
            except ValueError:  # 否则抛 ValueError
                return json.dumps(  # 返回错误 chunk
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Invalid template_path: {tp}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            if not target.is_file():  # 如果模板文件不存在
                return json.dumps(  # 返回错误并提示改用 html 参数
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Template not found: {tp}. "
                                    "This skill does not have HTML templates. "
                                    "Please retry by calling html_interpreter "
                                    "with the `html` parameter instead — "
                                    "generate the complete HTML report code "
                                    "yourself and pass it directly via "
                                    '{"html": "<html>...</html>", '
                                    '"title": "report title"}.'
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            try:
                raw_template = target.read_text(encoding="utf-8")  # 读取模板原始内容
            except Exception as e:
                return json.dumps(  # 读取失败时返回错误
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading template: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            # Replace {{KEY}} placeholders with values from data dict
            # Sometimes the LLM passes data as a JSON string instead of a dict
            replacements = data  # 取出 LLM 传入的 data 参数
            if isinstance(replacements, str):  # LLM 可能传 JSON 字符串而非 dict
                try:
                    replacements = json.loads(replacements)  # 尝试解析为 dict
                except Exception as e:
                    logger.warning(  # 解析失败告警
                        f"html_interpreter failed to parse string data as json: {e}"
                    )
                    # Attempt to fix truncated JSON by appending closing
                    # braces/quotes
                    # 尝试修复被截断的 JSON：补齐闭合的引号和大括号
                    try:
                        fixed = str(replacements).rstrip()  # 去掉末尾空白
                        if not fixed.endswith("}"):  # 如果没有以 } 结尾
                            if fixed.endswith('"'):  # 如果末尾是引号
                                fixed += "}"  # 补 }
                            else:  # 否则补 "}
                                fixed += '"}'
                        replacements = json.loads(fixed)  # 再次尝试解析
                    except Exception:
                        replacements = {}  # 仍失败则用空 dict
            if not isinstance(replacements, dict):  # 不是 dict 就重置
                replacements = {}
            auto_data = react_state.get("auto_data", {})  # 取会话状态中的 auto_data
            if isinstance(auto_data, dict):
                replacements = {**auto_data, **replacements}  # auto_data 作为底层，LLM data 覆盖

            # Merge LLM replacements with ratio_data from calculate_ratios.py
            # 与 calculate_ratios.py 产出的 ratio_data 合并（财报技能兼容）
            ratio_data = react_state.get("ratio_data", {})
            if isinstance(ratio_data, dict):
                # auto_data / LLM data overwrites ratio_data if keys overlap
                # 优先级：auto_data / LLM data > ratio_data（key 冲突时前者覆盖后者）
                merged = {**ratio_data, **replacements}
                replacements = merged

            # Auto-resolve CHART_* placeholders from generated images.
            # 自动把图片映射成 CHART_STEM 占位符（HTML 模板里用 {{CHART_XXX}} 引用）
            # image_url_map: {
            #     "financial_overview": "/images/abc_financial_overview.png"
            # }
            # Template uses:
            #     {{CHART_FINANCIAL_OVERVIEW}}
            #     -> /images/abc_financial_overview.png
            image_url_map = react_state.get("image_url_map", {})  # 取图片 stem -> URL 映射
            if isinstance(image_url_map, dict):
                for stem, url in image_url_map.items():  # 遍历每个图片
                    chart_key = f"CHART_{stem.upper()}"  # 构造 {{CHART_STEM}} 形式的占位符 key
                    if chart_key not in replacements:  # LLM 没显式覆盖时才注入
                        replacements[chart_key] = url

            def _replace_placeholder(m):  # 占位符替换回调：{{KEY}} -> replacements[KEY]
                key = m.group(1)
                return str(replacements.get(key, ""))

            html = re.sub(r"\{\{([A-Z_0-9]+)\}\}", _replace_placeholder, raw_template)  # 执行 {{KEY}} 替换
            if not title or title == "Report":  # 如果没有传 title
                title = target.stem  # 用模板文件名作为标题
            logger.info(  # 记录模板模式执行情况
                "html_interpreter: template=%s, %d placeholders replaced, "
                "html=%d chars",
                tp,
                len(replacements),
                len(html),
            )

        # ── Mode 2: file_path ─────────────────────────────────────────
        # 模式 2：file_path 模式（从磁盘读 HTML 文件）
        elif file_path and file_path.strip():
            fp = file_path.strip()  # 去掉前后空白
            if not os.path.isfile(fp):  # 如果主路径不存在，尝试会话独立目录
                cid = react_state.get("conv_id") or "default"
                from dbgpt.configs.model_config import PILOT_PATH

                alt = os.path.join(PILOT_PATH, "data", cid, os.path.basename(fp))  # 会话目录下的同名文件
                if os.path.isfile(alt):  # 如果会话目录下有
                    fp = alt  # 切换到会话目录文件
                else:
                    return json.dumps(  # 找不到时返回错误
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": f"File not found: {file_path}",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
            try:
                with open(fp, "r", encoding="utf-8") as f:  # 读取 HTML 文件
                    html = f.read()
                if not title or title == "Report":  # 默认用文件名作为标题
                    title = os.path.splitext(os.path.basename(fp))[0]
                logger.info(  # 记录读取情况
                    "html_interpreter: read %d chars from file %s",
                    len(html),
                    fp,
                )
            except Exception as e:
                return json.dumps(  # 读取失败时返回错误
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading file: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        # ── Mode 3: inline html ──────────────────────────────────────
        # 模式 3：内联 HTML 模式（默认模式，LLM 直接传 html 字符串）
        # Unescape literal \n sequences that LLM may produce.
        # IMPORTANT: Only apply this unescape when html was provided directly
        # (inline mode).  Template mode (Mode 1) and file mode (Mode 2) produce
        # real HTML that already contains actual newlines and may contain JS
        # regex literals like /\\n/ which must NOT be collapsed into real
        # newlines — doing so corrupts the JS and breaks chart rendering.
        # 注意：只在 inline 模式下做 \n -> 换行符的还原；模板模式和文件模式产生的
        # HTML 已包含真实换行符，且可能含 JS 正则字面量（如 /\n/），不能替换，
        # 否则会破坏 JS、导致图表无法渲染。
        if html and isinstance(html, str) and not template_path and not file_path:  # 仅 inline 模式
            if "\\n" in html:  # 如果包含字面 \n
                html = html.replace("\\n", "\n")  # 替换为真实换行
            if "\\t" in html:  # 如果包含字面 \t
                html = html.replace("\\t", "\t")  # 替换为真实制表符
        if not html or not html.strip():  # 校验非空
            return json.dumps(  # 空内容返回错误
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No HTML content provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Post-process: fix image URLs that the LLM may have guessed wrong.
        # 后处理：修正 LLM 猜错的图片 URL（自动用静态目录里实际存在的文件名替换）
        # Files in STATIC_MESSAGE_IMG_PATH are named "{uuid8}_{original}.ext".
        # The LLM might reference "/images/original.ext" (without UUID prefix)
        # or even just "original.ext".  Build a lookup and replace.
        fixed_html = html.strip()  # 去掉首尾空白
        try:
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}  # 支持的图片扩展名
            # Map: lowercase base name (without uuid prefix) -> served path
            # e.g. "monthly_sales_trend.png"
            #      -> "/images/a1b2c3ff_monthly_sales_trend.png"
            name_to_served: Dict[str, str] = {}  # 文件名（去 UUID 前缀） -> 服务端路径 的映射
            if os.path.isdir(STATIC_MESSAGE_IMG_PATH):  # 静态目录存在时才扫描
                for fname in os.listdir(STATIC_MESSAGE_IMG_PATH):  # 遍历目录下文件
                    ext = os.path.splitext(fname)[1].lower()  # 取扩展名
                    if ext not in IMAGE_EXTS:  # 非图片跳过
                        continue
                    # Strip the 8-char hex UUID prefix + underscore
                    # Pattern: <8 hex chars>_<original_name>
                    m = re.match(r"^[0-9a-f]{8}_(.+)$", fname, re.IGNORECASE)  # 匹配 UUID 前缀
                    if m:
                        base_name = m.group(1).lower()  # 取出原文件名
                        served_path = f"/images/{fname}"  # 构造 URL
                        # Keep the latest (last alphabetically = most recent
                        # UUID)
                        name_to_served[base_name] = served_path  # 写入映射（后覆盖前 = 最新）

            if name_to_served:  # 如果有可用映射
                # Replace patterns like:
                #   src="/images/monthly_sales_trend.png"
                #   src="images/monthly_sales_trend.png"
                #   src="monthly_sales_trend.png"
                # with the correct served path.
                def _fix_img_src(match: re.Match) -> str:  # 正则替换回调：修正单个 src="..."
                    prefix = match.group(1)  # src=" or src='  # 前缀（含引号）
                    raw_path = match.group(2)  # the path value  # 原始路径
                    quote = match.group(3)  # closing quote  # 闭合引号

                    # Extract just the filename from the path
                    filename = raw_path.rsplit("/", 1)[-1].lower()  # 只取文件名部分

                    # Check if it's already a correct served path
                    if re.match(r"^[0-9a-f]{8}_.+$", filename, re.IGNORECASE):  # 已带 UUID 前缀
                        return match.group(0)  # Already has UUID prefix  # 不需要修正

                    if filename in name_to_served:  # 命中映射
                        return f"{prefix}{name_to_served[filename]}{quote}"  # 返回修正后的 src
                    return match.group(0)  # No match, keep original  # 未命中，保留原样

                # Match src="..." or src='...' containing image references
                # 正则匹配 src="xxx.png" / src='xxx.png' 等
                fixed_html = re.sub(
                    r"""(src\s*=\s*["'])"""
                    r"""([^"']+\.(?:png|jpg|jpeg|gif|svg|webp))"""
                    r"""(["'])""",
                    _fix_img_src,
                    fixed_html,
                    flags=re.IGNORECASE,
                )
        except Exception:
            pass  # If post-processing fails, use original HTML  # 后处理失败时静默，沿用原 HTML

        # Auto-append images generated during this session that the LLM
        # forgot to include in the HTML.
        # 自动追加：会话内已生成但 LLM 忘记引用的图片（追加到 </body> 之前）
        try:
            gen_images = react_state.get("generated_images", [])  # 取会话内已生成图片
            if gen_images:
                # Extract all image filenames already referenced in the HTML
                # (e.g. "time_series_trend.png" from any src="...time_series_trend.png")
                html_img_stems = set(  # 提取 HTML 中已引用的图片 stem 集合
                    re.sub(r"^[0-9a-f]+_", "", os.path.basename(src))
                    for src in re.findall(
                        r'<img[^>]+src=["\']([^"\']+)["\']', fixed_html, re.IGNORECASE
                    )
                )

                # An image is "missing" only when neither its exact URL nor its
                # stem (filename with UUID prefix stripped) is already covered.
                def _img_stem(url):  # 工具函数：从 URL 提取 stem（去掉 UUID 前缀）
                    return re.sub(r"^[0-9a-f]+_", "", os.path.basename(url))

                missing = [  # 找出未被引用的图片
                    url
                    for url in gen_images
                    if url not in fixed_html and _img_stem(url) not in html_img_stems
                ]
                if missing:  # 如果有遗漏的图片
                    imgs_html = "".join(  # 拼成一段 <img> 卡片 HTML
                        f'<div style="margin:16px 0">'
                        f'<img src="{url}" '
                        f'style="max-width:100%;height:auto;'
                        f'border-radius:8px">'
                        f"</div>"
                        for url in missing
                    )
                    section = (  # 外层包一层带标题的 section
                        '<div style="margin-top:32px">'
                        "<h2>📊 分析图表</h2>"
                        f"{imgs_html}</div>"
                    )
                    # Insert before </body> if present, otherwise append
                    if "</body>" in fixed_html.lower():  # 如果有 </body>，插到它前面
                        fixed_html = re.sub(
                            r"(</body>)",
                            section + r"\1",
                            fixed_html,
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:  # 否则直接追加到末尾
                        fixed_html += section
        except Exception:
            pass

        chunks: List[Dict[str, Any]] = [  # 最终输出：单个 html chunk
            {"output_type": "html", "content": fixed_html, "title": title},
        ]
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    llm_client = DefaultLLMClient(  # 创建默认 LLM 客户端（基于 WorkerManager）
        CFG.SYSTEM_APP.get_component(  # 从 SystemApp 取 WorkerManagerFactory 组件
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create(),  # 创建 worker manager 实例
        auto_convert_message=True,  # 自动把消息转成模型兼容格式
    )
    # If user specified a model_name, use Priority strategy to ensure the
    # agent uses the requested model instead of picking the first available one.
    # 如果用户指定了 model_name，用 Priority 策略确保 agent 用该模型而非第一个可用模型
    if dialogue.model_name:  # 用户指定了模型
        llm_config = LLMConfig(
            llm_client=llm_client,
            llm_strategy=LLMStrategyType.Priority,  # Priority 策略：按优先级选模型
            strategy_context=json.dumps([dialogue.model_name]),  # 传入期望的模型名
        )
    else:  # 用户未指定模型
        llm_config = LLMConfig(llm_client=llm_client)  # 用默认策略

    conv_id = dialogue.conv_uid or str(uuid.uuid4())  # 取会话 ID 或新生成
    react_state["conv_id"] = conv_id  # 写入会话状态
    # ─────────────────────────────────────────────────────────────
    # 【上下文注入点 #2：AgentMemory 创建】
    # AgentMemory 组合了两套 memory：
    #   - self.memory = ShortTermMemory(buffer_size=5)  ← 进程内存，保留最近 5 个 ReAct step
    #   - self.gpts_memory = GptsMemory(...)           ← 落库，见下
    # gpts_memory 的 message_memory = MetaDbGptsMessageMemory() 会把每轮对话写进
    # gpts_messages 表；agent.build() 时会从该表恢复历史到 ShortTermMemory（见 base_agent.py L220-223）
    # gpts_memory 通过 REACT_AGENT_MEMORY_CACHE[conv_id] 跨请求复用
    # ─────────────────────────────────────────────────────────────
    if conv_id in REACT_AGENT_MEMORY_CACHE:  # 同一会话已有 memory 缓存
        gpt_memory = REACT_AGENT_MEMORY_CACHE[conv_id]  # 复用缓存
    else:  # 首次创建
        gpt_memory = GptsMemory(
            plans_memory=DefaultGptsPlansMemory(),     # 计划：内存版，重启丢失
            message_memory=MetaDbGptsMessageMemory(),   # 消息：落 gpts_messages 表
        )
        gpt_memory.init(conv_id, enable_vis_message=False)  # 初始化（不落可视化消息）
        REACT_AGENT_MEMORY_CACHE[conv_id] = gpt_memory  # 缓存到全局 dict
    # AgentMemory 默认 memory=ShortTermMemory(buffer_size=5)
    agent_memory = AgentMemory(gpts_memory=gpt_memory)  # 组装成 AgentMemory

    # --- Persist conversation to chat_history for sidebar display ---
    # 把会话写入 chat_history 表，供前端侧边栏展示
    conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)  # 取 ConversationServe 实例
    storage_conv = StorageConversation(  # 构造 StorageConversation 持久化对象
        conv_uid=conv_id,
        chat_mode=dialogue.chat_mode or "chat_react_agent",  # 默认 react_agent 模式
        user_name=dialogue.user_name,
        sys_code=dialogue.sys_code,
        summary=dialogue.user_input,  # 用首条用户输入作为会话摘要
        app_code=dialogue.app_code,
        conv_storage=conv_serve.conv_storage,  # 会话存储
        message_storage=conv_serve.message_storage,  # 消息存储
    )
    storage_conv.save_to_storage()  # 保存会话
    storage_conv.start_new_round()  # 开启新一轮对话
    storage_conv.add_user_message(user_input)  # 加入用户消息
    context = AgentContext(  # 构造 Agent 上下文（conv_id、语言、温度等）
        conv_id=conv_id,
        gpts_app_code="react_agent",
        gpts_app_name="ReAct",
        language="zh",  # 中文
        temperature=dialogue.temperature or 0.2,  # 默认 0.2
        enable_context_management=True,  # 启用上下文管理（budget 控制）
    )

    # Build file context if file uploaded
    # 如果用户上传了文件，构造 file context 注入到 system prompt
    file_context = ""
    if file_path:
        file_context = f"""
## User Uploaded File
- File path: {file_path}
- Analyze this file if needed for the user's request.
"""

    # Build skill context for system prompt when skill is pre-selected
    # 如果预匹配了技能，构造技能指令上下文（注入到 system prompt）
    skill_prompt_context = ""
    execution_instruction = ""
    if pre_matched_skill and react_state.get("skill_prompt"):
        skill_template = react_state["skill_prompt"]  # 取技能模板
        skill_text = (  # 提取模板文本
            skill_template.template
            if hasattr(skill_template, "template")
            else str(skill_template)
        )
        skill_prompt_context = f"""
## 已加载技能指令（{pre_matched_skill.metadata.name}）
以下是用户选择的技能的完整指令，请严格按照这些指令进行操作：

{skill_text}
"""
        execution_instruction = f"""
## 执行要求
1. 用户已明确选择技能：{pre_matched_skill.metadata.name}
2. 你必须严格按照上述技能指令的步骤执行
3. 阅读技能指令，理解每一步需要调用的工具
4. 按顺序执行工具调用，完成技能目标
"""

    # ── TodoWrite tool ──────────────────────────────────────────────────
    # A session-level task list that the agent maintains.  The full list is
    # replaced on every call (same semantics as OpenCode's todowrite).
    # The tool pushes a ``plan.update`` SSE event so the frontend can
    # render a live task-plan card.
    # TodoWrite 工具：会话级任务列表，每次调用整表替换（与 OpenCode 语义一致）
    # 工具会推 plan.update SSE 事件让前端实时渲染任务卡片
    _todo_list: List[Dict[str, str]] = []  # 会话级任务列表（闭包共享）

    @tool(  # @tool 装饰器：注册为 agent 可调用的任务管理工具
        description=(
            "Create and manage a structured task list for the current session. "
            "Use this tool to plan complex tasks (3+ steps), track progress, "
            "and show the user what you are doing. "
            "Pass the FULL todo list every time (not incremental). "
            "Each todo has: content (brief description), "
            "status (pending | in_progress | completed | cancelled), "
            "priority (high | medium | low). "
            "Rules: only ONE task in_progress at a time; mark tasks completed "
            "immediately after finishing; do NOT use for single trivial tasks."
            '\nParameter: {"todos": [{"content": "...", "status": "...", '
            '"priority": "..."}]}'
        )
    )
    def todowrite(todos: str) -> str:  # 闭包版 TodoWrite 工具
        """Update the session todo list (full replacement)."""
        import json as _json  # 局部 import 避免循环依赖

        parsed: List[Dict[str, str]] = []  # 解析后的 todos
        try:
            raw = _json.loads(todos) if isinstance(todos, str) else todos  # 兼容字符串/dict
            items = raw if isinstance(raw, list) else raw.get("todos", raw)  # 兼容裸 dict
            if isinstance(items, list):  # 是列表才解析
                for item in items:
                    parsed.append(  # 规范化为 dict
                        {
                            "content": str(item.get("content", "")),
                            "status": str(item.get("status", "pending")),  # 默认 pending
                            "priority": str(item.get("priority", "medium")),  # 默认 medium
                        }
                    )
        except Exception:  # JSON 解析失败
            return _json.dumps(  # 返回错误 chunk
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Error: invalid todos JSON",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        _todo_list.clear()  # 整表替换：清空旧列表
        _todo_list.extend(parsed)  # 整表替换：写入新列表

        total = len(parsed)  # 总数
        done = sum(1 for t in parsed if t["status"] == "completed")  # 已完成数
        return _json.dumps(  # 返回更新结果（含 __todos__ 字段供 SSE 转发）
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": f"Todo list updated: {done}/{total} completed",
                    }
                ],
                # Attach the todo list so SSE handler can forward it
                # 附上 todo 列表，SSE 主循环会读取并推 plan.update 事件
                "__todos__": parsed,
            },
            ensure_ascii=False,
        )

    _todo_action_history: Dict[int, List[str]] = {}  # 每个 todo 索引对应的 action 调用历史

    def _active_todo_index() -> Optional[int]:  # 找当前 in_progress 状态的 todo 索引
        for idx, item in enumerate(_todo_list):
            if item.get("status") == "in_progress":
                return idx
        return None

    def _normalize_text(value: Optional[str]) -> str:  # 文本归一化：去空白 + 转小写
        return (value or "").strip().lower()

    def _is_report_like(text: str) -> bool:  # 启发式判断文本是否是"报告类"任务
        keywords = [  # 报告类关键词
            "report",
            "html",
            "dashboard",
            "visual",
            "visualization",
            "图表",
            "报告",
            "报表",
            "可视化",
            "渲染",
            "展示",
        ]
        return any(keyword in text for keyword in keywords)

    def should_advance_todo(  # 启发式判断当前 todo 是否实质性完成（可推进到下一个）
        action_name: Optional[str],
        thought: Optional[str] = None,
        observation_text: Optional[str] = None,
    ) -> bool:
        """Heuristically decide whether the current todo is actually complete."""
        if not _todo_list:  # 没有任务列表
            return False

        active_idx = _active_todo_index()  # 当前 in_progress 的索引
        if active_idx is None:  # 没有 in_progress 的任务
            return False

        action_lower = _normalize_text(action_name)  # 归一化 action
        thought_lower = _normalize_text(thought)  # 归一化 thought
        observation_lower = _normalize_text(observation_text)  # 归一化 observation
        current_todo = _normalize_text(_todo_list[active_idx].get("content"))  # 当前 todo 文本
        next_todo = (  # 下一个 todo 文本（用于检测过渡）
            _normalize_text(_todo_list[active_idx + 1].get("content"))
            if active_idx + 1 < len(_todo_list)
            else ""
        )

        history = _todo_action_history.setdefault(active_idx, [])  # 取当前 todo 的 action 历史
        if action_lower:  # 把本次 action 加入历史
            history.append(action_lower)

        transition_markers = [  # thought 中的过渡标记词
            "next step",
            "now i need",
            "now i should",
            "now let me",
            "现在需要",
            "下一步",
            "接下来",
            "然后",
            "接着",
            "接下来我将",
        ]
        if next_todo and any(marker in thought_lower for marker in transition_markers):  # thought 里出现过渡词
            if any(token and token in thought_lower for token in next_todo.split()):  # 且提到下一个 todo 内容
                return True

        if action_lower == "html_interpreter":  # 调用了 html_interpreter = 报告已生成
            return True

        if action_lower in {  # skill 类 action
            "load_skill",
            "execute_skill_script",
            "execute_skill_script_file",
        }:
            if next_todo and next_todo in thought_lower:  # thought 提到下一个任务
                return True
            if _is_report_like(next_todo) and _is_report_like(thought_lower):  # 当前任务和下一任务都是报告类
                return True

        if action_lower == "sql_query":  # SQL 查询类 action
            sql_calls = sum(1 for item in history if item == "sql_query")  # 累计 SQL 调用次数
            if sql_calls < 3:  # 少于 3 次不推进（避免单次查询就跳过）
                return False

            if next_todo and any(  # thought 提到下一任务
                token and token in thought_lower for token in next_todo.split()
            ):
                return True

            if _is_report_like(next_todo) and (  # 下一任务是报告类且 thought 在做汇总
                "summary" in thought_lower
                or "summarize" in thought_lower
                or "整理" in thought_lower
                or "汇总" in thought_lower
                or "报告" in thought_lower
            ):
                return True

            if current_todo and not _is_report_like(current_todo):  # 当前非报告类任务
                completion_markers = [  # "已收集足够信息" 类完成标记
                    "enough information",
                    "collected enough",
                    "gathered enough",
                    "completed metadata",
                    "obtained the overview",
                    "获取了足够",
                    "已经获取了足够",
                    "已完成",
                    "已获取",
                    "整理一下",
                ]
                if any(marker in thought_lower for marker in completion_markers):
                    return True

            return False

        if action_lower in {"code_interpreter", "execute_tool", "shell_interpreter"}:  # 代码执行类 action
            if _is_report_like(current_todo):  # 当前任务是报告类，不推进
                return False
            if next_todo and any(  # thought 提到下一任务
                token and token in thought_lower for token in next_todo.split()
            ):
                return True
            if observation_lower and _is_report_like(observation_lower):  # observation 是报告类内容
                return True

        return False

    def advance_todo_list() -> Optional[List[Dict[str, str]]]:  # 推进 todo 列表：当前置 completed，下一 pending 置 in_progress
        """Advance one todo when the current task appears substantively complete."""
        if not _todo_list:  # 无任务列表
            return None

        changed = False  # 是否有变更
        active_idx = _active_todo_index()  # 当前 in_progress 索引

        if active_idx is not None:  # 有 in_progress 任务
            _todo_list[active_idx]["status"] = "completed"  # 标记为已完成
            changed = True
            _todo_action_history.pop(active_idx, None)  # 清理历史
            for next_item in _todo_list[active_idx + 1 :]:  # 找下一个 pending 任务
                if next_item.get("status") == "pending":
                    next_item["status"] = "in_progress"  # 标记为 in_progress
                    _todo_action_history.pop(active_idx + 1, None)
                    break
        else:  # 没有 in_progress，激活第一个 pending
            for item in _todo_list:
                if item.get("status") == "pending":
                    item["status"] = "in_progress"
                    changed = True
                    break

        return list(_todo_list) if changed else None  # 有变更才返回新列表

    # Build a hint listing all images currently available in
    # STATIC_MESSAGE_IMG_PATH so the LLM can reference them correctly in
    # html_interpreter.
    # 构造静态目录下已有图片清单的提示，方便 LLM 在 html_interpreter 里正确引用
    # NOTE: This is the initial hint at prompt build time. Images generated
    # during the session are tracked in react_state["generated_images"] and
    # appended to html_interpreter output dynamically.
    # 注意：这只是 prompt 构建时的初始提示；会话过程中生成的图片会通过
    # react_state["generated_images"] 动态追加到 html_interpreter 输出
    available_images_hint = ""

    # Check if skill is pre-selected to use simplified prompt
    # 判断是否技能模式（预匹配技能时用简化 prompt）
    is_skill_mode = pre_matched_skill is not None
    _skill_name = pre_matched_skill.metadata.name if pre_matched_skill else "skill"  # 技能名（用于 prompt 提示）

    # Inject connector tools — only the ones the user explicitly selected.
    # 注入 connector 工具：只注入用户明确选中的 connector
    connector_tool_extras: List[Any] = []
    try:
        from dbgpt.agent.resource.connector.manager import (
            ConnectorManager as _ConnectorManager,
        )

        _connector_manager = CFG.SYSTEM_APP.get_component(  # 从 SystemApp 取 connector_manager 组件
            "connector_manager", _ConnectorManager, default_component=None
        )
        if _connector_manager is not None and connector_ids:  # 有 manager 且用户选了 connector
            connector_tool_extras, _missing = _select_connector_tools(  # 选择 connector 对应的工具
                connector_ids, _connector_manager
            )
            for _mid in _missing:  # 不活跃的 connector_id 警告
                logger.warning(
                    "_react_agent_stream: connector_id %s not active, skipping",
                    _mid,
                )
            if connector_tool_extras:  # 注入成功
                logger.info(
                    "_react_agent_stream: injected %d connector tool pack(s) "
                    "(selected: %d)",
                    len(connector_tool_extras),
                    len(connector_ids),
                )
    except Exception:
        pass  # graceful degradation — connector tools are optional  # connector 工具可选，失败时静默降级

    if is_skill_mode:  # 技能模式：用简化 prompt（只暴露技能相关工具）
        # Simplified prompt for skill mode - only skill-related tools +
        # html_interpreter
        # 技能模式 prompt：只列出技能相关工具 + html_interpreter
        workflow_prompt = f"""
You are the DB-GPT intelligent assistant, executing the skill task selected by the user.
Please always response in the same language as the user's input language.

## Autonomous Decision Principles
1. Strictly follow the instructions of the loaded skill.
2. For each step, output Thought -> Action Intention -> Action Reason -> Action
   -> Action Input.
3. Wait for the system to return Observation before deciding on the next step.
4. **[Mandatory Rule] If the task requires generating an analysis report, you MUST
call `html_interpreter` for HTML rendering.** By default, generate complete HTML
code yourself and pass it via the `html` parameter (include DOCTYPE, html, head,
body, styles, and all content). Only use `template_path` mode if the skill
explicitly provides HTML templates in its `templates/` directory and its
documentation references them. When using template mode, provide ALL required
placeholders in the `data` dictionary.
5. If the task does not require generating a report, directly call terminate to
return the final result. The Action Input format must be
{{"result": "final answer"}}.

{skill_prompt_context}
{execution_instruction}

## Skill Execution Norms
### Resource Usage
- **Need to execute skill script** -> Use `execute_skill_script_file` with
parameters {{"skill_name": "skill name", "script_file_name": "script file name",
"args": {{parameters}}}}. This tool will automatically handle image copying and
data recording.
- **Need to understand indicator definitions/analysis framework** -> Use
`get_skill_resource` and specify the `references/xxx.md` path to read the
reference document.
- **Encounter image file** -> If the model does not support image input, it will
return an error prompt.
- **Need to generate report** -> Call `html_interpreter`. **Default: directly pass
complete HTML via the `html` parameter** — you generate the full HTML code
yourself (including `<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`, styles,
content). The HTML can be as long as needed. **Only use `template_path` if the
skill explicitly provides HTML templates in its `templates/` directory and its
documentation tells you to use them.** Do not use `code_interpreter` to generate
the report.

## Available Tools Description
1. **execute_skill_script_file** (recommended for executing skill scripts): Execute
script files in the skills scripts directory, automatically handling
post-processing such as copying images to the static directory and recording
calculation results.
   Parameters: {{"skill_name": "skill name", "script_file_name": "script file
name", "args": {{parameters}}}}
   - Example: {{"skill_name": "{_skill_name}",
"script_file_name": "calculate_ratios.py",
"args": {{"input_data": "..."}}}}
   - **Must use this tool when executing skill scripts**, do not use
shell_interpreter.
2. **get_skill_resource**: Read reference documents, configurations, templates, and
other non-script resource files in the skill.
   Parameters: {{"skill_name": "skill name", "resource_path": "resource path"}}
   - Read reference document: {{"skill_name": "{_skill_name}",
"resource_path": "references/analysis_framework.md"}}
   - Note: For generating reports, prefer using html_interpreter directly with the
`html` parameter. Only use template_path if the skill explicitly provides
templates.
3. **execute_skill_script**: Execute the inline script defined in the skill
(backup). Parameters: {{"skill_name": "skill name", "script_name": "script name",
"args": {{"parameter name": "parameter value"}}}}
4. **shell_interpreter**: Execute shell/bash commands (only for non-skill script
system commands, such as ls, cat, etc.).
   Parameters: {{"code": "shell command"}}
   - Each call is independent and does not retain state. If multi-step operations
are needed, use `&&` or `;` to connect commands.
   - **Note: Do not use this tool to execute skill scripts**, as it will not
automatically handle images and data recording.
5. **html_interpreter**: Render HTML as an interactive web report. This is the ONLY
way to display reports on the right panel.
   **Default usage (recommended)**: {{"html": "<html>your complete HTML code</html>",
"title": "report title"}}
   - Generate complete HTML yourself (DOCTYPE, html, head, body, CSS styles,
content). No length limit.
   - **Do not** use code_interpreter to write HTML. Directly pass the HTML string
to this tool.
   **Template mode (only when skill has templates/)**: {{"template_path":
"skill-name/templates/template.html", "data": {{"KEY": "value"}}, "title": "title"}}
   - Only use this if the skill's documentation explicitly provides template paths.
If template_path returns "Template not found", immediately switch to the default
`html` parameter usage.
   {available_images_hint}
6. **sql_query**: Execute a read-only SQL query against the selected database.
Parameters: {{"sql": "SELECT statement"}}
7. **todowrite**: Create and manage a structured task list. Use for complex tasks
(3+ steps) to plan and track progress. Pass the FULL list every time. Each item:
{{"content": "description", "status": "pending|in_progress|completed|cancelled",
"priority": "high|medium|low"}}. Only ONE task in_progress at a time.
IMPORTANT: You MUST call todowrite again after EACH task completes to update status.
The user sees progress in real time — never skip an update.
Parameters: {{"todos": [{{...}}]}}
8. **terminate**: Return the final answer when the task is completed. Action Input
must be {{"result": "your final answer content"}}.

## Task Management
For complex tasks that require 3 or more steps, use the `todowrite` tool to create
a structured task plan BEFORE starting work. This helps users track your progress.
- Call `todowrite` with the FULL todo list (all items) each time you update.
- Mark exactly ONE task as `in_progress` at a time.
- Mark tasks `completed` immediately after finishing each one.
- Do NOT use todowrite for simple single-step tasks.

CRITICAL: You MUST call `todowrite` to update the task list at EVERY transition:
1. BEFORE starting a task: mark it `in_progress` (call todowrite)
2. AFTER finishing a task: mark it `completed` AND mark the next one
   `in_progress` (call todowrite)
3. Never skip updating — the user sees this progress in real time.
Example flow for 3 tasks:
- Create plan: [task1=in_progress, task2=pending, task3=pending] → call todowrite
- Finish task1: [task1=completed, task2=in_progress, task3=pending] → call todowrite
- Finish task2: [task1=completed, task2=completed, task3=in_progress] → call todowrite
- Finish task3: [task1=completed, task2=completed, task3=completed] → call todowrite

{file_context}
{knowledge_context}
{database_context}
## ReAct Output Format
Must output for each interaction round:
Thought: Analyze current task status and think about what to do next
Action Intention: What this step will do, plain text, MUST be concise and fit in
<= 18 Chinese chars or <= 8 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action Reason: Why this action is needed now, plain text, MUST be concise and fit in
<= 30 Chinese chars or <= 12 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action: The selected tool name (must be one of the tools listed above)
Action Input: The JSON format of tool parameters
""".strip()

        tool_pack = ToolPack(  # 技能模式 ToolPack：只含技能相关工具
            [
                execute_skill_script,
                get_skill_resource,
                execute_skill_script_file,
                shell_interpreter,
                html_interpreter,
                sql_query,
                todowrite,
                Terminate(),
            ]
            + business_tools  # 业务工具（数据源相关）
            + connector_tool_extras  # 用户选中的 connector 工具
        )
    else:  # 完整模式：未预匹配技能时，列出全部工具
        # Full prompt with all tools when no skill is pre-selected
        # 完整模式 prompt：列出全部工具供 LLM 自主选择
        workflow_prompt = f"""
You are the DB-GPT intelligent assistant, capable of autonomously selecting tools
to solve problems based on user tasks.
Please always response in the same language as the user's input language.

## Autonomous Decision Principles
1. Carefully analyze the user's task requirements.
2. Autonomously select required tools based on requirements (do not follow a fixed
order, select as needed).
3. For each step, output Thought -> Action Intention -> Action Reason -> Action
   -> Action Input.
4. Wait for the system to return Observation before deciding on the next step.
5. When the task is completed, call the terminate tool to return the final result.
The Action Input format must be {{"result": "final answer"}}.
6. **[Mandatory Rule] If there is a requirement for an analysis report, you MUST call
`html_interpreter` for HTML rendering. When the user requests generating a webpage,
HTML report, or interactive report, the final presentation step must call
`html_interpreter` to render it. It is forbidden to output HTML using only
`code_interpreter` and then directly terminate. Correct process: code_interpreter
writes to .html file -> html_interpreter(file_path=...) renders -> terminate.**

## Task Management
For complex tasks that require 3 or more steps, use the `todowrite` tool to create
a structured task plan BEFORE starting work. This helps users track your progress.
- Call `todowrite` with the FULL todo list (all items) each time you update.
- Mark exactly ONE task as `in_progress` at a time.
- Mark tasks `completed` immediately after finishing each one.
- Do NOT use todowrite for simple single-step tasks.

CRITICAL: You MUST call `todowrite` to update the task list at EVERY transition:
1. BEFORE starting a task: mark it `in_progress` (call todowrite)
2. AFTER finishing a task: mark it `completed` AND mark the next one
   `in_progress` (call todowrite)
3. Never skip updating — the user sees this progress in real time.
Example flow for 3 tasks:
- Create plan: [task1=in_progress, task2=pending, task3=pending] → call todowrite
- Finish task1: [task1=completed, task2=in_progress, task3=pending] → call todowrite
- Finish task2: [task1=completed, task2=completed, task3=in_progress] → call todowrite
- Finish task3: [task1=completed, task2=completed, task3=completed] → call todowrite

## Available Skills List (Pre-loaded)
{skills_context}

## Skill Execution Norms (Important)
When using a skill, the following rules must be followed:

### 1. Understand the Workflow
After loading the skill, carefully read the **Core Workflow** section in SKILL.md
and execute it in order. If a step explicitly states conditions to skip (such as
when user intent is clear), directly skip to the next step; do not force the
execution of every step. Prioritize producing results quickly, and perform
iterative optimization in subsequent steps.

### 2. Resource Usage Timing
- **Need to calculate/process data** -> Use `execute_skill_script_file` to execute
scripts in the skill's scripts directory (this tool automatically handles images
and data recording). Parameters are {{"skill_name": "skill name",
"script_file_name": "script.py", "args": {{parameters}}}}.
- **Need to understand indicator definitions/analysis framework** -> Use
`get_skill_resource` and specify the `references/xxx.md` path to read the
reference document.
- **Encounter image file** -> If the model does not support image input, it will
return an error prompt.

### 3. Execution Order
Complete each workflow step before moving to the next. Do not mix multiple tool
calls in the same step.

### 4. Special Scenarios
- For report generation: Same as the principle above, must finally call
`html_interpreter` to render.

## Available Tools Description
1. **load_skill**: Load skill content by skill name and file path.
Parameters: {{"skill_name": "skill name", "file_path": "skill file path"}}
2. **execute_skill_script_file**: Execute script files in the skill's scripts
directory. Parameters: {{"skill_name": "skill name",
"script_file_name": "script file name", "args": {{parameters}}}}
3. **get_skill_resource**: Read reference documents in the skill.
Parameters: {{"skill_name": "skill name", "resource_path": "resource path"}}
4. **execute_skill_script**: Execute the inline script defined in the skill.
Parameters: {{"skill_name": "skill name", "script_name": "script name",
"args": {{parameters}}}}
5. **shell_interpreter**: Execute shell/bash commands.
Parameters: {{"code": "shell command"}}
6. **code_interpreter**: Execute arbitrary Python code.
Parameters: {{"code": "python code string"}}
7. **load_file**: Load uploaded file info. Parameters: none.
8. **execute_analysis**: Execute quick analysis on uploaded Excel/CSV file.
Parameters: none.
9. **knowledge_retrieve**: Retrieve relevant info from knowledge base.
Parameters: {{"query": "search query"}}
10. **sql_query**: Execute a read-only SQL query against the selected database.
Parameters: {{"sql": "SELECT statement"}}
11. **load_tools**: Resolve required tools for the selected skill. Parameters: none.
12. **execute_tool**: Execute a tool by name with JSON args.
Parameters: {{"tool_name": "tool name", "args": {{parameters}}}}
13. **html_interpreter**: Render HTML as an interactive web report (the ONLY way
to display reports on the right panel). Default usage:
{{"html": "<html>complete HTML code</html>", "title": "title"}}. Template mode:
{{"template_path": "skill/templates/xxx.html", "data": {{...}}, "title": "title"}}.
File mode: {{"file_path": "/path/to/report.html"}}
14. **todowrite**: Create and manage a structured task list. Use for complex tasks
(3+ steps) to plan and track progress. Pass the FULL list every time. Each item:
{{"content": "description", "status": "pending|in_progress|completed|cancelled",
"priority": "high|medium|low"}}. Only ONE task in_progress at a time.
IMPORTANT: You MUST call todowrite again after EACH task completes to update status.
The user sees progress in real time — never skip an update.
Parameters: {{"todos": [{{...}}]}}
15. **terminate**: Finish the task. Parameters: {{"result": "final answer"}}

{file_context}
{knowledge_context}
{database_context}

## ReAct Output Format
Must output for each interaction round:
Thought: Analyze current task status and think about what to do next
Action Intention: What this step will do, plain text, MUST be concise and fit in
<= 18 Chinese chars or <= 8 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action Reason: Why this action is needed now, plain text, MUST be concise and fit in
<= 30 Chinese chars or <= 12 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action: The selected tool name
Action Input: The JSON format of tool parameters
""".strip()

        tool_pack = ToolPack(  # 完整模式 ToolPack：列出全部工具
            [
                load_skill,
                load_tools,
                knowledge_retrieve,
                execute_skill_script,
                get_skill_resource,
                execute_skill_script_file,
                code_interpreter,
                shell_interpreter,
                html_interpreter,
                sql_query,
                todowrite,
                Terminate(),
            ]
            + business_tools  # 业务工具
            + connector_tool_extras  # 用户选中的 connector 工具
        )

    # Debug: print all registered tools
    # 调试日志：打印 ToolPack 内已注册的工具
    logger.info(f"ToolPack resources: {list(tool_pack._resources.keys())}")
    if "execute_skill_script" not in tool_pack._resources:  # 检查关键工具是否注册
        logger.error("execute_skill_script NOT in ToolPack!")

    # Combine tool_pack and knowledge_resources into a single ResourcePack
    # 把 tool_pack 和知识库 resources 合并成 all_resources（agent 会绑定所有）
    all_resources = [tool_pack]
    if knowledge_resources:  # 有知识库资源时追加
        all_resources.extend(knowledge_resources)

    # --- Connector system prompt injection (T11) ---
    # Connector 系统 prompt 注入：把用户选中的 connector 工具描述追加到 workflow_prompt
    try:
        from dbgpt.agent.resource.connector.manager import (
            ConnectorManager as _ConnectorManager,
        )

        _cm = CFG.SYSTEM_APP.get_component(  # 取 ConnectorManager 组件
            "connector_manager", _ConnectorManager, default_component=None
        )
        if _cm is not None and connector_ids:  # 有 manager 且用户选了 connector
            _active = _cm.list_active()  # 列出所有活跃 connector
            # Only describe connectors the user explicitly selected.
            # Iterate connector_ids (not _active) so prompt order matches
            # user selection order and stays consistent with _select_connector_tools.
            # 只描述用户明确选中的 connector；按 connector_ids（而非 _active）遍历，
            # 让 prompt 顺序与用户选择顺序一致，也与 _select_connector_tools 保持一致
            _active_map = {c["connector_id"]: c for c in _active if isinstance(c, dict)}  # id -> connector 信息
            _selected = [  # 只保留用户选中的 connector
                _active_map[cid] for cid in connector_ids if cid in _active_map
            ]
            if _selected:  # 有选中的 connector
                _connector_lines = []  # 每行描述一个 connector
                for _c in _selected:  # 遍历每个选中的 connector
                    _tool_lines = []  # 该 connector 下每个工具的描述
                    for t in _c.get("tools", []):  # 遍历 connector 的工具
                        _name = t.get("name", "unknown")  # 工具名
                        _desc = t.get("description", "") or "(no description)"  # 工具描述
                        _args_schema = t.get("args", {}) or {}  # 参数 schema
                        # Render args schema as concise Parameters description
                        # 把参数 schema 渲染成简明的 Parameters 描述
                        if _args_schema:
                            _param_parts = []  # 每个参数的描述片段
                            for _arg_name, _arg_meta in _args_schema.items():  # 遍历参数
                                if isinstance(_arg_meta, dict):  # 参数元信息是 dict
                                    _arg_type = _arg_meta.get("type", "any")  # 参数类型
                                    _req = (  # 是否必填
                                        "required"
                                        if _arg_meta.get("required")
                                        else "optional"
                                    )
                                    _arg_desc = _arg_meta.get("description", "")  # 参数描述
                                    if _arg_desc:  # 有描述时拼接
                                        _trimmed_desc = (  # 描述超 120 字截断
                                            _arg_desc[:120] + "..."
                                            if len(_arg_desc) > 120
                                            else _arg_desc
                                        )
                                        _param_parts.append(
                                            f'"{_arg_name}": <{_arg_type}, {_req}, '
                                            f"{_trimmed_desc}>"
                                        )
                                    else:  # 无描述时只写类型和必填
                                        _param_parts.append(
                                            f'"{_arg_name}": <{_arg_type}, {_req}>'
                                        )
                                else:  # 参数元信息不是 dict，简化为 any
                                    _param_parts.append(f'"{_arg_name}": <any>')
                            _params_str = "{" + ", ".join(_param_parts) + "}"  # 拼成 JSON 风格字符串
                        else:  # 无参数 schema
                            _params_str = "{}"
                        _tool_lines.append(  # 把工具描述拼成一行
                            f"  - **{_name}**: {_desc}\n    Parameters: {_params_str}"
                        )
                    _connector_lines.append(  # 把整个 connector 描述拼成一段
                        f"### {_c.get('name', 'unknown')} "
                        f"({_c.get('connector_type', 'unknown')})\n"
                        f"{_c.get('description', '') or '(no description)'}\n\n"
                        f"Tools (call directly with `Action: <tool_name>`):\n"
                        + "\n".join(_tool_lines)
                        + "\n\nNote: Write operations require user confirmation."
                    )
                _connector_prompt = (  # 拼接 connector 系统 prompt 段落
                    "\n\n## Available MCP Connector Tools\n"
                    "You have access to the following external MCP connectors. "
                    "All listed tools are pre-registered — invoke them directly "
                    "with `Action: <tool_name>`, NOT through `execute_tool`.\n"
                    + "\n\n".join(_connector_lines)
                )
                workflow_prompt += _connector_prompt  # 追加到 workflow_prompt 末尾
    except Exception:
        pass  # graceful degradation  # connector 系统 prompt 注入失败时静默降级
    # --- End connector system prompt injection ---

    # Convert workflow_prompt to PromptTemplate so it is used as system prompt
    # Use jinja2 format to avoid issues with JSON braces { } in the prompt
    # 把 workflow_prompt 包装成 PromptTemplate 作为 system prompt
    # 用 jinja2 格式避免 prompt 中的 JSON 大括号 { } 被错误解析
    workflow_prompt_template = PromptTemplate(
        template=workflow_prompt,  # 模板内容
        input_variables=[],  # 无输入变量（已全部预先 f-string 拼好）
        template_format="jinja2",  # jinja2 格式（保护 JSON 大括号）
    )

    agent_builder = (  # 用 Builder 模式组装 ReActAgent
        ReActAgent(max_retry_count=30)  # 最大重试 30 次
        .bind(context)  # 绑定 AgentContext
        .bind(agent_memory)  # 绑定 AgentMemory
        .bind(llm_config)  # 绑定 LLMConfig
        .bind(tool_pack)  # 绑定 ToolPack（含所有工具）
        .bind(workflow_prompt_template)  # 绑定 system prompt 模板
    )

    agent = await agent_builder.build()  # 异步构建 agent（会从 gpts_messages 恢复历史到 ShortTermMemory）

    parser = ReActOutputParser()  # ReAct 输出解析器（解析 Thought/Action/Action Input）
    # ─────────────────────────────────────────────────────────────
    # 【上下文注入点 #3：user message 拼接向量库检索结果】
    # 将 db_summary_context（向量库 top-20 表结构）拼到 user_input 后面
    # ⚠️ 每次请求都会拼接，导致每个新问题的 user message 都带表结构
    # ─────────────────────────────────────────────────────────────
    _received_content = user_input  # 用户原始输入
    if db_summary_context:  # 如果有向量库检索到的表结构上下文
        _received_content = f"{user_input}{db_summary_context}"  # 拼到 user_input 后面
    received = AgentMessage(content=_received_content)  # 构造 AgentMessage
    stream_queue: asyncio.Queue = asyncio.Queue()  # 事件队列：agent 回调写、SSE 主循环读

    # Wire up context-management status events into the SSE stream.
    # 把上下文管理状态事件转发到 SSE 流
    async def _context_status_callback(status: Dict[str, Any]) -> None:  # 状态事件回调
        await stream_queue.put({"type": "context.status", **status})  # 推入队列

    agent.init_context_management(  # 初始化上下文管理（budget 控制）
        config=await _load_context_budget_config(  # 加载 budget 配置（按 model_name）
            llm_client=llm_client,
            model_name=dialogue.model_name,
        ),
        model_name=dialogue.model_name,  # 传模型名
        on_status_event=_context_status_callback,  # 注册状态事件回调
    )

    async def stream_callback(event_type: str, payload: Dict[str, Any]) -> None:  # agent 流式回调
        await stream_queue.put({"type": event_type, **payload})  # 把事件推入队列

    # ─────────────────────────────────────────────────────────────
    # 【上下文注入点 #4：手动全量加载历史对话】
    # 每次请求都从 conversation service 加载 conv_id 下的全部历史消息
    # 转成 List[AgentMessage] 传给 generate_reply 的 historical_dialogues 参数
    # ⚠️ 重复风险：这段历史和 ShortTermMemory（从 gpts_messages 表恢复）内容重叠
    #    同一轮 user_input 会在 agent_messages 中出现多次：
    #    - 一次在 historical_dialogues（这里注入）
    #    - 一次在 memory_list（base_agent.py L1373 从 ShortTermMemory 读）
    # ─────────────────────────────────────────────────────────────
    historical_dialogues: List[AgentMessage] = []  # 历史对话列表
    try:
        from dbgpt_serve.conversation.api.schemas import ServeRequest  # 会话请求 schema

        conv_service = _get_conversation_service()  # 取会话 service 实例
        hist_msgs = conv_service.get_history_messages(  # 加载 conv_id 下全部历史消息
            ServeRequest(conv_uid=conv_id)
        )
        # MessageVo 的内容字段是 context（不是 content），role 是角色字符串
        # MessageVo 的内容字段是 context（不是 content），role 是角色字符串
        from dbgpt.core import ModelMessageRoleType as _Role  # 角色 enum
        for m in hist_msgs or []:  # 遍历每条历史
            content = m.context if hasattr(m, "context") else ""  # 取 context 字段
            role_str = m.role if hasattr(m, "role") else "human"  # 取角色
            # 跳过 view 类型消息（渲染视图，非用户或 AI 文本回复）
            # 跳过 view 类型消息（渲染视图，非用户或 AI 文本回复）
            if role_str == "view":
                continue
            historical_dialogues.append(  # 追加到列表
                AgentMessage(
                    content=content,
                    role=_Role.HUMAN if role_str == "human" else _Role.AI,  # 转成 enum
                )
            )
        if historical_dialogues:  # 有历史时打印日志
            logger.info(
                f"Loaded {len(historical_dialogues)} historical dialogues "
                f"for conv={conv_id}"
            )
    except Exception as he:  # 加载失败仅告警，不中断流程
        logger.warning(f"Failed to load historical dialogues: {he}")

    async def run_agent():  # 启动 agent 的协程任务
        return await agent.generate_reply(
            received_message=received,  # 接收消息（含 db_summary_context）
            sender=agent,  # 发送者 = agent 自身
            stream_callback=stream_callback,  # 流式回调
            # historical_dialogues 在 base_agent.py L1357-1371 被合并进 agent_messages
            historical_dialogues=historical_dialogues or None,  # 历史对话（None 表示不传）
        )

    agent_task = asyncio.create_task(run_agent())  # 创建后台任务执行 agent
    round_step_map: Dict[int, str] = {}  # ReAct 轮次 -> SSE step_id 的映射
    pending_thoughts: Dict[
        int, List[str]
    ] = {}  # Buffer thinking content for delayed step creation  # 缓存思考内容，延迟创建 step
    pending_action_intentions: Dict[int, str] = {}  # 缓存 action intention
    pending_action_reasons: Dict[int, str] = {}  # 缓存 action reason
    # --- History persistence: collect step data during streaming ---
    # 历史持久化：在流式过程中收集 step 数据
    history_steps: List[Dict[str, Any]] = []  # 全部 step 数据
    current_history_step: Optional[Dict[str, Any]] = None  # 当前正在处理的 step

    # Emit pre-loaded skill as an SSE step before agent starts processing
    # 如果预匹配了技能，在 agent 开始处理前先发一个 "Load Skill" SSE step
    if pre_matched_skill:
        skill_step_id, skill_step_event = build_step(  # 构造技能加载 step
            f"Load Skill: {pre_matched_skill.metadata.name}",
            "Pre-loaded skill from user selection",
            phase="加载技能",
        )
        current_history_step = {  # 同步记录到 history
            "id": skill_step_id,
            "title": f"Load Skill: {pre_matched_skill.metadata.name}",
            "detail": "Pre-loaded skill from user selection",
            "phase": "加载技能",
            "thought": None,
            "action": None,
            "action_input": None,
            "outputs": [],
            "status": "done",
        }
        yield skill_step_event  # 推 step.start SSE 事件
        # Emit skill metadata as text chunk
        # 把技能元数据作为 text chunk 发出
        skill_desc = (
            f"Skill: {pre_matched_skill.metadata.name}"
            f" - {pre_matched_skill.metadata.description}"
        )
        yield step_chunk(skill_step_id, "text", skill_desc)  # 推 text chunk
        current_history_step["outputs"].append(  # 记录到 history
            {"output_type": "text", "content": skill_desc}
        )
        # Emit skill instructions as markdown content (shows in right panel)
        # 把技能指令作为 markdown chunk 发出（前端右面板展示）
        if pre_matched_skill.instructions:
            yield step_chunk(skill_step_id, "markdown", pre_matched_skill.instructions)
            current_history_step["outputs"].append(
                {
                    "output_type": "markdown",
                    "content": pre_matched_skill.instructions,
                }
            )
        yield step_done(skill_step_id)  # 推 step.done
        history_steps.append(current_history_step)  # 写入历史
        current_history_step = None

    while True:  # SSE 主循环：从 stream_queue 取事件并转 SSE
        if agent_task.done() and stream_queue.empty():  # agent 任务完成且队列空
            break
        try:
            event = await asyncio.wait_for(stream_queue.get(), timeout=0.1)  # 100ms 取一个事件
        except asyncio.TimeoutError:  # 超时继续下一轮
            continue

        event_type = event.get("type")  # 取事件类型
        if event_type == "context.status":  # 上下文管理状态事件
            # Forward context-management status to frontend as-is.
            # 上下文管理状态事件直接转发给前端
            yield _sse_event(event)
        elif event_type == "thinking":  # 完整 thinking 事件（一轮 LLM 回复）
            # Parse thinking content but don't create step yet
            # Step will be created when 'act' event arrives with confirmed
            # action
            # 解析 thinking 内容，但暂不创建 step；等 'act' 事件确认 action 后再创建
            round_num = int(event.get("round") or (len(round_step_map) + 1))  # 当前轮次
            llm_reply = event.get("llm_reply") or ""  # LLM 完整回复
            thought = None
            action_intention = None
            action_reason = None
            action = None
            action_input = None
            try:
                steps = parser.parse(llm_reply)  # 用 ReActOutputParser 解析
                if steps:
                    thought = steps[0].thought  # 思考内容
                    action_intention = steps[0].action_intention  # 行动意图
                    action_reason = steps[0].action_reason  # 行动原因
                    action = steps[0].action  # 行动名
                    action_input = steps[0].action_input  # 行动输入
            except Exception:
                pass

            # Store parsed thinking info in pending_thoughts for later use
            # 把解析出的 thinking 信息缓存到 pending_thoughts 等后续使用
            if round_num not in pending_thoughts:
                pending_thoughts[round_num] = []
            if thought:
                pending_thoughts[round_num].append(thought)
            intention_text = normalize_display_text(action_intention)  # 归一化 intention
            if intention_text:
                pending_action_intentions[round_num] = intention_text  # 缓存 intention
            reason_text = normalize_display_text(action_reason)  # 归一化 reason
            if reason_text:
                pending_action_reasons[round_num] = reason_text  # 缓存 reason
            # Don't emit anything yet - wait for 'act' event to create step
            # 暂不发 SSE，等 'act' 事件到达再创建 step

        elif event_type == "thinking_chunk":  # 增量 thinking chunk（流式思考）
            round_num = int(event.get("round") or (len(round_step_map) + 1))  # 当前轮次
            delta_thinking = event.get("delta_thinking") or ""  # thinking 增量
            delta_text = event.get("delta_text") or ""  # text 增量

            chunk = delta_thinking or delta_text  # 优先用 delta_thinking
            if chunk:
                # Clean chunk: remove Action Input JSON to keep thought pure
                # Split on Action Input pattern and keep only thought part
                # 清洗 chunk：去掉 Action Input JSON，只保留 thought 部分
                clean_chunk = re.split(
                    r"\n\s*Action\s*Input\s*:\s*\{", chunk, maxsplit=1
                )[0]
                # Also remove Action: lines
                # 也去掉 Action: 行
                clean_chunk = re.sub(r"\n\s*Action\s*:\s*\w+", "", clean_chunk)
                # Remove Thought: prefix if present
                # 去掉 Thought: 前缀
                if clean_chunk.startswith("Thought:"):
                    clean_chunk = clean_chunk[len("Thought:") :].strip()
                if clean_chunk:
                    if round_num not in pending_thoughts:
                        pending_thoughts[round_num] = []
                    pending_thoughts[round_num].append(clean_chunk)  # 缓存 thinking
                    if round_num not in round_step_map:  # 该轮次还没创建 step
                        pending_step_id, pending_step_event = build_step(  # 先建一个"思考中" step
                            "思考中",
                            "Thought/Action/Observation",
                        )
                        round_step_map[round_num] = pending_step_id
                        yield pending_step_event  # 推 step.start

        elif event_type == "act":  # act 事件：action 已执行完成
            # Create step ONLY when action is confirmed
            # 只有 action 确认后才创建 step
            round_num = int(event.get("round") or (len(round_step_map) + 1))  # 当前轮次

            action_output = event.get("action_output") or {}  # action 输出
            thoughts = action_output.get("thoughts")  # 思考
            action = action_output.get("action")  # 行动名
            action_input = action_output.get("action_input")  # 行动输入
            action_input_data = None
            if action_input is not None:  # 尝试解析 action_input 为 dict
                if isinstance(action_input, str):
                    try:
                        action_input_data = json.loads(action_input)
                    except Exception:
                        action_input_data = action_input
                else:
                    action_input_data = action_input

            # Skip step display for terminate action — its output will be
            # sent as a streaming "final" event instead of a step card.
            # Also skip emitting the thought for terminate since it's noise.
            # Note: TerminateAction.run() sets terminate=True but does NOT
            # set the action field, so we must check the terminate boolean.
            # terminate action 不显示 step（其输出会作为 final 事件流式发出）
            # 注意：TerminateAction.run() 只置 terminate=True，不设 action 字段，
            # 所以要额外检查 terminate 布尔
            is_terminate = action_output.get("terminate") or (
                action and action.lower() == "terminate"
            )
            if is_terminate:  # 是 terminate
                pending_thoughts.pop(round_num, [])  # 清空缓存
                pending_action_intentions.pop(round_num, None)
                pending_action_reasons.pop(round_num, None)
                # ── Auto-complete all remaining todos on terminate ──
                # ── terminate 时自动把所有未完成的 todo 标记为 completed ──
                if _todo_list:
                    for t in _todo_list:
                        if t["status"] in ("pending", "in_progress"):
                            t["status"] = "completed"
                    yield _sse_event({"type": "plan.update", "tasks": list(_todo_list)})  # 推 plan.update
                continue

            # ── TodoWrite: emit plan.update SSE and show step card ──
            # ── TodoWrite：发 plan.update SSE 并展示 step 卡片 ──
            if action and action.lower() == "todowrite":
                pending_thoughts.pop(round_num, [])  # 清空缓存
                pending_action_intentions.pop(round_num, None)
                pending_action_reasons.pop(round_num, None)
                # Extract todos from observation JSON
                # 从 observation JSON 中提取 todos
                obs_text = action_output.get("observations") or action_output.get(
                    "content"
                )
                todos_payload: List[Dict[str, str]] = []
                if obs_text:
                    try:
                        obs_json = (
                            json.loads(obs_text)
                            if isinstance(obs_text, str)
                            else obs_text
                        )
                        if isinstance(obs_json, dict):
                            todos_payload = obs_json.get("__todos__", [])  # 取 __todos__ 字段
                    except Exception:
                        pass
                # Fallback: read from the closure variable
                # 兜底：从闭包变量读
                if not todos_payload and _todo_list:
                    todos_payload = list(_todo_list)

                _td_total = len(todos_payload)  # 总数
                _td_done = sum(  # 已完成数
                    1 for t in todos_payload if t.get("status") == "completed"
                )
                if _td_done == 0:  # 状态判断
                    todo_state = "init"
                elif _td_done == _td_total and _td_total > 0:
                    todo_state = "done"
                else:
                    todo_state = "progress"

                todo_meta = {  # todo 元数据
                    "state": todo_state,
                    "done": _td_done,
                    "total": _td_total,
                }
                _todo_step_title = (  # step 标题：TODO::state:done/total
                    f"TODO::{todo_state}:{_td_done}/{_td_total}"
                    if _td_total > 0
                    else f"TODO::{todo_state}"
                )

                # Emit or update the step card for this round
                # NOTE: Do NOT set phase — let it fall into the default
                # "Execution Steps" group so todowrite cards appear inline
                # alongside other action steps in chronological order.
                # 发送或更新该轮的 step 卡片
                # 注意：不设 phase，让它落到默认的 "Execution Steps" 分组，
                # 让 todowrite 卡片与其他 action 步骤按时间顺序内联展示
                if round_num in round_step_map:  # 该轮已有 step
                    todo_step_id = round_step_map[round_num]
                    yield _sse_event(  # 更新已有 step 的标题
                        {
                            "type": "step.start",
                            "step": step,
                            "id": todo_step_id,
                            "title": _todo_step_title,
                            "detail": "todowrite",
                            "todo_meta": todo_meta,
                        }
                    )
                else:  # 该轮无 step，新建
                    todo_step_id, todo_step_event = build_step(
                        _todo_step_title,
                        "todowrite",
                    )
                    round_step_map[round_num] = todo_step_id
                    yield _sse_event(
                        {
                            "type": "step.start",
                            "step": step,
                            "id": todo_step_id,
                            "title": _todo_step_title,
                            "detail": "todowrite",
                            "todo_meta": todo_meta,
                        }
                    )

                yield _sse_event({"type": "plan.update", "tasks": todos_payload})  # 推 plan.update
                yield step_meta(  # 推 step.meta
                    round_step_map[round_num],
                    None,
                    action,
                    None,
                    _todo_step_title,
                    todo_meta=todo_meta,
                )
                history_steps.append(  # 记录到 history
                    {
                        "id": round_step_map[round_num],
                        "title": _todo_step_title,
                        "detail": "todowrite",
                        "thought": None,
                        "action_intention": None,
                        "action_reason": None,
                        "action": action,
                        "action_input": None,
                        "outputs": [],
                        "status": "done",
                        "todo_meta": todo_meta,
                    }
                )
                yield step_done(round_step_map[round_num])  # 推 step.done
                continue

            # Collect buffered thoughts for history persistence
            # (already streamed to frontend via thinking_chunk handler)
            # 收集缓存的 thoughts 用于历史持久化（已通过 thinking_chunk handler 流到前端）
            buffered_thoughts = pending_thoughts.pop(round_num, [])
            thought_text = None
            if buffered_thoughts:
                full_thought = "".join(buffered_thoughts)  # 拼成完整 thinking
                full_thought = re.split(r"\n\s*Action\s*:", full_thought, maxsplit=1)[
                    0
                ].strip()  # 去掉 Action: 之后部分
                if full_thought.startswith("Thought:"):  # 去掉 Thought: 前缀
                    full_thought = full_thought[len("Thought:") :].strip()
                if full_thought:
                    thought_text = full_thought
            action_intention = normalize_display_text(  # 归一化 intention（多个来源兜底）
                action_output.get("action_intention")
                or pending_action_intentions.pop(round_num, None)
                or action_output.get("phase")
            )
            action_reason = normalize_display_text(  # 归一化 reason
                action_output.get("action_reason")
                or pending_action_reasons.pop(round_num, None)
            )
            display_thought = action_intention or summarize_thought(  # 显示用的 thought（intention 优先，否则摘要）
                thought_text or thoughts, action
            )

            # Use the actual action name as the step title (Manus-style UI)
            # 用 action 名作为 step 标题（Manus 风格 UI）
            action_title = action or f"ReAct Round {round_num}"
            if round_num in round_step_map:  # 已有 step（从 thinking 创建的）
                # Step already exists (from thinking) - update title with same id
                # 更新已有 step 的标题为 action 名
                react_step_id = round_step_map[round_num]
                updated_event = _sse_event(
                    {
                        "type": "step.start",
                        "step": step,
                        "id": react_step_id,
                        "title": action_title,
                        "detail": "Thought/Action/Observation",
                    }
                )
                yield updated_event
            else:  # 没有就新建
                react_step_id, react_step_event = build_step(
                    action_title,
                    "Thought/Action/Observation",
                )
                round_step_map[round_num] = react_step_id
                yield react_step_event

            # --- History: create step record ---
            # --- 历史：创建 step 记录 ---
            action_input_str = None
            if action_input is not None:  # 序列化 action_input 为字符串
                action_input_str = (
                    action_input
                    if isinstance(action_input, str)
                    else json.dumps(action_input, ensure_ascii=False)
                )
            current_history_step = {  # 当前 step 历史记录
                "id": react_step_id,
                "title": action_title,
                "detail": "Thought/Action/Observation",
                "thought": display_thought,
                "action_intention": action_intention,
                "action_reason": action_reason,
                "action": action,
                "action_input": action_input_str,
                "outputs": [],
                "status": "running",
            }

            # Stream action code to frontend for right panel
            # (code_interpreter)
            # 如果是 code_interpreter，把代码作为 code chunk 流到前端右面板
            code_payload = None
            if action == "code_interpreter" and isinstance(action_input_data, dict):
                code_payload = action_input_data.get("code")
            if isinstance(code_payload, str) and code_payload.strip():
                yield step_chunk(react_step_id, "code", code_payload)  # 推 code chunk
                if current_history_step is not None:
                    current_history_step["outputs"].append(  # 记录到 history
                        {"output_type": "code", "content": code_payload}
                    )

            # Emit thinking metadata
            # 推 thinking 元数据（thoughts / action / action_input）
            if thoughts or action or action_input:
                step_action_input = (  # code_interpreter 的 action_input 不再重复推（已作为 code chunk）
                    None if action == "code_interpreter" else action_input
                )
                yield step_meta(
                    react_step_id,
                    display_thought,
                    action,
                    step_action_input,
                    action_title,
                    action_intention=action_intention,
                    action_reason=action_reason,
                )

            # Emit observation (action execution result)
            # 推 observation（action 执行结果）
            observation_text = action_output.get("observations") or action_output.get(
                "content"
            )
            if observation_text:
                raw_chunks = emit_tool_chunks(react_step_id, observation_text)  # 解析 chunks
                if raw_chunks:  # 有结构化 chunks
                    for chunk in raw_chunks:
                        yield chunk
                else:  # 无结构化 chunks，按文本分片发出
                    for chunk in chunk_text(str(observation_text), max_len=600):
                        yield step_chunk(react_step_id, "text", chunk)
                # --- History: collect outputs from observation ---
                # --- 历史：从 observation 收集 outputs ---
                if current_history_step is not None:
                    parsed_obs = None
                    if isinstance(observation_text, str):
                        try:
                            parsed_obs = json.loads(observation_text)  # 尝试解析为 JSON
                        except Exception:
                            pass
                    if isinstance(parsed_obs, dict) and isinstance(  # 是 {"chunks": [...]} 形式
                        parsed_obs.get("chunks"), list
                    ):
                        for item in parsed_obs["chunks"]:  # 把每个 chunk 记录到 history
                            if isinstance(item, dict):
                                current_history_step["outputs"].append(
                                    {
                                        "output_type": item.get("output_type", "text"),
                                        "content": item.get("content"),
                                    }
                                )
                    elif isinstance(observation_text, str) and observation_text:  # 纯文本
                        current_history_step["outputs"].append(
                            {
                                "output_type": "text",
                                "content": observation_text,
                            }
                        )

            # Mark step as done and track as last completed
            # 标记 step 完成（或失败）
            status = "done" if action_output.get("is_exe_success", True) else "failed"
            yield step_done(react_step_id, status)  # 推 step.done
            if (  # 满足条件时自动推进 todo
                status == "done"
                and action
                and action.lower() != "todowrite"
                and should_advance_todo(
                    action, thought_text or thoughts, observation_text
                )
            ):
                updated_todos = advance_todo_list()
                if updated_todos:
                    yield _sse_event({"type": "plan.update", "tasks": updated_todos})  # 推 plan.update
            # --- History: finalize step ---
            # --- 历史：终结 step ---
            if current_history_step is not None:
                current_history_step["status"] = status
                history_steps.append(current_history_step)
                current_history_step = None

    try:
        reply = await agent_task  # 等待 agent 任务完成
    except Exception as e:  # agent 执行异常
        err_msg = f"React agent failed: {e}"
        error_payload = json.dumps(  # 错误 payload（结构化）
            {
                "version": 1,
                "type": "react-agent",
                "final_content": err_msg,
                "steps": history_steps,
                "task_plan": list(_todo_list),
                "generated_images": react_state.get("generated_images", []),
            },
            ensure_ascii=False,
        )
        storage_conv.add_view_message(error_payload)  # 写入会话 view 消息
        storage_conv.end_current_round()  # 结束本轮
        storage_conv.save_to_storage()  # 保存
        yield _sse_event({"type": "final", "content": err_msg})  # 推 final
        yield _sse_event({"type": "done"})  # 推 done
        return

    if reply.action_report and reply.action_report.terminate:  # 正常 terminate 结束
        raw_content = reply.action_report.content or ""
        # The terminate ActionOutput.content is the full raw LLM text, e.g.:
        # "Thought: ...\nAction: terminate\nAction Input: {"result": "..."}"
        # We need to extract the "result" value from Action Input.
        # terminate 的 ActionOutput.content 是完整 LLM 原文，需要从中提取 "result"
        final_content = raw_content
        try:
            steps = parser.parse(raw_content)  # 解析 ReAct 步骤
            if steps:
                action_input = steps[0].action_input  # 取 Action Input
                if action_input:
                    # action_input could be a string like '{"result": "..."}'
                    # action_input 可能是字符串 '{"result": "..."}'
                    if isinstance(action_input, str):
                        parsed_input = json.loads(action_input)
                    else:
                        parsed_input = action_input
                    if isinstance(parsed_input, dict) and "result" in parsed_input:
                        final_content = parsed_input["result"]  # 提取 result
        except Exception:
            pass
    elif reply.action_report:  # 循环结束但未 terminate（达到最大步数或超时）
        # Loop ended without terminate (max retries or timeout).
        # reply.content is raw LLM output containing ReAct prefixes.
        # Try to extract a clean summary from the last step's thought.
        # 循环未 terminate 而结束；尝试从最后一步的 thought/observation 提取摘要
        raw = reply.content or reply.action_report.content or ""
        final_content = raw
        try:
            steps = parser.parse(raw)
            if steps:
                last_step = steps[-1]
                # Prefer observation (execution result) > thought
                # 优先用 observation，其次 thought
                if last_step.observations:
                    final_content = last_step.observations
                elif last_step.thoughts:
                    final_content = last_step.thoughts
        except Exception:
            pass
        # Fallback: strip remaining ReAct prefixes via regex
        # 兜底：用正则去掉 ReAct 前缀
        final_content = re.sub(
            r"^(Thought|Action|Action Input|Observation|Phase):\s*",
            "",
            final_content,
            flags=re.MULTILINE,
        ).strip()
        if not final_content:  # 仍为空时给默认提示
            final_content = "任务执行已达到最大步数限制，请查看上方各步骤的执行结果。"
    else:  # 没有 action_report
        final_content = reply.content or ""

    # Persist AI reply with structured history payload
    # 持久化 AI 回复（含结构化历史 payload）
    history_payload = json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": final_content,
            "steps": history_steps,
            "task_plan": list(_todo_list),
            "generated_images": react_state.get("generated_images", []),
        },
        ensure_ascii=False,
    )
    storage_conv.add_view_message(history_payload)  # 写入 view 消息
    storage_conv.end_current_round()  # 结束本轮
    storage_conv.save_to_storage()  # 保存

    yield _sse_event({"type": "final", "content": final_content})  # 推 final
    yield _sse_event({"type": "done"})  # 推 done


# ---------------------------------------------------------------------------
# Share link APIs
# ---------------------------------------------------------------------------
# 分享链接 API（创建/查看/删除会话分享）


class ShareCreateRequest(_BaseModel):  # 创建分享链接的请求体
    """Request body for creating a share link."""

    conv_uid: str  # 要分享的会话 ID


class ShareCreateResponse(_BaseModel):  # 创建分享链接的响应体
    """Response body for share link creation."""

    token: str  # 分享 token（URL 中的唯一标识）
    conv_uid: str  # 对应的会话 ID
    share_url: str  # 相对路径的分享 URL（前端拼 host 成绝对 URL）


class ShareConvResponse(_BaseModel):  # 查看分享会话的响应体
    """Public payload returned when viewing a shared conversation."""

    conv_uid: str  # 会话 ID
    token: str  # 分享 token
    messages: list  # list[{role, context, order}]  # 消息列表（含 role/context/order）


def _get_share_dao():  # 懒加载 ShareLinkDao（避免 import 时副作用）
    """Lazily instantiate the ShareLinkDao (avoids import-time side-effects)."""
    from dbgpt_app.share.models import ShareLinkDao  # 局部 import

    return ShareLinkDao()  # 返回 DAO 实例


def _get_conversation_service():  # 取 ConversationServe Service 组件
    """Return the ConversationServe Service component."""
    from dbgpt_serve.conversation.config import SERVE_SERVICE_COMPONENT_NAME  # 组件名常量
    from dbgpt_serve.conversation.service.service import Service  # Service 类型

    return CFG.SYSTEM_APP.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)  # 从 SystemApp 取组件


@router.post("/v1/chat/share", response_model=Result)  # POST /v1/chat/share：创建分享
async def create_share_link(
    body: ShareCreateRequest = Body(),  # 请求体（含 conv_uid）
    user_token: UserRequest = Depends(get_user_from_headers),  # 从 header 取用户身份
):
    """Create (or return existing) share link for a conversation.

    The returned ``share_url`` is a relative path that the client should
    prepend with the current host to form an absolute URL.
    """
    dao = _get_share_dao()  # 取 DAO
    created_by = user_token.user_id if user_token else None  # 创建者
    entity = dao.create_share(conv_uid=body.conv_uid, created_by=created_by)  # 创建分享
    if entity is None:  # 创建失败
        return Result.failed(msg="Failed to create share link")
    return Result.succ(  # 返回分享信息
        ShareCreateResponse(
            token=entity.token,
            conv_uid=entity.conv_uid,
            share_url=f"/share/{entity.token}",  # 相对路径
        )
    )


@router.get("/v1/chat/share/{token}", response_model=Result)  # GET /v1/chat/share/{token}：查看分享（公开）
async def get_share_conversation(token: str):
    """Public endpoint — no authentication required.

    Returns the full conversation history for the given share token so that the
    replay page can reconstruct and animate the session.
    """
    dao = _get_share_dao()  # 取 DAO
    link = dao.get_by_token(token)  # 按 token 查分享
    if link is None:  # 找不到时 404
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Share link not found")

    service = _get_conversation_service()  # 取会话 service
    from dbgpt_serve.conversation.api.schemas import ServeRequest

    history = service.get_history_messages(ServeRequest(conv_uid=link.conv_uid))  # 加载会话全部消息

    messages = [  # 转成简洁 dict 列表
        {"role": m.role, "context": m.context, "order": m.order}
        for m in (history or [])
    ]
    return Result.succ(
        ShareConvResponse(
            conv_uid=link.conv_uid,
            token=token,
            messages=messages,
        )
    )


@router.delete("/v1/chat/share/{token}", response_model=Result)  # DELETE /v1/chat/share/{token}：撤销分享
async def delete_share_link(
    token: str,
    user_token: UserRequest = Depends(get_user_from_headers),  # 校验身份
):
    """Revoke a share link.  Only the owner (or any authenticated user) may delete."""
    dao = _get_share_dao()  # 取 DAO
    deleted = dao.delete_by_token(token)  # 删除分享
    if not deleted:  # 找不到时 404
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Share link not found")
    return Result.succ({"deleted": True, "token": token})  # 返回删除结果


@router.get("/v1/agent/files/download")  # GET /v1/agent/files/download：下载 agent 生成的文件
async def download_agent_file(
    file_path: str = Query(..., description="Absolute path to the file to download"),  # 文件绝对路径
):
    """Download a file created by agent tools (shell_interpreter, code_interpreter).

    Only files under allowed directories (/tmp, PILOT_PATH/tmp/) can be downloaded.
    This prevents arbitrary file access on the server.
    """
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    from dbgpt.configs.model_config import PILOT_PATH, ROOT_PATH

    # If path is not absolute, resolve relative to ROOT_PATH (sandbox working dir)
    # 如果不是绝对路径，相对 ROOT_PATH 解析（沙箱工作目录）
    if not os.path.isabs(file_path):
        file_path = os.path.join(ROOT_PATH, file_path)

    # Resolve to absolute path and prevent path traversal
    # 解析为绝对路径，防止路径穿越
    try:
        resolved = os.path.realpath(file_path)
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Allowed base directories for agent-created files
    # 允许下载的目录白名单（沙箱生成的文件只能落到这些目录）
    allowed_dirs = [
        os.path.realpath("/tmp"),
        os.path.realpath(os.path.join(PILOT_PATH, "tmp")),
        os.path.realpath(ROOT_PATH),
    ]

    if not any(resolved.startswith(d + os.sep) or resolved == d for d in allowed_dirs):  # 不在白名单
        raise HTTPException(
            status_code=403,
            detail="Access denied: file is not in an allowed directory",
        )

    if not os.path.isfile(resolved):  # 文件不存在
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(resolved)  # 取文件名
    return FileResponse(  # 返回文件流
        path=resolved,
        filename=filename,
        media_type="application/octet-stream",  # 二进制流
    )


@router.get("/v1/agent/skills/download")  # GET /v1/agent/skills/download：下载技能 zip 包
async def download_skill_package(
    skill_name: str = Query(..., description="Skill folder name"),  # 技能名
    user_token: UserRequest = Depends(get_user_from_headers),  # 校验身份
):
    """Download a skill folder as a .zip archive."""
    from fastapi import HTTPException

    if not skill_name:  # 缺参数
        raise HTTPException(status_code=400, detail="skill_name is required")

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()  # 技能根目录
    skill_path = (skills_dir / skill_name).resolve()  # 目标技能目录

    # Security: ensure path is under skills_dir
    # 安全检查：技能路径必须在 skills_dir 之下
    try:
        skill_path.relative_to(skills_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not skill_path.is_dir():  # 技能不存在
        raise HTTPException(status_code=404, detail="Skill not found")

    # Build zip in memory
    # 在内存中构建 zip 包
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:  # 创建 zip
        for root, _dirs, files in os.walk(skill_path):  # 遍历技能目录
            for fname in files:
                abs_file = os.path.join(root, fname)  # 绝对路径
                arc_name = os.path.relpath(abs_file, skill_path)  # zip 内相对路径
                zf.write(abs_file, arcname=os.path.join(skill_name, arc_name))  # 写入 zip（顶层是技能名）
    buf.seek(0)  # 重置指针

    return StreamingResponse(  # 返回 zip 流
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{skill_name}.zip"',  # 下载文件名
        },
    )


@router.post("/v1/chat/react-agent")  # POST /v1/chat/react-agent：核心 ReAct Agent 入口
async def chat_react_agent(
    dialogue: ConversationVo = Body(),  # 会话请求体
    user_token: UserRequest = Depends(get_user_from_headers),  # 校验身份
):
    logger.info(  # 记录请求信息
        "chat_react_agent:%s,%s,%s",
        dialogue.chat_mode,
        dialogue.select_param,
        dialogue.model_name,
    )
    dialogue.user_name = user_token.user_id if user_token else dialogue.user_name  # 注入用户名
    headers = {  # SSE 响应头
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    try:
        return StreamingResponse(  # 返回 SSE 流
            _react_agent_stream(dialogue),  # 流式生成器
            headers=headers,
            media_type="text/event-stream",
        )
    except Exception as e:  # 异常时返回错误流
        logger.exception("React Agent Exception!%s", dialogue, exc_info=e)

        async def error_text(err_msg):  # 错误流生成器
            yield f"data:{err_msg}\n\n"

        return StreamingResponse(
            error_text(str(e)),
            headers=headers,
            media_type="text/plain",  # 错误用纯文本
        )
