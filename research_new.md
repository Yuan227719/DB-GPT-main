# DB-GPT 项目架构与运行流程深度解析

> 本文档基于对 DB-GPT 源码（v0.8.1）的全面分析，涵盖项目整体架构、模块关系、启动流程、核心子系统设计及数据流。

***

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构图](#2-整体架构图)
3. [目录结构](#3-目录结构)
4. [启动流程](#4-启动流程)
5. [配置系统](#5-配置系统)
6. [模型管理系统](#6-模型管理系统)
7. [RAG 与知识管理](#7-rag-与知识管理)
8. [Agent 系统](#8-agent-系统)
9. [AWEL 工作流引擎](#9-awel-工作流引擎)
10. [API 层](#10-api-层)
11. [前端架构](#11-前端架构)
12. [组件与插件系统](#12-组件与插件系统)
13. [存储层](#13-存储层)
14. [代码沙箱](#14-代码沙箱)
15. [Serve 层](#15-serve-层)
16. [数据流总结](#16-数据流总结)
17. [常见配置与运维操作](#17-常见配置与运维操作)
18. [MCP 与连接器系统](#18-mcp-与连接器系统)
19. [可视化系统 (Vis)](#19-可视化系统-vis)
20. [场景系统 (Scene)](#20-场景系统-scene)
21. [资源系统 (Resource)](#21-资源系统-resource)
22. [工具系统 (Tool)](#22-工具系统-tool)
23. [Agent Profile 系统](#23-agent-profile-系统)
24. [Skills 技能集成](#24-skills-技能集成)
25. [API V1 深度分析](#25-api-v1-深度分析)
26. [数据源系统详情](#26-数据源系统详情)
27. [缓存系统](#27-缓存系统)
28. [全文搜索与图存储](#28-全文搜索与图存储)
29. [嵌入模型管理](#29-嵌入模型管理)
30. [评估与基准测试系统](#30-评估与基准测试系统)
31. [链路追踪系统](#31-链路追踪系统)
32. [对话管理系统](#32-对话管理系统)
33. [模型集群与 Worker 管理](#33-模型集群与-worker-管理)
34. [客户端 SDK](#34-客户端-sdk)
35. [补充子系统](#35-补充子系统)
36. [Chat 请求全链路](#36-chat-请求全链路)
37. [数据库连接配置全流程](#37-数据库连接配置全流程)
38. [RAG 知识库摄取全流程](#38-rag-知识库摄取全流程)
39. [AWEL 工作流执行流程](#39-awel-工作流执行流程)

***

## 1. 项目概述

DB-GPT 是一个开源的 AI 原生数据应用开发框架，基于大语言模型（LLM）与数据库（DB）的深度融合，提供 RAG（检索增强生成）、Agent（智能体）、AWEL（工作流编排）、数据对话等核心能力。

### 技术栈

| 类别     | 技术                                     | 版本/说明           |
| ------ | -------------------------------------- | --------------- |
| 后端框架   | FastAPI + Uvicorn                      | ASGI 服务         |
| CLI 框架 | Click + Rich                           | 命令行交互           |
| ORM    | SQLAlchemy                             | 2.0.25\~2.0.29  |
| 数据库迁移  | Alembic                                | 1.12.0          |
| 包管理    | uv (workspace)                         | Monorepo 管理     |
| 构建后端   | Hatchling                              | Python wheel 构建 |
| 前端框架   | Next.js 13 + React 18                  | TypeScript      |
| UI 库   | Ant Design 5 + MUI 5 + TailwindCSS     | <br />          |
| 向量存储   | ChromaDB（默认）/ Milvus / Weaviate 等      | 8 种可选           |
| 模型推理   | Transformers / vLLM / llama.cpp / MLX  | 本地模型            |
| LLM 代理 | OpenAI SDK / Anthropic SDK / LiteLLM 等 | 21 个 Provider   |
| Python | >= 3.10                                | <br />          |

***

## 2. 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户 (Web UI / API / CLI)                      │
└──────────────┬──────────────────────────┬────────────────────────────┘
               │                          │
    ┌──────────▼──────────┐   ┌──────────▼──────────┐
    │   Next.js 前端       │   │  Python Client SDK  │
    │   (web/ 目录)        │   │  (dbgpt-client)     │
    └──────────┬──────────┘   └──────────┬──────────┘
               │  HTTP / WebSocket       │
┌──────────────▼─────────────────────────▼────────────────────────────┐
│                     dbgpt-app (FastAPI 服务层)                       │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐ │
│  │ API V1  │ │ API V2   │ │ Scene    │ │ Operators │ │ Component │ │
│  │ 路由    │ │ OpenAI兼容│ │ 聊天场景 │ │ AWEL算子  │ │ 注册中心  │ │
│  └─────────┘ └──────────┘ └──────────┘ └───────────┘ └───────────┘ │
└──────┬────────────┬─────────────┬─────────────┬────────────────────┘
       │            │             │             │
┌──────▼──────┐ ┌──▼──────────┐ ┌▼───────────┐ ┌▼──────────────┐
│ dbgpt-serve │ │ dbgpt-core  │ │ dbgpt-ext  │ │dbgpt-sandbox  │
│ (15个Serve │ │ (核心库)     │ │ (扩展库)   │ │ (代码沙箱)    │
│  服务模块)  │ │             │ │            │ │               │
│             │ │ ┌─────────┐ │ │            │ └───────────────┘
│ Prompt      │ │ │ Agent   │ │ │ RAG扩展    │
│ Flow(AWEL)  │ │ │ AWEL    │ │ │ 存储引擎   │
│ RAG         │ │ │ Model   │ │ │ 数据源     │
│ Datasource  │ │ │ RAG     │ │ │            │
│ Evaluate    │ │ │ Storage │ │ │            │
│ Model       │ │ │ Vis     │ │ │            │
│ Connector   │ │ └─────────┘ │ │            │
│ ...         │ │             │ │            │
└─────────────┘ └─────────────┘ └────────────┘
```

### 包依赖关系

```
dbgpt-core     ← 核心库（组件系统、AWEL DAG、存储、Agent、模型适配器、RAG）
    ↑
dbgpt-ext      ← 扩展库（额外数据源连接器、RAG扩展、存储引擎）
    ↑
dbgpt-serve    ← Serve 模块（标准化服务模块：flow、rag、prompt、model 等）
    ↑
dbgpt-app      ← 应用层（FastAPI 服务器、API 路由、场景、初始化）

dbgpt-sandbox  ← 独立的沙箱执行服务（不依赖 app 层）
dbgpt-client   ← Python 客户端 SDK
```

***

## 3. 目录结构

### 顶层目录

| 目录              | 说明                                 |
| --------------- | ---------------------------------- |
| `packages/`     | Monorepo 核心代码，包含 7 个 Python 子包     |
| `configs/`      | TOML 配置文件模板（各种 LLM provider 的示例配置） |
| `web/`          | Next.js 前端项目                       |
| `docker/`       | Docker 构建文件（base / allinone）       |
| `docs/`         | Docusaurus 文档站                     |
| `examples/`     | Python 示例代码（agents, rag, client 等） |
| `scripts/`      | 安装/构建脚本（含 `install/` 和 `lib/` 辅助库） |
| `pilot/`        | 示例数据和 Alembic 迁移模板                 |
| `skills/`       | 内置 Skill 定义（SKILL.md 格式）           |
| `tests/`        | 单元测试                               |
| `requirements/` | 开发/lint 依赖                         |
| `assets/`       | 静态图片和 SQL schema                   |

### packages/ 子包详情

```
packages/
├── dbgpt-core/              # 核心包 (name="dbgpt")
│   └── src/dbgpt/
│       ├── agent/           # Agent 框架（角色、记忆、团队协作）
│       ├── cli/             # CLI 脚本和配置向导（_profiles.py, _wizard.py, _config.py）
│       ├── configs/         # 模型配置
│       ├── core/            # AWEL DAG/Flow 引擎
│       ├── datasource/      # 数据源抽象
│       ├── model/           # 模型集群管理（adapter/cluster/proxy）
│       ├── rag/             # RAG 组件（embedding/retriever/extractor）
│       ├── storage/         # 存储抽象（cache/vector_store/graph_store/metadata）
│       ├── util/            # 工具类（configure/module_utils 等）
│       └── vis/             # 可视化
├── dbgpt-app/               # 应用层包 (name="dbgpt-app")
│   └── src/dbgpt_app/
│       ├── _cli.py          # webserver 启动命令定义
│       ├── dbgpt_server.py  # FastAPI 服务主入口
│       ├── base.py          # 初始化逻辑（DB、迁移）
│       ├── component_configs.py  # 组件注册中心
│       ├── config.py        # ApplicationConfig 数据类
│       ├── openapi/         # API V1/V2 路由
│       ├── scene/           # 聊天场景（chat_db, chat_data, chat_normal）
│       ├── operators/       # AWEL 算子（rag, llm 等）
│       └── static/          # 前端静态文件
├── dbgpt-ext/               # 扩展包（RAG, datasource 连接器, 存储引擎）
├── dbgpt-serve/             # 服务层包（15 个 Serve 模块）
├── dbgpt-client/            # 客户端 SDK
├── dbgpt-sandbox/           # 代码沙箱（独立服务）
└── dbgpt-accelerator/       # 加速器包（dbgpt-acc-auto, dbgpt-acc-flash-attn）
```

### Monorepo 配置

根 `pyproject.toml` 定义了 uv workspace：

```toml
[tool.uv.workspace]
members = [
  "packages/dbgpt-app",
  "packages/dbgpt-client",
  "packages/dbgpt-core",
  "packages/dbgpt-ext",
  "packages/dbgpt-serve",
  "packages/dbgpt-sandbox",
  "packages/dbgpt-accelerator/dbgpt-acc*",
]
```

所有子包通过 `{ workspace = true }` 声明为本地 workspace 依赖。

***

## 4. 启动流程

### 4.1 完整启动调用链

从 `dbgpt start webserver --profile glm` 到 Uvicorn 运行的完整流程，分为 **4 个阶段**：

#### 阶段一：CLI 命令解析 (`cli_scripts.py`)

用户敲下 `dbgpt start webserver --profile glm`，触发 Click 命令路由：

```
dbgpt                  → cli() 回调（设置日志级别）
  └── start            → start group（invoke_without_command=True）
        └── webserver  → start_webserver() 执行
```

`cli()` 作为根 group 的 callback **总是先执行**（参见 [cli_scripts.py](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-core/src/dbgpt/cli/cli_scripts.py#L25-L26) L25-L26），根据 `--log-level` 参数（默认 `warn`）设置全局日志级别。这一步保证后续所有 `logger.info()` / `logger.debug()` 的输出可见。

#### 阶段二：配置文件解析 (`_cli.py` → `_wizard.py`)

`start_webserver()` ([_cli.py](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/_cli.py#L101) L101) 接收 `--profile` 和 `--config` 参数后，调用 `maybe_run_wizard()` ([_wizard.py](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-core/src/dbgpt/cli/_wizard.py#L158) L158) 解析配置文件路径，**优先级**如下：

1. `--config` 显式指定路径 → 直接使用（不做 wizard）
2. `--profile glm` → 去 `~/.dbgpt/configs/glm.toml` 查找，存在则返回绝对路径
3. `--yes` 标志 → 非交互式自动生成配置（`run_setup_noninteractive`）
4. 都不满足 → 启动交互式配置向导（`run_setup_wizard`）

最后 `maybe_run_wizard()` 返回一个**配置文件的绝对路径字符串**，传给 `run_webserver()`。

#### 阶段三：配置加载 (`dbgpt_server.py` → `load_config()`)

`run_webserver()` ([dbgpt_server.py](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py#L282) L282) 拿到配置文件路径后，调用 `load_config()` ([L340](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py#L340))：

**3a. 路径兜底**（L344-L350）：`config_file` 为 `None` 时用项目自带 `dbgpt-proxy-siliconflow.toml` 兜底；为相对路径时拼接到项目根目录。

**3b. TOML 解析**（L357）：`ConfigurationManager.from_file()` 用 `tomllib` 将 TOML 文件解析成字典，生成 `ConfigurationManager` 实例。你的 `openai.toml` 被解析为含 `[system]`、`[service]`、`[models]`、`[rag]` 等段的嵌套字典。

**3c. 系统配置**（L358）：`cfg.parse_config(SystemParameters, prefix="system")` 只取 `[system]` 段生成 Pydantic 对象，用于设置语言等全局参数。

**3d. Provider 扫描**（L365）：`scan_configs()` 扫描 `dbgpt.model.scan_model_providers()` 和 `scan_storage_configs()` 等，将所有模型 provider（`proxy/openai`、`proxy/zhipu` 等）和存储后端注册到 `ConfigurationManager` 的多态分发系统。

**3e. 应用配置**（L367）：`cfg.parse_config(ApplicationConfig, hook_section="hooks")` 解析**整个 TOML 文件**为一个大 Pydantic 容器，包含 `service.web`（端口、数据库）、`models`（LLM/Embedding/Rerank 列表）、`rag`（向量存储）、`trace`（链路追踪）等所有配置段。`hook_section="hooks"` 指定在加载后执行 `[hooks]` 段配置的 Hook（如 `EnvVarSetHook` 将 `${env:VAR:-default}` 展开为实际环境变量值）。

#### 阶段四：应用初始化 (`initialize_app()`)

`run_webserver()` 拿到 `ApplicationConfig` 后，将其注入全局配置容器 `config.configs["app_config"] = param`，然后**用 `root_tracer` 包裹**整个初始化过程，最后调用 `initialize_app()` ([L137](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py#L137))。这一阶段按序执行：

**4a. 日志设置**（L151-L155）：`setup_logging("dbgpt", log_config)` 初始化应用日志，输出到 `logs/dbgpt_webserver.log`。

**4b. 数据库初始化**（L157 → [base.py](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/base.py#L37) L37）：`server_init()` → `_initialize_db_storage()` 创建 SQLite 连接引擎和会话工厂。SQLite 路径由 TOML 的 `[service.web.database]` 段指定（默认 `pilot/meta_data/dbgpt.db`）。

**4c. 路由挂载**（L158）：`mount_routers(app)` 导入 `api_v1`、`api_v2`、`editor` 等所有 API 模块，将路由注册到 FastAPI `app` 上。此时路由已就绪但后端组件尚未初始化。

**4d. 组件注册**（L160-L163）：`initialize_components()` ([component_configs.py](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/component_configs.py#L14) L14) 按依赖顺序注册 20+ 个组件到 `SystemApp`。`SystemApp` 是全局 IoC 容器，各组件通过 `system_app.get_component()` 互相获取。注册顺序代表启动优先级：

| 注册项 | 用途 |
| ------ | ---- |
| `DefaultExecutorFactory` | 全局线程池（默认 `default_thread_pool_size` 个线程），所有同步阻塞任务（embedding、文件读写）通过它异步化 |
| `DefaultScheduler` | 定时任务调度器，管理后台定时任务 |
| `ModelController` | 模型集群控制器，负载均衡分发 LLM 请求到多个 worker |
| `ConnectorManager`（SQL 数据源） | 管理 SQL 数据源连接（MySQL/PG/SQLite 等），含连接池 |
| `StorageManager` | RAG 存储管理器，管理 Chroma/Elasticsearch 等向量存储 |
| `PluginHub` | 插件中心，管理第三方 Agent 插件（`module_plugin`） |
| `MultiAgents` | 多 Agent 编排控制器 |
| `EditorService` | SQL 编辑器服务（含 SQL 检查/优化） |
| Serve 模块（15 个） | `register_serve_apps()` 按 `configs/mode_serve.json` 扫描并注册 15 个 Serve 模块（agent/flow/datasource/knowledge/evaluate/model/prompt 等），每个 Serve 自带 REST API + 数据模型 + DAL |
| AWEL 引擎 | `_initialize_awel()` 从 `examples/awel/` 和用户自定义目录加载 DAG 定义文件 |
| Resource Manager | `_initialize_resource_manager()` 注册 Agent 可用的 9 类资源：数据源、知识库、插件、App、搜索工具、模型列表、主机状态、MCP 工具、Skill |
| Agent | `_initialize_agent()` 初始化 Agent 框架（ReAct/Conversable Agent 等） |
| Operators | `_initialize_operators()` 扫描 `dbgpt_app.operators` 和 `dbgpt_serve.agent.resource` 模块下所有 `BaseOperator` 子类并注册 |
| Prompt Templates | `_initialize_prompt_templates()` 批量 import 8 个场景的 prompt 模块（chat_db/chat_excel/chat_dashboard/chat_knowledge/chat_normal），将它们注册到 `PromptTemplateRegistry` |
| Model Cache | `_initialize_model_cache()` 可选启用 LLM 响应缓存（内存/磁盘/Redis） |
| Benchmark Data | `_initialize_benchmark_data()` 加载评测基准数据 |
| ConnectorManager（外部 MCP） | `_initialize_connector_manager()` 注册外部连接器管理器，从 `dbgpt_ext.connector/catalog.json` 加载连接器目录 |

**4e. 生命周期钩子**（L164-L172）：`system_app.on_init()` 通知所有组件的 `on_init()` 方法；`_migration_db_storage()` 执行 Alembic 数据库迁移（升级 schema）；`system_app.after_init()` 通知组件数据库就绪，可以做数据初始化操作。

**4f. 模型集群初始化**（L210-L249）：分两种模式：
- **统一部署模式**（`light=False`，默认）：所有模型 worker 和 controller 在同一进程内运行，配置来自 TOML 的 `[[models.llms]]` 数组
- **轻量模式**（`light=True`）：仅作为 API 客户端，连接远程 `controller_addr`

**4g. 静态文件挂载**（L251）：`mount_static_files()` 将 Next.js 构建的前端文件挂载到 FastAPI 根路径 `/`，包括 `/images/` 图片目录和 `/share/{token}` 分享页的动态路由兜底。

**4h. `before_start()`**（L254）：最后一个生命周期钩子，通知所有组件即将启动。

#### 最终阶段：Uvicorn 启动 (`run_uvicorn()`)

`run_uvicorn()` ([L258](file:///e:/embed_agent/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py#L258)) 对 FastAPI app 包装 CORS 中间件（允许所有跨域请求），然后调用 `uvicorn.run(cors_app, host, port)` 在 `0.0.0.0:5670` 上启动 ASGI 服务。

**完整符号流程：**

```
用户: dbgpt start webserver --profile glm
  │
  ├── cli_scripts.py:main() → cli()       # 设日志级别
  │   └── start group → start_webserver()
  │       ├─ _print_banner()
  │       └─ maybe_run_wizard(profile="glm")
  │           └─ → ~/.dbgpt/configs/glm.toml (绝对路径)
  │
  ├── run_webserver(resolved_config)      # dbgpt_server.py L282
  │   ├─ load_config(config_file)         # L340
  │   │   ├─ ConfigurationManager.from_file() → TOML → 字典
  │   │   ├─ parse_config(SystemParameters, prefix="system")
  │   │   ├─ set_default_language()
  │   │   ├─ scan_configs() (Provider + Storage 注册)
  │   │   └─ parse_config(ApplicationConfig, hook_section="hooks")
  │   │
  │   ├─ initialize_tracer()              # 链路追踪
  │   │
  │   └─ initialize_app(param)            # L137
  │       ├─ setup_logging("dbgpt")
  │       ├─ server_init() → _initialize_db_storage()
  │       ├─ mount_routers(app)
  │       ├─ initialize_components(param, system_app)
  │       │   ├─ register(DefaultExecutorFactory)
  │       │   ├─ register(DefaultScheduler)
  │       │   ├─ register_instance(controller)
  │       │   ├─ register(ConnectorManager) (SQL)
  │       │   ├─ register(StorageManager)
  │       │   ├─ register_instance(module_plugin)
  │       │   ├─ register_instance(multi_agents)
  │       │   ├─ _initialize_embedding_model()
  │       │   ├─ _initialize_rerank_model()
  │       │   ├─ _initialize_model_cache()
  │       │   ├─ _initialize_awel()
  │       │   ├─ _initialize_resource_manager()
  │       │   │   ├─ initialize_skill(system_app)
  │       │   │   └─ rm.register_resource(9 类资源)
  │       │   ├─ _initialize_agent()
  │       │   ├─ _initialize_openapi()
  │       │   ├─ register_serve_apps(15 modules)
  │       │   ├─ _initialize_operators()
  │       │   ├─ _initialize_code_server()
  │       │   ├─ _initialize_prompt_templates()
  │       │   ├─ _initialize_benchmark_data()
  │       │   └─ _initialize_connector_manager() (MCP)
  │       ├─ system_app.on_init()
  │       ├─ _migration_db_storage()
  │       ├─ system_app.after_init()
  │       ├─ initialize_worker_manager_in_client()
  │       ├─ mount_static_files(app)
  │       └─ system_app.before_start()
  │
  └── run_uvicorn(param.service.web)      # L258
      ├─ CORSMiddleware 包装
      └─ uvicorn.run(cors_app, host=0.0.0.0, port=5670)
```

### 4.2 关键函数索引

| 函数                        | 文件路径                                                    | 行号  |
| ------------------------- | ------------------------------------------------------- | --- |
| `main()`                  | `packages/dbgpt-core/src/dbgpt/cli/cli_scripts.py`      | 344 |
| `start_webserver`         | `packages/dbgpt-app/src/dbgpt_app/_cli.py`              | 99  |
| `run_webserver()`         | `packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py`      | 282 |
| `load_config()`           | `packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py`      | 340 |
| `initialize_app()`        | `packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py`      | 137 |
| `run_uvicorn()`           | `packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py`      | 258 |
| `server_init()`           | `packages/dbgpt-app/src/dbgpt_app/base.py`              | 37  |
| `initialize_components()` | `packages/dbgpt-app/src/dbgpt_app/component_configs.py` | 14  |

### 4.3 CLI 命令注册机制

`cli_scripts.py` 通过多个 `try/except` 块（第233-341行）实现插件式命令注册，即使某个模块导入失败也不影响其他命令注册。命令别名通过 `add_command_alias()` 实现（如 `web` 和 `webserver` 是同一命令）。

***

## 5. 配置系统

### 5.1 配置文件层次

```
~/.dbgpt/
├── config.toml              # 全局配置（记录活跃 profile）
└── configs/
    └── glm.toml             # Profile 配置（实际使用的配置）
```

### 5.2 TOML 配置结构

以 `~/.dbgpt/configs/glm.toml` 为例：

```toml
# 系统配置
[system]
language = "${env:DBGPT_LANG:-en}"    # 支持 ${env:VAR:-default} 语法
api_keys = []
encrypt_key = "your_secret_key"

# Web 服务配置
[service.web]
host = "0.0.0.0"
port = 5670

[service.web.database]
type = "sqlite"
path = "pilot/meta_data/dbgpt.db"

# RAG 存储配置
[rag.storage.vector]
type = "chroma"
persist_path = "pilot/data"

# 模型配置
[models]
[[models.llms]]                      # 双括号 = 数组（可配多个 LLM）
name = "glm-4-plus"
provider = "proxy/zhipu"             # 多态分发字段
api_base = "https://open.bigmodel.cn/api/paas/v4"
api_key = "${env:ZHIPUAI_API_KEY:-sk-xxx}"

[[models.embeddings]]
name = "embedding-3"
provider = "proxy/openai"            # embedding 用 OpenAI 兼容接口
api_url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
api_key = "${env:ZHIPUAI_API_KEY:-sk-xxx}"
```

### 5.3 ConfigurationManager

核心文件：`packages/dbgpt-core/src/dbgpt/util/configure/manager.py`

**主要职责：**

1. **从 TOML 加载**：`from_file()` 方法（第309行）使用 `tomllib`/`tomli` 读取 TOML 文件
2. **环境变量替换**：`_resolve_env_vars()`（第195行）处理 `${env:VAR:-default}` 语法
3. **类型转换**：`_convert_to_dataclass()`（第532行）将字典递归转换为有类型的 dataclass 实例
4. **多态分发**：`_get_concrete_class()`（第228行）根据 `provider` 字段值从注册表查找实际子类

**多态类型系统核心：**

- `PolymorphicMeta`（元类，第44行）：在类创建时自动将子类注册到 `_type_registry` 字典
- `RegisterParameters`（第130行）：所有多态配置的基类，提供 `get_subclass(type_value)` 方法
- `__type_field__` = `"provider"`：指定 TOML 中的 `provider` 字段为多态分发键

### 5.3.1 PolymorphicMeta 多态元类 — 详细算法

`PolymorphicMeta`（`manager.py` L44-L89）是整个配置系统最核心的部分，通过 ABCMeta 实现 dataclass 的多态解析。

**注册算法** (`__new__` 方法):

```
1. 调用 super().__new__ 创建类
2. 如果基类中包含 RegisterParameters → 创建独立的 _type_registry 字典
3. 查找直接父类中的 PolymorphicMeta 基类
4. 获取 type_value 的优先级:
   a) 显式 __type__ 属性（最高优先级）
   b) __type_field__ 指定的字段值（如 provider="openai"）
   c) 自动推导: 移除父类名后缀并转小写
5. 解析环境变量（${env:VAR} 语法）
6. 注册: registry[type_value] = cls
7. 重复检测: 如果 type_value 已在注册表中则抛出 ValueError

**完整的三层优先级算法**：

```
第1层: __type__ 属性（显式声明）
  class MyConfig(RegisterParameters):
      __type__ = "my_custom_type"

第2层: __type_field__ 指定的字段值
  class MyConfig(RegisterParameters):
      __type_field__ = "provider"  # 使用 provider 字段作为类型标识
      provider: str = "openai"

第3层: 自动推导（移除父类名后缀）
  父类 LLMConfig → 子类 OpenAILLMConfig:
    type_value = "openai" (openai_llm_config → 移除 llm_config → "openai")
```

**`RegisterParameters` 关键方法**（`manager.py` L130-L192）：
- `get_subclass(type_value)`: 从注册表查找子类，注意 `type_value.lower()` 大小写不敏感
- `get_register_class()`: 返回 `_type_registry` 字典
- `register_subclass(type_value, subclass)`: 允许运行时手动注册
- `get_type_value()`: 递归获取类型值，优先级同上三层

在 `_get_concrete_class()`（L228-L248）中：
```python
type_field = getattr(base_class, "__type_field__", "type")  # L237
type_value = data.get(type_field)                            # L238
type_value = _resolve_env_vars(type_value)                   # L240
real_cls = base_class.get_subclass(type_value.lower())       # L241
```

### 5.3.2 HookConfig 与 Hook 执行系统

**HookConfig 结构**（`manager.py` L92-L128）:

```python
@dataclass
class HookConfig:
    path: str           # 类路径或函数路径, 如 'dbgpt.config.hooks.env_var_hook'
    init_params: Dict   # 类钩子的构造参数
    params: Dict        # 传递给钩子的运行时参数
    enabled: bool = True
```

**Hook 加载与执行** (`_load_hook`, L909-L942):

```
1. 遍历配置中的 hook_config 列表
2. 对每个 hook:
   a) 解析为 HookConfig 对象
   b) 检查 enabled 标志
   c) 通过 import_from_string 动态加载
   d) 如果指向类 → hook_cls(**init_params) 实例化
   e) 如果指向可调用对象 → 直接使用
3. 按声明顺序依次执行所有 hooks:
   config_section = hook(config_section, **params)
```

**在 `parse_config` 中的触发**（L647-L653）:
```python
if hook_section:
    hook_configs = config_section.get(hook_section, [])
    config_section = _load_hook(hook_configs, config_section)
```

### 5.3.3 EnvVarSetHook 实现

`env_hook.py`（L1-L41）提供了启动时自动设置环境变量的 Hook：

```python
class EnvVarSetHook:
    def __init__(self, env_vars: List[Dict[str, str]]):
        # 将 [{"key": "KEY", "value": "VALUE"}] 转为 {KEY: VALUE} 字典
    
    def __call__(self, config, **kwargs) -> Dict:
        # 1. 保存原始环境变量 (_original_env)
        # 2. 批量设置新环境变量
        # 3. 返回不变的配置
```

特点：是可调用对象（函数式 Hook），不是类钩子。修改环境变量但不改变配置内容。

### 5.3.4 DynConfig 动态热加载

`base.py`（L123-L163）提供的 `DynConfig` 工厂函数：

```python
def DynConfig(
    default=_MISSING,
    category=None,
    key=None,
    provider=None,     # ProviderType.ENV 或 ProviderType.PROMPT_MANAGER
    is_list=False,
    separator="[LIST_SEP]",
    description=None,
) -> ConfigInfo:
```

创建 `ConfigInfo` 对象，在运行时通过 `query()` 方法动态获取值：
1. 若有 `ConfigProvider` 实例 → `provider.query(key)`
2. 若 `provider == ProviderType.ENV` → `os.environ.get(key)`
3. 若 `provider == ProviderType.PROMPT_MANAGER` → 尝试从 PromptManager 获取
4. 若 `value is None` → 使用 `default` 值
5. 若 `is_list` → 用 separator 分割字符串为列表

**限制**：当前仅支持字符串或字符串列表类型。

### 5.3.5 `_convert_value` 边界情况一览

`ConfigurationManager._convert_value()`（`manager.py` L450-L530）的完整类型转换逻辑：

| 步骤 | 条件 | 行为 |
|------|------|------|
| None 值检查 | `value is None` | 检查 Optional 类型，非 Optional 则抛 ValueError |
| 环境变量解析 | `isinstance(value, str) and resolve_env_vars` | 替换 `${env:NAME}` 和 `${env:NAME:-default}` |
| 基本类型 | `str, int, float, bool` | 直接类型转换 |
| Optional 类型 | `origin is Union and None in args` | 递归处理内部类型 |
| List 类型 | `origin is list` | 递归转换每个元素，非 list 输入抛 ValueError |
| Dict 类型 | `origin is dict` | 递归转换 key 和 value，非 dict 输入抛 ValueError |
| 嵌套 dataclass | `is_dataclass(field_type)` | 调用 `_convert_to_dataclass`，非 dict 输入抛 ValueError |
| 兜底 | 其他 | 返回原值不变 |

**`_convert_to_dataclass` 多态解析流程**（L532-L605）:

```
1. 检查 _parse_class_ 方法（自定义解析钩子）
2. 调用 _get_concrete_class 确定实际子类
3. 递归准备字段值:
   a) MISSING + 有 default → 使用默认值
   b) MISSING + 有 default_factory → 调用 factory
   c) 都不是 MISSING → 调用 _convert_value
4. 检查 _from_dict_ 方法（自定义构造钩子）
5. 构造实例: concrete_cls(**field_values)
```

### 5.4 Profile 体系

**Shell Profiles（安装脚本用）：**

文件：`scripts/install/lib/profiles.sh`

| Profile              | uv extras                                           | API Key 环境变量        |
| -------------------- | --------------------------------------------------- | ------------------- |
| `openai`             | base, proxy\_openai, rag, storage\_chromadb, dbgpts | `OPENAI_API_KEY`    |
| `kimi`               | base, proxy\_openai, rag, storage\_chromadb, dbgpts | `MOONSHOT_API_KEY`  |
| `qwen`               | base, proxy\_openai, **proxy\_tongyi**, rag, ...    | `DASHSCOPE_API_KEY` |
| `minimax`            | base, proxy\_openai, rag, ...                       | `MINIMAX_API_KEY`   |
| `glm`                | base, proxy\_openai, **proxy\_zhipuai**, rag, ...   | `ZHIPUAI_API_KEY`   |
| `custom` / `default` | base, proxy\_openai, rag, ...                       | -                   |

**Python Profiles（配置生成用）：**

文件：`packages/dbgpt-core/src/dbgpt/cli/_profiles.py`

每个 `ProfileSpec` 包含完整的 provider 信息（LLM model/provider/api\_base、embedding model/provider/api\_url）。安装向导 `_wizard.py` 使用这些信息生成 TOML 配置。

### 5.5 配置文件生成流程

```
dbgpt setup --profile glm --yes
    │
    ├─ _wizard.py: run_setup_wizard() 或 run_setup_noninteractive()
    │   ├─ 选择 profile
    │   ├─ 获取 API key（环境变量 > 用户输入 > 占位符）
    │   └─ 生成模型配置
    │
    ├─ _config.py: _render_profile_toml()
    │   ├─ 生成 [system] 段
    │   ├─ 生成 [service.web] + [service.web.database] 段
    │   ├─ 生成 [rag.storage.vector] 段
    │   └─ 生成 [models] 段（[[models.llms]] + [[models.embeddings]]）
    │
    └─ write_profile_config()
        ├─ 写入 ~/.dbgpt/configs/<profile>.toml（权限 0o600）
        └─ 更新 ~/.dbgpt/config.toml（记录活跃 profile）
```

***

## 6. 模型管理系统

### 6.1 适配器体系

DB-GPT 的模型管理采用**适配器模式**，支持本地模型和远程代理两种模式。

**核心继承层次：**

```
BaseParameters
  └─ BaseDeployModelParameters  (__type_field__ = "provider")
       │
       ├─ LLMDeployModelParameters (__cfg_type__ = "llm")
       │    ├─ OpenAICompatibleDeployModelParameters  (provider="proxy/openai")
       │    │    └─ ZhipuDeployModelParameters (provider="proxy/zhipu")
       │    ├─ VLLMDeployModelParameters
       │    ├─ HFLLMDeployModelParameters
       │    └─ MLXDeployModelParameters
       │
       ├─ EmbeddingDeployModelParameters (__cfg_type__ = "embedding")
       │    ├─ HFEmbeddingDeployModelParameters (provider="hf")
       │    └─ OpenAPIEmbeddingDeployModelParameters (provider="proxy/openai")
       │
       └─ RerankerDeployModelParameters (__cfg_type__ = "reranker")
```

> **注意**：Embedding 目前只注册了 `hf` 和 `proxy/openai` 两种 provider。像 `proxy/zhipu` 这样的 embedding 类型尚未注册，需要使用 `proxy/openai` 替代（因为 ZhipuAI 的 embedding 接口是 OpenAI 兼容的）。

### 6.2 适配器注册机制

核心文件：`packages/dbgpt-core/src/dbgpt/model/adapter/base.py`

**三个全局注册表：**

- `model_adapters` — LLM 适配器列表
- `embedding_adapters` — Embedding 适配器列表

**注册函数：**

| 函数                               | 用途                               |
| -------------------------------- | -------------------------------- |
| `register_model_adapter()`       | 注册 LLM 适配器                       |
| `register_embedding_adapter()`   | 注册 Embedding 适配器                 |
| `register_proxy_model_adapter()` | 注册代理模型适配器（`proxy/base.py` 第465行） |

**查找策略**：逆序遍历（后注册的先匹配），优先级为 provider > model\_name > model\_path。

**自动扫描注册**：

`scan_model_providers()`（`packages/dbgpt-core/src/dbgpt/model/__init__.py` 第22行）使用 `ModelScanner` 自动扫描以下路径并触发注册：

| 扫描路径                          | 内容                               |
| ----------------------------- | -------------------------------- |
| `dbgpt.model.adapter`         | vllm, mlx, hf, llama\_cpp 等本地适配器 |
| `dbgpt.model.proxy.llms`（递归）  | 所有代理 LLM provider（21个）           |
| `dbgpt.rag.embedding`         | Embedding 实现                     |
| `dbgpt_ext.rag.embeddings`    | 扩展 Embedding                     |
| `dbgpt.rag.embedding`（rerank） | Reranker 实现                      |

### 6.3 代理 Provider（Proxy Providers）

文件目录：`packages/dbgpt-core/src/dbgpt/model/proxy/llms/`

共 **21 个**代理 Provider 实现：

| Provider 文件      | provider 值          | 说明                |
| ---------------- | ------------------- | ----------------- |
| `chatgpt.py`     | `proxy/openai`      | OpenAI 兼容（基类）     |
| `zhipu.py`       | `proxy/zhipu`       | 智谱 GLM（继承 OpenAI） |
| `moonshot.py`    | `proxy/moonshot`    | Kimi（继承 OpenAI）   |
| `tongyi.py`      | `proxy/tongyi`      | 通义千问              |
| `minimax.py`     | `proxy/minimax`     | MiniMax           |
| `claude.py`      | `proxy/claude`      | Anthropic Claude  |
| `deepseek.py`    | `proxy/deepseek`    | DeepSeek          |
| `gemini.py`      | `proxy/gemini`      | Google Gemini     |
| `ollama.py`      | `proxy/ollama`      | Ollama 本地服务       |
| `siliconflow.py` | `proxy/siliconflow` | 硅基流动              |
| `litellm.py`     | `proxy/litellm`     | LiteLLM 统一网关      |
| ...              | ...                 | 共 21 个            |

**继承复用模式**：大部分 Provider 继承 `OpenAILLMClient`，因为它们使用 OpenAI 兼容 API。例如 `ZhipuLLMClient` 继承 `OpenAILLMClient`，只覆写 `provider` 和 `api_base`。

### 6.4 本地模型适配器

| 适配器                                  | 文件                                | 后端                                     |
| ------------------------------------ | --------------------------------- | -------------------------------------- |
| `CommonModelAdapter`                 | `adapter/hf_adapter.py`           | HuggingFace Transformers（兜底匹配所有 HF 模型） |
| Qwen/Llama3/GLM4/Deepseek/Yi/Gemma 等 | `adapter/hf_adapter.py`           | 30+ 个特定模型适配器                           |
| `VLLMModelAdapter`                   | `adapter/vllm_adapter.py`         | vLLM 推理引擎                              |
| `MLXModelAdapter`                    | `adapter/mlx_adapter.py`          | Apple MLX                              |
| `LlamaCppModelAdapter`               | `adapter/llama_cpp_py_adapter.py` | llama.cpp Python 绑定                    |

### 6.5 uv extras 到 Python 依赖映射

文件：`packages/dbgpt-core/pyproject.toml`（第124-139行）

```toml
proxy_openai = ["openai>=1.59.6", "tiktoken>=0.8.0", "httpx[socks]"]
proxy_zhipuai = ["openai>=1.59.6"]
proxy_tongyi = ["openai", "dashscope"]
proxy_qianfan = ["qianfan"]
proxy_anthropic = ["anthropic"]
proxy_litellm = ["litellm>=1.60,<1.85"]
proxy_ollama = ["ollama"]
```

### 6.6 代理 Provider 继承复用模式

大部分 Provider **直接继承 `OpenAILLMClient`**，因为它们都使用 OpenAI 兼容 API，仅覆盖 `__init__` 修改 `provider` 和 `api_base`。

**`OpenAILLMClient.__init__` 核心流程**（`chatgpt.py`）:

1. 检查 `openai` 包是否已安装
2. `api_type/api_base/api_key/api_version` 经 `_resolve_env_vars` 解析（支持 `${env:VAR}` 语法）
3. 预加载客户端: `_ = self.client.default_headers`（预热缓存请求头）
4. API 配置优先级链:
   ```
   api_type  = 入参 or OPENAI_API_TYPE 环境变量(默认"open_ai")
   api_base  = 入参 or OPENAI_API_BASE or (AZURE_OPENAI_ENDPOINT if azure)
   api_key   = 入参 or OPENAI_API_KEY or (AZURE_OPENAI_KEY if azure)
   ```

**`generate_stream_v1` 边界处理**:
- `len(r.choices) == 0` → `continue`（空 choices 跳过）
- `r.choices[0].delta is None` → `continue`（Azure GPT-4o 的已知 boundary）
- 累积 `text` 和 `reasoning_content`（推理模型支持）

**httpx 版本兼容**:
- `>= 0.28.0` 用 `proxy=`（单数）
- `< 0.28.0` 用 `proxies=`（复数）

### 6.7 完整代理 Provider 清单

| Provider 文件 | provider 值 | 说明 | 默认 api_base |
|-------------|------------|------|--------------|
| `chatgpt.py` | `proxy/openai` | OpenAI 兼容（基类） | `https://api.openai.com/v1` |
| `zhipu.py` | `proxy/zhipu` | 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| `moonshot.py` | `proxy/moonshot` | Kimi | `https://api.moonshot.cn/v1` |
| `tongyi.py` | `proxy/tongyi` | 通义千问 | DashScope API |
| `minimax.py` | `proxy/minimax` | MiniMax | MiniMax API |
| `claude.py` | `proxy/claude` | Anthropic Claude | Anthropic API |
| `deepseek.py` | `proxy/deepseek` | DeepSeek | `https://api.deepseek.com/v1` |
| `gemini.py` | `proxy/gemini` | Google Gemini | Google API |
| `ollama.py` | `proxy/ollama` | Ollama 本地服务 | `http://localhost:11434/v1` |
| `siliconflow.py` | `proxy/siliconflow` | 硅基流动 | `https://api.siliconflow.cn/v1` |
| `gitee.py` | `proxy/gitee` | Gitee AI | `https://ai.gitee.com/v1` |
| `yi.py` | `proxy/yi` | 零一万物 | `https://api.lingyiwanwu.com/v1` |
| `litellm.py` | `proxy/litellm` | LiteLLM 统一网关 | LiteLLM |
| `baichuan.py` | `proxy/baichuan` | 百川 | 百川 API |
| `bedrock.py` | `proxy/bedrock` | AWS Bedrock | AWS API |
| ... | ... | 共 **21 个** | — |

**DeepSeek 特殊处理**（最复杂的 Provider 子类）:
- 新增 `thinking_enabled` 字段
- 重写 `_build_request` 注入 `extra_body={"thinking": {"type": "enabled"/"disabled"}}`
- `_drop_thinking_if_disabled`: thinking 禁用时剥离 thinking 内容（确保 ReAct 输出可解析）
- context_length 按模型名推断: v4=1M, chat=32K, coder=16K

### 6.8 并发控制与错误处理

**并发控制**: `WorkerRunData.semaphore = asyncio.Semaphore(concurrency)`，每个模型实例独立信号量，默认 LLM concurrency=5，代理模型默认 100。`LocalWorkerManager.executor = ThreadPoolExecutor(max_workers=os.cpu_count() * 5)`。

**错误处理策略**:

| 层 | 策略 |
|----|------|
| Worker 层 | CUDA OOM → 特殊提示; 其他 → `ModelOutput(error_code=1)`，不抛异常 |
| Proxy 层 | `generate` 的 try-except 返回错误 ModelOutput; `generate_stream_v1` 防御性跳过空 choices |
| Manager 层 | `_get_model` 失败 yield 错误 output; `_start_all_worker` 捕获网络错误给代理提示 |

**重要**: 代码中**没有内置 LLM 调用的重试机制**（无 tenacity/retry），重试责任在上层（如 Agent 的 ReAct 循环）。

**双重环境变量读取设计**: 每个 Provider 都实现了两层 key 读取:
1. `field(default="${env:XXX_API_KEY}")` — `ConfigurationManager` 解析 TOML 时替换
2. `api_key = api_key or os.getenv("XXX_API_KEY")` — 运行时兜底
3. 仍为空 → **`raise ValueError`** 阻止启动

***

## 7. RAG 与知识管理

### 7.1 文档摄取管道（Ingestion Pipeline）

```
文件上传
    │
    ▼
FileServe 存储（bucket: dbgpt_knowledge_file）
    │
    ▼
RagServe: create_document()     # 创建文档记录，状态=TODO
    │
    ▼
RagServe: sync_document()       # 触发同步，状态=RUNNING
    │
    ▼
KnowledgeFactory.create()       # 根据文件类型创建 Knowledge 对象
    │  ├─ PDF/CSV/Markdown/PPTX/DOCX/TXT/HTML/Excel/URL/Text
    │
    ▼
ChunkManager.split()            # 分块
    │  ├─ CHUNK_BY_SIZE（默认 chunk_size=512, overlap=50）
    │  ├─ CHUNK_BY_PARAGRAPH
    │  ├─ CHUNK_BY_MARKDOWN_HEADER
    │  └─ CHUNK_BY_SEPARATOR
    │
    ▼
EmbeddingAssembler.apersist()   # 向量化并持久化
    │  ├─ 批量加载（max_chunks_once_load）
    │  ├─ 多线程（max_threads）
    │  └─ 写入 VectorStoreConnector（Chroma/Milvus/...）
    │
    ▼
文档状态=FINISHED，保存 vector_ids 和 chunk 详情
```

### 7.2 检索策略

`KnowledgeSpaceRetriever`（`packages/dbgpt-serve/src/dbgpt_serve/rag/retriever/knowledge_space.py`）支持四种检索模式：

| 模式               | 说明      | 实现                                                 |
| ---------------- | ------- | -------------------------------------------------- |
| **Semantic（语义）** | 向量相似度搜索 | `RetrieverChain`（QARetriever + EmbeddingRetriever） |
| **Keyword（关键词）** | 全文检索    | Elasticsearch BM25                                 |
| **Tree（文档树）**    | 文档树遍历   | `DocTreeRetriever` + `KeywordExtractor`            |
| **Hybrid（混合）**   | 并行多策略   | Semantic + FullText + Tree 合并去重                    |

**检索增强：**

- **Query Rewrite（查询重写）**：先检索获取上下文，基于上下文重写查询后再检索
- **Rerank（重排序）**：通过 `Ranker` + `RerankEmbeddings` 模型对候选 chunks 重新打分

### 7.3 向量存储集成

支持 **8 种**向量存储（`packages/dbgpt-ext/src/dbgpt_ext/storage/__init__.py`）：

| 存储                | 说明                                                      |
| ----------------- | ------------------------------------------------------- |
| **Chroma**（默认）    | `PersistentClient`，cosine 距离，持久化到 `pilot/data/chromadb` |
| **Milvus**        | 高性能向量数据库                                                |
| **Weaviate**      | 语义搜索平台                                                  |
| **OceanBase**     | 分布式数据库向量能力                                              |
| **PGVector**      | PostgreSQL 向量扩展                                         |
| **ElasticSearch** | 全文+向量混合                                                 |
| **Qdrant**        | 向量搜索引擎                                                  |
| **Valkey**        | Redis 分支                                                |

另外还支持知识图谱存储（`KnowledgeGraph`、`CommunitySummaryKnowledgeGraph`、`OpenSPG`）和全文检索存储（`FullText`）。

### 7.4 知识数据模型

| 实体                        | 表名                   | 说明                                              |
| ------------------------- | -------------------- | ----------------------------------------------- |
| `KnowledgeSpaceEntity`    | `knowledge_space`    | 知识空间（name, vector\_type, domain\_type, context） |
| `KnowledgeDocumentEntity` | `knowledge_document` | 文档记录（doc\_name, doc\_type, status, vector\_ids） |
| `DocumentChunkEntity`     | -                    | 文档分块详情                                          |

***

## 8. Agent 系统

### 8.1 继承体系

```
BaseModel
    └─ Role (ABC)                           # 角色基类
         └─ ConversableAgent                # 核心可对话 Agent
              ├─ ReActAgent                 # ReAct 范式
              ├─ SimpleAssistantAgent       # 简单助手
              ├─ ToolAssistantAgent         # 工具调用
              ├─ WebSearchAgent             # 网络搜索
              ├─ CodeAssistantAgent         # 代码编写
              ├─ DataAnalysisAgent          # 数据分析
              ├─ DashboardAssistantAgent    # 仪表盘生成
              ├─ SummaryAssistantAgent      # 摘要
              ├─ PlannerAgent               # 任务规划
              └─ ...                        # 共 12+ 种 Agent
                    ↑
              ManagerAgent (Team)           # 团队管理器
                    └─ AutoPlanChatManager  # 自动计划协作
```

### 8.2 核心执行循环：Thinking-Review-Act-Verify

`ConversableAgent.generate_reply()`（`packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py` 第436行，`@final` 不可重写）：

```
┌─────────────────────────────────────────┐
│         Thinking（思考）                  │
│  ├─ 加载记忆（read_memories）             │
│  ├─ 加载资源（Resource）                  │
│  ├─ 构建 System/User Prompt              │
│  └─ 调用 LLM 推理（3次重试）              │
│     └─ 上下文溢出 → reactive_compact 压缩 │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│         Review（审查）                    │
│  └─ 对 LLM 输出进行审查                   │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│         Act（行动）                       │
│  ├─ 遍历所有绑定的 Actions                │
│  ├─ 解析 Action 输入                     │
│  └─ 执行 Action（工具调用等）             │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│         Verify（验证）                    │
│  ├─ 检查审批结果                          │
│  ├─ 检查 Action 输出                     │
│  └─ 验证失败 → 写入失败记忆 → 重新生成    │
└─────────────────────────────────────────┘
```

### 8.3 团队协作

- **Team**：管理一组 Agent（`hire` 方法招募）
- **ManagerAgent**：负责 speaker 选择（`select_speaker`），决定下一个发言的 Agent
- **AutoPlanChatManager**：PlannerAgent 分解任务 → Manager 分配给合适的 Agent → 处理依赖关系

### 8.4 Agent 记忆系统

| 类型       | 文件                                | 说明                               |
| -------- | --------------------------------- | -------------------------------- |
| 短期记忆     | `agent/core/memory/short_term.py` | 当前对话上下文                          |
| 长期记忆     | `agent/core/memory/long_term.py`  | 持久化记忆                            |
| 混合记忆     | `agent/core/memory/hybrid.py`     | 短期+长期组合                          |
| LLM 评分   | `agent/core/memory/llm.py`        | LLM 驱动的重要性评分和洞察提取                |
| 多Agent对话 | `agent/core/memory/gpts/`         | `GptsMemory`、`DefaultGptsMemory` |

### 8.5 上下文加载链路（Context Loading Chain）

上下文加载链路是 Agent 在每次调用 LLM 推理之前，将所有上下文信息（系统提示词、历史记忆、资源信息、用户问题等）组装成最终消息列表的完整流程。入口方法是 `ConversableAgent.generate_reply()`（`@final` 不可重写），核心组装方法是 `_load_thinking_messages()`。

#### 8.5.1 整体数据流

```
generate_reply() [base_agent.py:442]  ← @final, Think-Review-Act-Verify 主循环
  │
  └─ _load_thinking_messages() [base_agent.py:1279]  ← 上下文组装核心
       │
       ├── ① read_memories(observation)  →  ShortTermMemory
       │      └─ ReActAgent 重写：解析 JSON → List[AgentMessage]
       │
       ├── ② 处理 rely_messages 依赖消息
       │      └─ 拼接 Question: / Observation: 到 most_recent_memories
       │
       ├── ③ load_resource(observation)  →  Resource.get_prompt()
       │      ├─ DBResource: 数据库 schema 信息
       │      ├─ RetrieverResource: 知识库向量检索结果
       │      └─ ReActAgent 重写：移除 Tool 类型资源（工具另行处理）
       │
       ├── ④ generate_resource_variables(resource_prompt_str)
       │      → {"resource_prompt", "out_schema", "now_time"}
       │
       ├── ⑤ build_system_prompt()  →  Role.build_prompt(is_system=True)
       │      →  Profile.format_system_prompt()
       │      →  Jinja2 渲染 _DEFAULT_SYSTEM_TEMPLATE
       │      └─ 变量：role, name, goal, resource_prompt, constraints,
       │                examples, out_schema, now_time, task_progress...
       │
       ├── ⑥ build_prompt(is_system=False)  →  构建 user_prompt
       │      →  Profile.format_user_prompt()
       │
       └── ⑦ 按顺序组装 AgentMessage 列表：
            1. system_prompt    (SYSTEM 角色)
            2. historical_dialogues (HUMAN/AI 交替，来自 API 层)
            3. memory_list      (来自 ShortTermMemory 的 ReAct 历史)
            4. ContextManager.manage_context() ← 【多层压缩】
            5. user_prompt      (HUMAN 角色，当前轮 Observation)

thinking() [base_agent.py:744]
  ├─ AgentMessage → to_llm_message() → LLM dict
  └─ llm_client.create(messages=llm_messages, ...)  →  发送 LLM
```

#### 8.5.2 入口：generate_reply() — Think-Review-Act-Verify 主循环

**文件**：`packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py` L442（`@final`）

```python
async def generate_reply(
    self,
    received_message: AgentMessage,      # 当前收到的消息
    sender: Agent,
    reviewer: Optional[Agent] = None,
    rely_messages: Optional[List[AgentMessage]] = None,       # 依赖的历史消息
    historical_dialogues: Optional[List[AgentMessage]] = None, # API 层传入的对话历史
    is_retry_chat: bool = False,
    ...
) -> AgentMessage:
```

每次调用 `generate_reply()` 执行一轮 Think-Review-Act-Verify 循环（最多 `max_retry_count` 次重试）。每轮调用 `_load_thinking_messages()` 重新组装上下文。

**关键参数说明**：
| 参数 | 来源 | 说明 |
|---|---|---|
| `received_message` | 上游 sender | 当前轮收到的消息，content 为 observation（工具执行结果或用户问题） |
| `rely_messages` | sender 发送的历史消息 | 上一轮发送的全部消息，用于恢复上下文 |
| `historical_dialogues` | API 层（`agentic_data_api.py`） | 从 `gpts_messages` 表全量加载的对话历史，偶数位=用户，奇数位=AI |
| `is_retry_chat` | API 层 | 是否重试模式，影响 prompt 模板变量选择 |

#### 8.5.3 核心：_load_thinking_messages() 分步详解

**文件**：`packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py` L1279-L1429

这是整个上下文加载链路的核心方法，负责将所有信息来源组装成发送给 LLM 的 `List[AgentMessage]`。

##### Step 1：读取记忆 — `read_memories(observation)`

```python
# L1310
memories = await self.read_memories(observation)
```

**Role 默认实现** (`role.py` L267-L274)：
```python
async def read_memories(self, question: str):
    memories = await self.memory.read(question)  # ShortTermMemory._fragments
    recent_messages = [m.raw_observation for m in memories]
    return "".join(recent_messages)  # 返回字符串
```

**ReActAgent 重写** (`react_agent.py` L274-L305)：
- 从 `ShortTermMemory._fragments`（buffer_size=5）读取最近 5 个 ReAct step
- 每个 fragment 的 `raw_observation` 是 JSON 结构，包含 `question/thought/action/action_input/observation` 字段
- 解析为 `List[AgentMessage]`：Question→HUMAN，Thought/Action→AI，Observation→HUMAN
- 返回值类型根据子类实现可能是 `str` 或 `List[AgentMessage]`

**数据来源**：`ShortTermMemory._fragments` 的内容来自两个恢复路径（见 8.5.9 节）。

##### Step 2：注入 task_progress — 任务进度追踪

```python
# L1321-1323
task_progress = self.task_progress_summary
if task_progress:
    context["task_progress"] = task_progress
```

`task_progress_summary`（`role.py` L210-L255）是 `_task_progress` 列表的人类可读摘要，记录所有已完成步骤。**它不存储在 ShortTermMemory 中**（是普通实例属性而非 Pydantic field），因此不受 buffer_size 淘汰影响。

##### Step 3：加载资源 — `load_resource(observation)`

```python
# L1344-1346
resource_prompt_str, resource_references = await self.load_resource(
    observation, is_retry_chat=is_retry_chat
)
```

**ReActAgent 重写** (`react_agent.py` L200-L217)：
- 调用 `self.resource.apply(apply_func=_remove_tool)` 移除所有 Tool 类型的资源
- 工具在 `_a_init_reply_message()` 中作为 `action_space` 另行处理
- 只保留非 Tool 资源（知识库、数据库 schema 等）调用 `get_prompt()`

**Resource.get_prompt() 实现** (`resource/base.py` L173-L190)：

| Resource 类型 | 实现文件 | get_prompt() 内容 |
|---|---|---|
| **DBResource** | `resource/database.py` L78 | 数据库类型 + 表结构定义（`_parse_db_summary` 提取所有表 schema 后再拼接成 prompt） |
| **RetrieverResource** | `resource/knowledge.py` L83 | 向量检索获取相关 chunks → 可选 rerank → 格式化为 `\nResources-{name}:\n {content}` |
| **ResourcePack** | `resource/pack.py` | 聚合内部所有子 Resource 的 get_prompt() 输出 |

##### Step 4：生成资源变量 — `generate_resource_variables()`

```python
# L1062-1076
async def generate_resource_variables(self, resource_prompt):
    return {
        "resource_prompt": resource_prompt or "",  # 从 load_resource 返回的资源提示词
        "out_schema": self.actions[0].ai_out_schema,  # Action 输出格式（JSON schema 指令）
        "now_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 当前时间
    }
```

##### Step 5：构建 System Prompt — `build_system_prompt()`

```python
# L1353-1359
system_prompt = await self.build_system_prompt(
    question=question,
    most_recent_memories=most_recent_memories,
    resource_vars=resource_vars,
    context=context,
    is_retry_chat=is_retry_chat,
)
```

**调用链**：`base_agent.py L1240` → `role.py L64` → `Profile.format_system_prompt()` → `Profile._format_prompt()` (`profile/base.py` L282)

**Prompt 模板**（`profile/base.py` L27-L70，Jinja2 格式）：

```jinja2
You are a {{ role }}, {% if name %}named {{ name }}.
{% endif %}your goal is {% if is_retry_chat %}{{ retry_goal }}{% else %}{{ goal }}{% endif %}.

{% if resource_prompt %}
Given resources information:
{{ resource_prompt }}
{% endif %}

*** IMPORTANT REMINDER ***
Please answer in English.
The current time is:{{now_time}}.

{% if constraints %}{% for constraint in constraints %}
{{ loop.index }}. {{ constraint }}
{% endfor %}{% endif %}

{% if out_schema %} {{ out_schema }} {% endif %}
```

**模板变量完整列表**（`VALID_TEMPLATE_KEYS`，L13-L25）：

| 变量 | 来源 | 说明 |
|---|---|---|
| `role` | Profile.get_role() | 角色名称，如 "ReActToolMaster" |
| `name` | Profile.get_name() | Agent 名称 |
| `goal` / `retry_goal` | Profile | 目标描述 / 重试目标 |
| `resource_prompt` | `generate_resource_variables()` | 数据库 schema + 知识库检索结果 |
| `expand_prompt` | Profile | 可扩展的额外上下文 |
| `constraints` / `retry_constraints` | Profile | 约束规则列表 |
| `examples` | Profile | Few-shot 示例 |
| `out_schema` | `actions[0].ai_out_schema` | 输出 JSON 格式规范 |
| `most_recent_memories` | `read_memories()` 返回的字符串 | 最近记忆文本 |
| `now_time` | `generate_resource_variables()` | 当前时间戳 |
| `is_retry_chat` | 参数 | 是否重试模式 |
| `language` | Agent 语言设置 | 回答语言要求 |

**子渲染机制** (`_sub_render_keys`)：`role`、`name`、`goal`、`expand_prompt`、`constraints` 等值本身也可能是 Jinja2 模板，会被二次渲染。

##### Step 6：构建 User Prompt — `build_prompt(is_system=False)`

```python
# L1360-1366
user_prompt = await self.build_prompt(
    question=question,
    is_system=False,
    most_recent_memories=most_recent_memories,
    resource_vars=resource_vars,
    **context,
)
```

- 调用 `Profile.format_user_prompt()`，同样走 `_format_prompt()`
- 模板内容由具体 Profile 子类定义，通常比 System Prompt 简短
- `**context` 传入 `ActionOutput` 的 context dict 及 `task_progress` 等运行时变量

##### Step 7：组装最终消息列表

```python
# L1368-1429
agent_messages = []

# ① System Prompt — SYSTEM 角色
if system_prompt:
    agent_messages.append(
        AgentMessage(content=system_prompt, role=ModelMessageRoleType.SYSTEM)
    )

# ② Historical Dialogues — HUMAN/AI 交替
# 来自 agentic_data_api.py 全量加载的会话历史
# 偶数位=HUMAN，奇数位=AI
if historical_dialogues:
    for i, message in enumerate(historical_dialogues):
        message.role = HUMAN if i % 2 == 0 else AI
        agent_messages.append(message)

# ③ Memory List — ShortTermMemory 的 ReAct 历史
# Question(HUMAN) / Thought(AI) / Action(AI) / Observation(HUMAN) 格式
if memory_list:
    agent_messages.extend(memory_list)

# ④ 多层上下文压缩（ContextManager）
# 如果配置了 enable_context_management，在 user_prompt 前插入压缩
ctx_mgr = getattr(self, "_context_manager", None)
if ctx_mgr is not None:
    agent_messages = await ctx_mgr.manage_context(
        messages=agent_messages,
        current_round=current_retry_counter or 0,
        task_progress=task_progress,
    )

# ⑤ User Prompt — HUMAN 角色
# 如果 user_prompt 为空且无 memory 或首次调用，兜底为 "Observation: {observation}"
if not user_prompt and (not memory_list or not current_retry_counter):
    user_prompt = f"Observation: {observation}"
if user_prompt:
    agent_messages.append(
        AgentMessage(content=user_prompt, role=ModelMessageRoleType.HUMAN)
    )
```

**最终消息顺序**：
```
┌─────────────────────────────────────────────────┐
│ ① system_prompt      SYSTEM   含 resource_prompt、constraints、out_schema │
├─────────────────────────────────────────────────┤
│ ② historical_dialogue[0]  HUMAN  （API 层传入）                          │
│ ② historical_dialogue[1]  AI                                            │
│ ② ...                                                                    │
├─────────────────────────────────────────────────┤
│ ③ memory_list[0]      HUMAN    Question（来自 ShortTermMemory）          │
│ ③ memory_list[1]      AI       Thought                                  │
│ ③ memory_list[2]      AI       Action                                   │
│ ③ memory_list[3]      HUMAN    Observation                              │
│ ③ ...                    （最多 5 个 ReAct step）                         │
├─────────────────────────────────────────────────┤
│ ← [可选] ContextManager 压缩层                                           │
├─────────────────────────────────────────────────┤
│ ⑤ user_prompt         HUMAN    当前轮 Observation / 用户问题             │
└─────────────────────────────────────────────────┘
```

**⚠️ 内容重叠问题**：`historical_dialogues` 和 `memory_list` 都来自 `gpts_messages` 表，只是读取路径不同（API 层 vs Agent 内部恢复），存在内容重叠。在 L1297-L1298 有注释明确说明。

#### 8.5.4 思考阶段：thinking() — 发送 LLM

**文件**：`packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py` L744-L795

```python
async def thinking(self, messages: List[AgentMessage], ...):
    # 把 AgentMessage 转为 LLM 兼容格式
    llm_messages = [message.to_llm_message() for message in messages]
    # 每个 to_llm_message() 返回 {"content": ..., "context": ..., "role": ...}

    # 自动重试 3 次（网络/限流容错）
    while retry_count < 3:
        response = await self.llm_client.create(
            context=llm_messages[-1].pop("context", None),
            messages=llm_messages,
            llm_model=llm_model,
            max_new_tokens=...,
            temperature=...,
            stream_out=self.stream_out,
            stream_callback=stream_callback,
        )
        return response, llm_model
```

**AgentMessage.to_llm_message()** (`agent.py` L282-L310)：
- 将 `AgentMessage.content` 和 `context` 转为 LLM 客户端接受的 `{"content": str, "context": dict, "role": str}` 格式
- `context` 字段包含 `task_progress` 等结构化上下文，LLM 客户端可将其注入实际 prompt

**LLM 调用异常处理**：

| 异常类型 | 处理方式 | 代码位置 |
|---|---|---|
| `LLMChatError` + context overflow | 触发 Layer 4 `reactive_compact` → 重新 thinking | L572-L600 |
| `LLMChatError` | 等待 10s → 换 model → 重试（最多 3 次） | L757-L793 |
| 其他异常 | 向上传播到 `generate_reply()` → 返回 `AgentMessage(success=False)` | L734-L738 |

#### 8.5.5 多层上下文压缩：ContextManager

**文件**：`packages/dbgpt-core/src/dbgpt/agent/core/context/manager.py` L27-L178

`ContextManager` 是一个渐进式 4 层压缩系统，当上下文 token 用量超过预算时逐层触发。

**ContextBudgetConfig 配置** (`budget.py` L42-L74)：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `max_context_tokens` | 120000 | 最大上下文 token 数，`<=0` 时自动从模型元数据推断 |
| `warning_threshold` | 0.70 (70%) | Layer 1/2 触发阈值 |
| `error_threshold` | 0.90 (90%) | Layer 3 触发阈值 |
| `critical_threshold` | 0.95 (95%) | 熔断器触发的阈值 |
| `reserved_tokens` | 4096 | 预留给 LLM 输出的 token |
| `min_keep_recent_rounds` | 3 | 最少保留的最近轮数 |
| `max_compact_failures` | 3 | 最大压缩失败次数，超限后熔断 |
| `max_observation_age_rounds` | 5 | 旧 Observation 轮数阈值 |
| `truncated_observation_max_chars` | 200 | Layer 1 截断后最大字符数 |
| `min_keep_tokens` | 10000 | Layer 2 最少保留 token 数 |

**TokenState 状态机** (`budget.py` L16-L39)：

```
NORMAL → WARNING (>=70%) → ERROR (>=90%) → CRITICAL (>=95%) → OVERFLOW
```

**4 层压缩算法**：

| 层级 | 类 | 触发状态 | 策略 | 是否需要 LLM |
|---|---|---|---|---|
| **Layer 1** | `ObservationMicroCompact` (L86) | >= WARNING | 截断旧轮次（超过 `max_observation_age_rounds` 轮）的 Observation 消息到 `truncated_observation_max_chars` 字符，保留快照文件路径供恢复 | 否 |
| **Layer 2** | `SessionMemoryCompact` (L139) | >= WARNING | 删除旧的完整 ReAct 轮次，保留至少 `min_keep_recent_rounds` 轮 + `min_keep_tokens` 个 token。system_prompt 中的 `task_progress` 作为隐式摘要 | 否 |
| **Layer 3** | `FullContextCompression` (L208) | >= ERROR | 使用 LLM 将旧轮次对话压缩为结构化摘要（Original Task / Completed Steps / Current State / Key Data / Errors / Next Steps） | **是** |
| **Layer 4** | `ReactiveCompact` (L283) | 应急（LLM 返回 context_too_long） | 保留 system_prompt + 最后 2 轮，丢弃所有其他内容 | 否 |

**熔断机制** (`budget.py` L100-L130)：
- `circuit_breaker_tripped`：连续 `max_compact_failures` 次 Layer 3 压缩失败后，跳过后续所有压缩
- `record_compact_success()` / `record_compact_failure()` 维护成功/失败计数

**启用条件**：在 `AgentContext` 中设置 `enable_context_management=True`，然后在 `ReActAgent.__init__()` 中调用 `init_context_management()` 创建 `ContextManager` 实例。

#### 8.5.6 上下文压缩后的 LLM 重试

`generate_reply()` L572-L602 中的 **Layer 4 应急处理**：

```python
try:
    llm_reply, model_name = await self.thinking(thinking_messages, ...)
except LLMChatError as e:
    _ctx_mgr = getattr(self, "_context_manager", None)
    err_str = str(e).lower()
    if _ctx_mgr and (
        "context_too_long" in err_str
        or "context_length_exceeded" in err_str
        or "maximum context length" in err_str
    ):
        # 紧急压缩 → 重新 thinking
        thinking_messages = await _ctx_mgr.reactive_compact(thinking_messages)
        llm_reply, model_name = await self.thinking(thinking_messages, ...)
    else:
        raise
```

此路径独立于 `manage_context()`，仅在 LLM 返回 `context_too_long` 错误时触发，是最后一道防线。

#### 8.5.7 记忆写入：write_memories()

每轮 Think-Act 完成后，`generate_reply()` 调用 `write_memories()` 将本轮结果持久化（`role.py` L276-L398）：

```
write_memories()
  ├─ 构建 memory_map: {thought, action, action_input, observation, question}
  ├─ 更新 self._task_progress 任务进度列表
  │    └─ 追加 {step_num, action, thought, action_input, observation_tokens}
  ├─ 写入快照文件（_write_op_snapshot） → 磁盘 JSON
  ├─ 格式化 write_memory_template → MemoryFragment
  │    └─ ReActAgent 使用 _REACT_WRITE_MEMORY_TEMPLATE
  ├─ memory.write(fragment) → ShortTermMemory
  │    ├─ handle_duplicated() 去重
  │    └─ transfer_to_long_term() 溢出检查（buffer_size=5）
  └─ memory.gpts_memory.append_message() → 持久化到 gpts_messages 表
```

**快照文件**：完整 Observation 内容写入磁盘 JSON（`role.py` L394-L398），路径存储在 `MemoryFragment.context["snapshot_path"]` 中。Layer 1 压缩时，截断的 Observation 会提示快照路径。

#### 8.5.8 ReActAgent 的特化处理

**文件**：`packages/dbgpt-core/src/dbgpt/agent/expand/react_agent.py`

`ReActAgent` 在多个环节对上下文加载进行了特化：

| 方法 | 特化行为 | 行号 |
|---|---|---|
| `_a_init_reply_message()` | 从 ToolPack 提取 `action_space`（工具描述列表），写入 `reply_message.context["action_space"]` | L135-L168 |
| `load_resource()` | 移除 Tool 类型资源，只保留知识库/数据库等非工具资源 | L200-L217 |
| `read_memories()` | 将 ShortTermMemory 的 JSON fragment 解析为 `List[AgentMessage]`，Question→HUMAN、Thought/Action→AI、Observation→HUMAN | L274-L305 |
| `prepare_act_param()` | 传入 `ReActOutputParser`，确保 act() 按 ReAct 格式解析 | L219-L229 |
| `__init__()` | 根据 `enable_context_management` 配置初始化 `ContextManager` | L122-L133 |

**action_space 注入时机**：`action_space` 在 `_a_init_reply_message()` 中写入 `reply_message.context`，通过 `context` 参数传入 `build_system_prompt()` → Profile 模板中 `{{ action_space }}` 变量在 system prompt 中渲染（通常在 profile 模板通过 `expand_prompt` 或自定义方式注入）。

#### 8.5.9 上下文恢复路径（Build Time）

**文件**：`packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py` L190-L230

Agent 每次 `build()` 时从数据库恢复历史上下文：

```python
async def build(self, is_retry_chat=False) -> "ConversableAgent":
    await self.preload_resource()
    # 初始化 LLM 客户端
    self.llm_client = AIWrapper(llm_client=self.llm_config.llm_client)
    # 初始化记忆（含 embedding 服务）
    self.memory.initialize(...)
    # structure_clone：只 clone ShortTermMemory 结构，gpts_memory 共享
    self.memory = self.memory.structure_clone()
    # 【上下文恢复点 #1】从 gpts_messages 表读取该 conv_id 的历史消息
    action_outputs = await self.memory.gpts_memory.get_agent_history_memory(
        real_conv_id, self.role
    )
    # 恢复到 ShortTermMemory._fragments
    await self.recovering_memory(action_outputs)
```

**两套并行的上下文恢复路径**：

```
路径 A（Agent 内部）：
  build() → gpts_memory.get_agent_history_memory()
         → recovering_memory()
         → ShortTermMemory._fragments
         → _load_thinking_messages() 中的 read_memories() 读取

路径 B（API 层）：
  agentic_data_api.py → conversation service
                      → historical_dialogues 参数
                      → _load_thinking_messages() 中直接使用
```

⚠️ 两条路径的数据源都是 `gpts_messages` 表，**内容存在重叠**（已在 L1297-L1298 注释说明）。

#### 8.5.10 完整调用链总结

```
用户请求
  │
  ├─ agentic_data_api.py: _react_agent_stream()
  │   ├─ load_skills / 获取 resource_manager
  │   ├─ 准备 knowledge_space / database_name / connector 工具
  │   ├─ 构建 ReActAgent.build()
  │   │   ├─ preload_resource()
  │   │   ├─ 初始化 LLM 客户端
  │   │   ├─ 初始化 memory（embedding 服务）
  │   │   ├─ structure_clone()
  │   │   └─ recovering_memory() ← gpts_messages 表 [恢复点 #1]
  │   │
  │   └─ 创建 asyncio.Queue → 启动 agent_task
  │
  └─ agent.generate_reply() [base_agent.py:442]
      │
      └─ for round in range(max_retry_count):
           ├─ _load_thinking_messages() [L1279]
           │   ├─ read_memories() → ShortTermMemory [恢复点 #2]
           │   ├─ load_resource() → Resource.get_prompt()
           │   ├─ generate_resource_variables()
           │   ├─ build_system_prompt() → Profile.format_system_prompt()
           │   ├─ build_prompt(is_system=False)
           │   └─ 组装 ① system ② history ③ memory ④ [compact] ⑤ user
           │
           ├─ thinking() → llm_client.create()
           │   └─ [context_too_long → reactive_compact → retry]
           │
           ├─ review() → approve
           ├─ act() → Action.run() → tool_execute
           ├─ verify() → check_pass
           └─ write_memories()
               ├─ 更新 task_progress
               ├─ 写快照文件
               ├─ ShortTermMemory.write()
               └─ gpts_memory.append_message() → gpts_messages 表
```

#### 8.5.11 关键文件索引

| 组件 | 文件 | 关键行号 |
|---|---|---|
| **generate_reply 主循环** | `.../agent/core/base_agent.py` | L442-L742 |
| **_load_thinking_messages 核心组装** | `.../agent/core/base_agent.py` | L1279-L1429 |
| **thinking 发送 LLM** | `.../agent/core/base_agent.py` | L744-L795 |
| **build 记忆恢复** | `.../agent/core/base_agent.py` | L190-L230 |
| **generate_resource_variables** | `.../agent/core/base_agent.py` | L1062-L1076 |
| **Role.build_prompt** | `.../agent/core/role.py` | L64-L96 |
| **Role.read_memories** | `.../agent/core/role.py` | L267-L274 |
| **Role.write_memories** | `.../agent/core/role.py` | L276-L398 |
| **Role.task_progress_summary** | `.../agent/core/role.py` | L210-L255 |
| **ReActAgent 特化** | `.../agent/expand/react_agent.py` | L96-L305 |
| **Profile._DEFAULT_SYSTEM_TEMPLATE** | `.../agent/core/profile/base.py` | L27-L70 |
| **Profile._format_prompt** | `.../agent/core/profile/base.py` | L282-L339 |
| **ProfileConfig** | `.../agent/core/profile/base.py` | L529-L570 |
| **ShortTermMemory** | `.../agent/core/memory/base.py` | L705-L800 |
| **AgentMemory** | `.../agent/core/memory/agent_memory.py` | L283-L350 |
| **GptsMemory** | `.../agent/core/memory/gpts/gpts_memory.py` | L24-L200 |
| **ContextManager** | `.../agent/core/context/manager.py` | L27-L178 |
| **ContextBudgetConfig** | `.../agent/core/context/budget.py` | L42-L74 |
| **Layer 1: ObservationMicroCompact** | `.../agent/core/context/compact.py` | L86-L131 |
| **Layer 2: SessionMemoryCompact** | `.../agent/core/context/compact.py` | L139-L200 |
| **Layer 3: FullContextCompression** | `.../agent/core/context/compact.py` | L208-L275 |
| **Layer 4: ReactiveCompact** | `.../agent/core/context/compact.py` | L283-L320 |
| **Resource 基类** | `.../agent/resource/base.py` | L90-L204 |
| **DBResource（数据库 schema）** | `.../agent/resource/database.py` | L31-L120 |
| **RetrieverResource（知识库检索）** | `.../agent/resource/knowledge.py` | L30-L120 |
| **ResourceManager** | `.../agent/resource/manage.py` | L76-L300 |
| **AgentMessage** | `.../agent/core/agent.py` | L282-L310 |
| **LLMClient** | `.../agent/util/llm/llm_client.py` | L190-L250 |

***

## 9. AWEL 工作流引擎

AWEL（Agentic Workflow Expression Language）是 DB-GPT 的可视化工作流编排引擎，基于 DAG（有向无环图）。

### 9.1 DAG 核心

文件：`packages/dbgpt-core/src/dbgpt/core/awel/dag/base.py`

- `DependencyMixin`：定义上下游节点设置接口，重载 `<<`（set\_upstream）和 `>>`（set\_downstream）操作符，类似 Airflow 语法
- `DAGNode`：DAG 节点基类
- `DAG`：管理整个图结构
- `DAGContext`：执行上下文

### 9.2 Operator（操作符）体系

| Operator               | 文件                                       | 功能                            |
| ---------------------- | ---------------------------------------- | ----------------------------- |
| `MapOperator`          | `operators/base.py`                      | 一对一映射                         |
| `JoinOperator`         | `operators/common_operator.py`           | 使用 combine\_function 合并多个上游输入 |
| `ReduceStreamOperator` | `operators/common_operator.py`           | 使用 reduce\_function 聚合        |
| `RetrieverOperator`    | `interface/operators/retriever.py`       | 检索器操作符（继承 MapOperator）        |
| `LLMOperator`          | `interface/operators/llm_operator.py`    | LLM 调用操作符                     |
| `PromptOperator`       | `interface/operators/prompt_operator.py` | Prompt 构建操作符                  |
| `HOKnowledgeOperator`  | `dbgpt_app/operators/rag.py`             | 高阶知识检索操作符                     |

### 9.3 可视化元数据

每个 Operator 都有 `ViewMetadata`，包含 label、name、category、description、parameters（参数列表）、inputs/outputs（IOField），用于可视化画布渲染。

`register_resource` 装饰器将类注册为 AWEL 资源（带分类 `ResourceCategory`）。

### 9.4 DAG 管理器

`DAGManager`（`packages/dbgpt-core/src/dbgpt/core/awel/dag/dag_manager.py`）：

- 从 `dag_dirs` 加载 DAG 文件（`LocalFileDAGLoader`）
- `register_dag`：注册 DAG，支持 alias
- `get_dags_by_tag`：按 tag 查找 DAG（知识同步时使用此功能匹配领域处理流程）

### 9.5 触发器系统

| 触发器         | 文件                            | 说明        |
| ----------- | ----------------------------- | --------- |
| HTTP 触发器    | `trigger/http_trigger.py`     | HTTP 请求触发 |
| 扩展 HTTP 触发器 | `trigger/ext_http_trigger.py` | 扩展 HTTP   |
| 迭代器触发器      | `trigger/iterator_trigger.py` | 迭代触发      |

### 9.6 Flow Serve

`packages/dbgpt-serve/src/dbgpt_serve/flow/` 提供 AWEL 可视化编排的后端服务：

- DAG 的 CRUD 操作
- 变量管理（`VariablesProvider`，支持加密存储）
- 流程模板（`templates/en/` 和 `templates/zh/`）

### 9.7 DAG 构建与生命周期

**DAG 构建阶段**：

- `DAG._append_node()`（`dag/base.py` L816）将节点加入 `node_map`
- 访问 `root_nodes`、`leaf_nodes` 或 `trigger_nodes` 属性触发惰性 `_build()`（L862），遍历所有可达节点
  - `root_nodes`：无上游节点的节点
  - `leaf_nodes`：无下游节点的节点
  - `trigger_nodes`：`TriggerOperator` 实例

**DAGVar 上下文追踪**（`dag/base.py` L136-L183）：

- `DAGVar.enter_dag(dag)` / `.exit_dag()` 将 DAG 压入/弹出线程局部的 `collections.deque` 或异步 `ContextVar`
- `BaseOperatorMeta.__call__`（`operators/base.py` L91）自动注入 `dag`、`task_id`、`system_app`、`executor`、`variables_provider` — 任何在 `with DAG(...)` 块内创建的 operator 自动绑定到该 DAG

**节点连接**：`DependencyMixin`（`dag/base.py` L51）通过 `<<`（set\_upstream）和 `>>`（set\_downstream）操作符连接节点。`set_dependency()`（L441）验证所有节点属于同一 DAG 上下文。

### 9.8 DefaultWorkflowRunner 执行算法

核心文件：`packages/dbgpt-core/src/dbgpt/core/awel/runner/local_runner.py`

**`execute_workflow()` 流程**（L43）：

```
1. 从 end_node 构建 JobManager（执行计划）
2. 如有 exist_dag_ctx → 合并 node_outputs、share_data、dag_variables
3. 创建 DAGContext，设置 streaming_call 标志
4. 调用 job_manager.before_dag_run()
5. 在 root_tracer.start_span("dbgpt.awel.workflow.run_workflow") 追踪包裹中：
   a) 递归执行 _execute_node(end_node)
   b) 非流式：调用 dag._after_dag_end()
```

**`_execute_node()` 核心逻辑**（L125）：

1. **跳过检查**：`node.node_id` 已在 `node_outputs` 中 → 直接返回（缓存）
2. **拓扑排序**：递归执行所有上游节点（L141-L150），上游在同一 asyncio 任务中顺序执行（并行化标记为 TODO）
3. **收集输入**：将所有父节点 `TaskContext` 输出收集到 `DefaultInputContext`
4. **设置任务状态**：`INIT` → `RUNNING`
5. **分支跳过**：若 `node_id in skip_node_ids` → 设置 `SKIP`
6. **执行**：`node._run(dag_ctx, task_log_id)` 在 trace span 内

**`BranchOperator` 分支跳过传播**（L215）：

- 从 metadata 读取 `skip_node_names`
- `_skip_current_downstream_by_node_name()` 预注册所有直接跳过候选，使 `JoinOperator` 能知晓哪些父节点被跳过
- `JoinOperator.can_skip_in_branch()`（L248-L254）**仅当所有父节点都被跳过时才返回 True**
- 通过 `_skip_downstream_by_id()` 递归传播跳过

**异常处理**：捕获异常 → 设置 `FAILED` 状态 → 重新抛出。

### 9.9 触发器系统详解

**HttpTrigger**（`trigger/http_trigger.py`）：

- `_resolved_endpoint()`（L543）：将 URL 中的 `{dag_id}` 占位符替换为实际 dag_id
- `_create_route_func()`（L586）：GET/DELETE 将查询参数解析为请求体 Pydantic；POST/PUT 解析 body
- 支持 `Request`、`BaseModel`、`dict`、`str` 四种 body 类型
- **流式 vs 非流式**（`_trigger_dag()` L706）：
  - 非流式：`end_node.call(call_data=body)`，在 trace span 内
  - 流式：`end_node.call_stream(call_data=body)`，包装为 `root_tracer.wrapper_async_stream()`，返回带 SSE header 的 `StreamingResponse`。`_after_dag_end` 在 `BackgroundTasks` 中运行

**IteratorTrigger**（`trigger/iterator_trigger.py`）：

- 输入可为 `Iterator`、`AsyncIterator` 或 `InputSource`
- **并行执行**：`asyncio.Semaphore(parallel_num)` 控制并发
- **重试逻辑**（非流式）：max_retries，指数退避延迟（L276-L300）
- **超时**：`asyncio.wait_for()` 逐个任务
- **缓存系统**：
  - `cache_storage`（抽象 `CacheStorage`）、`cache_key_fn`、`cache_ttl`
  - 缓存 key 按输入数据项生成（L116-L128）
  - 缓存命中直接返回存储结果（L261-L271）
  - 流式缓存：流完成后存储结果列表（L222-L232）

### 9.10 FlowRegistry 与资源元数据

文件：`packages/dbgpt-core/src/dbgpt/core/awel/flow/base.py`

**`OperatorCategory` 枚举**（L161）：TRIGGER、SENDER、LLM、CONVERSION、OUTPUT_PARSER、COMMON、AGENT、RAG、EXPERIMENTAL、DATABASE、TYPE_CONVERTER、EXAMPLE、CODE — 共 13 种分类。

**`OperatorType` 枚举**（L195）：MAP、REDUCE、JOIN、BRANCH、INPUT、STREAMIFY、UN_STREAMIFY、TRANSFORM_STREAM。

**`ViewMetadata`**（L1224）：声明 operator 的输入（IOField）、输出、参数（Parameter），用于可视化画布渲染。

**注册装饰器**：
- `register_resource()`（L1044）：装饰资源类（如 `BaseHttpBody` 子类）
- `auto_register_resource()`（L1110）：从 dataclass 字段自动创建 Parameter 对象

**全局单例**：`FlowRegistry`（L1408），`_OPERATOR_REGISTRY` 存储所有 operator/resource 元数据。

***

***

## 10. API 层

### 10.1 路由注册机制

核心函数 `mount_routers(app)`（`dbgpt_server.py` 第55-88行），所有路由共享 `/api` 前缀：

| 路由模块       | 文件                                       | Tag       |
| ---------- | ---------------------------------------- | --------- |
| API V1     | `openapi/api_v1/api_v1.py`               | Chat      |
| API V2     | `openapi/api_v2.py`                      | ChatV2    |
| Editor     | `openapi/api_v1/editor/api_editor_v1.py` | Editor    |
| Feedback   | `openapi/api_v1/feedback/api_fb_v1.py`   | FeedBack  |
| GptsApp    | `dbgpt_serve/agent/app/controller.py`    | GptsApp   |
| Knowledge  | `dbgpt_app/knowledge/api.py`             | Knowledge |
| 各 Serve 模块 | 各 Serve 的 `api/endpoints.py`             | 模块特定      |

### 10.2 API V2 — OpenAI 兼容接口

`api_v2.py` 实现了 **OpenAI 兼容的聊天接口** `POST /v2/chat/completions`：

- 支持多种 `chat_mode`：`CHAT_APP`、`CHAT_AWEL_FLOW` 等
- 通过 `check_api_key` 依赖注入进行 Bearer Token 认证
- 支持流式和非流式响应

### 10.3 Serve 模块的路由

每个 Serve 模块都有独立的 `api/endpoints.py`，在 `init_endpoints()` 中注册路由。路由前缀通常为 `/api/v1/serve/{module_name}` 或 `/api/v2/serve/{module_name}`。

### 10.4 安全认证

**API Key 验证**（`openapi/api_v2.py` L43-L68）：

```python
async def check_api_key(
    request: Request,
    token: Optional[str] = Depends(HTTPBearer(auto_error=False)),
):
    api_keys = service.config.api_keys  # 逗号分隔的密钥列表
    # 未配置 API Key → 放行所有请求
    if not api_keys:
        return None
    # Token 不匹配 → 返回 HTTP 401 (OpenAI 风格错误体)
    if token is None or token not in api_keys.split(","):
        raise HTTPException(status_code=401, detail=...)
    return token
```

**安全策略**：
- 管理者在配置中设置以逗号分隔的 API Key 列表
- 客户端在请求中附带 `Authorization: Bearer <key>`
- 不匹配的 token 被拒绝，返回 HTTP 401
- 未配置 Key 时认证完全跳过（开发模式）
- 各 Serve 模块端点通过 `Depends(check_api_key)` 保护

**变量加密**（`packages/dbgpt-core/src/dbgpt/core/interface/variables.py`）：

- `FernetEncryption`（L75）：PBKDF2-HMAC（SHA256，800,000 次迭代）+ Fernet 对称加密
- `SimpleEncryption`（L133）：XOR + 哈希的轻量加密
- Flow 系统中的变量可通过加密方法在数据库中存储为密文

***

## 11. 前端架构

### 11.1 技术栈

- **框架**：Next.js 13.4.7 + React 18 + TypeScript
- **UI 库**：Ant Design 5 + MUI 5 + TailwindCSS 3.3
- **HTTP 客户端**：Axios
- **代码编辑器**：Monaco Editor
- **国际化**：`locales/en/` 和 `locales/zh/`

### 11.2 目录结构

| 目录                    | 用途                                                                       |
| --------------------- | ------------------------------------------------------------------------ |
| `web/pages/`          | Next.js 页面路由（chat, construct/app, construct/flow, knowledge, evaluation） |
| `web/components/`     | 旧版组件（agent, app, chart, chat, flow, model 等）                             |
| `web/new-components/` | 新版组件（app, chat, layout, connector, report）                               |
| `web/client/api/`     | API 调用层，按模块组织                                                            |
| `web/hooks/`          | 自定义 Hooks（use-chat, use-react-agent 等）                                   |
| `web/lib/`            | 工具库（api/, dto/, session.ts）                                              |

### 11.3 API 调用层

`web/client/api/index.ts` 基于 Axios 创建实例：

- `baseURL` 从环境变量 `API_BASE_URL` 获取
- 请求拦截器自动注入用户 ID header
- 长耗时 API 设置 60s 超时

### 11.4 静态资源服务

构建后的前端部署到 `packages/dbgpt-app/src/dbgpt_app/static/web/`，由 FastAPI 的 `StaticFiles` 中间件在根路径 `/` 提供服务。

***

## 12. 组件与插件系统

### 12.1 组件生命周期

`SystemApp`（`packages/dbgpt-core/src/dbgpt/component.py`）管理所有组件的注册和生命周期：

```
on_init → after_init → before_start → after_start → before_stop
```

### 12.2 ComponentType 枚举

关键组件类型：

| 类型                    | 说明         |
| --------------------- | ---------- |
| `WORKER_MANAGER`      | Worker 管理器 |
| `MODEL_CONTROLLER`    | 模型控制器      |
| `PLUGIN_HUB`          | 插件中心       |
| `MULTI_AGENTS`        | 多智能体       |
| `EXECUTOR_DEFAULT`    | 默认线程池      |
| `TRACER`              | 链路追踪       |
| `AWEL_DAG_MANAGER`    | DAG 管理器    |
| `CONNECTOR_MANAGER`   | 连接器管理器     |
| `AGENT_MANAGER`       | Agent 管理器  |
| `RESOURCE_MANAGER`    | 资源管理器      |
| `SKILL_MANAGER`       | 技能管理器      |
| `FILE_STORAGE_CLIENT` | 文件存储客户端    |

### 12.3 组件注册流程

`initialize_components()`（`component_configs.py` 第14行）按顺序注册 18 类组件（详见第 4 章启动流程）。

### 12.4 PluginHub 插件系统

文件：`packages/dbgpt-serve/src/dbgpt_serve/agent/hub/plugin_hub.py`

- 通过 `PluginHubDao` 和 `MyPluginDao` 管理插件元数据
- 默认插件仓库：`https://github.com/eosphoros-ai/DB-GPT-Plugins.git`
- 内置**安全验证** `_validate_plugin_code()`：通过 AST 分析禁止危险导入（subprocess、os.system、eval、exec、pickle 等）

***

## 13. 存储层

### 13.1 ORM 框架

使用 **SQLAlchemy**（传统 ORM 模式）。

- `DatabaseManager`（`packages/dbgpt-core/src/dbgpt/storage/metadata/db_manager.py`）：全局数据库管理器，提供 `BaseQuery`（分页查询）、`BaseModel`（声明式基类）、`db`（全局单例）
- `BaseDao[T, REQ, RES]`：泛型 CRUD 基类，提供 `session(commit=True)` 上下文管理器

#### DatabaseManager 初始化流程

`DatabaseManager.__init__()` 创建空的 `_engine` 和 `_session`，调用 `init_db()` 时：

```python
def init_db(self, db_url, engine_args, base, query_class, session_options):
    self._engine = create_engine(db_url, **(engine_args or {}))
    session_options.setdefault("class_", Session)
    session_options.setdefault("query_cls", self.Query)
    session_factory = sessionmaker(bind=self._engine, **session_options)
    self._session = session_factory
```

**`init_default_db()`** 为 SQLite 提供默认连接池配置：QueuePool, pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=3600, pool_pre_ping=True。

**全局单例**：`db = DatabaseManager()`（L425），`Model = create_model(db)`（L511）。

#### Session 管理

```python
@contextmanager
def session(self, commit=True):
    session = self._session()  # sessionmaker 创建的 Session
    try:
        yield session
        if commit:
            session.commit()     # 自动提交
    except Exception:
        session.rollback()       # 异常回滚
        raise
    finally:
        session.close()          # 总是关闭
```

#### BaseDao CRUD 模式

`BaseDao(Generic[T, REQ, RES])` 提供通用 CRUD：

| 方法 | 说明 |
|------|------|
| `create(request)` | add → commit → 重新查询返回 |
| `update(query_req, update_req)` | 查询 → setattr → merge |
| `delete(query_req)` | 确保只删一条记录 |
| `get_one(query_req)` | first() 返回单个 |
| `get_list(query_req)` | all() 返回列表 |
| `get_list_page(query_req, page, page_size)` | 分页查询，支持 desc_order_column |

**`_create_query_object`** 过滤逻辑：跳过 list/tuple/dict/set 类型值，list 使用 `.in_()` 操作符，其他使用 `==` 比较。

#### SQLite vs MySQL 差异

| 维度 | SQLite | MySQL |
|------|--------|-------|
| URL 格式 | `sqlite:///path` | `mysql+pymysql://user:pass@host:port/db` |
| 连接池 | `init_default_db` 自动配置 | 需手动指定 pool_size/max_overflow 等 |
| 特性兼容 | 部分 DDL 不支持 | 完整关系数据库功能 |

#### SQLAlchemyStorage 适配器

`SQLAlchemyStorage`（`db_storage.py` L31-L146）实现 `StorageInterface`，提供 save/update/save_or_update/load/delete/query/count 等标准 CRUD 操作的核心封装。

### 13.2 支持的数据库

| 数据库            | 说明                            |
| -------------- | ----------------------------- |
| **SQLite**（默认） | 路径 `pilot/meta_data/dbgpt.db` |
| **MySQL**      | <br />                        |
| **OceanBase**  | <br />                        |

### 13.3 数据库迁移

使用 **Alembic**：

- 配置：`pilot/meta_data/alembic.ini`
- 环境：`pilot/meta_data/alembic/env.py`
- 迁移版本：`pilot/meta_data/alembic/versions/`
- SQL Schema：`assets/schema/dbgpt.sql`
- 自动迁移在 `_initialize_db_storage()` 中通过 `disable_alembic_upgrade` 配置控制

### 13.4 存储分层

| 子目录             | 用途                     |
| --------------- | ---------------------- |
| `metadata/`     | 关系型元数据（SQLAlchemy ORM） |
| `cache/`        | LLM 缓存（内存/磁盘）          |
| `full_text/`    | 全文检索存储                 |
| `graph_store/`  | 图数据库存储                 |
| `vector_store/` | 向量数据库存储                |

***

## 14. 代码沙箱

### 14.1 四层架构

```
用户层 (UserLayer)       → 接收用户请求，创建/管理会话
    ↓
控制层 (ControlLayer)    → 任务生命周期管理，并发安全
    ↓
执行层 (ExecutionLayer)  → 运行时抽象（Docker/Podman/Nerdctl/Local）
    ↓
显示层 (DisplayLayer)     → 结果封装与展示
```

### 14.2 运行时

`RuntimeFactory` 自动检测并选择最佳运行时（优先级）：

1. 环境变量 `SANDBOX_RUNTIME` 指定的运行时
2. Docker SDK
3. Podman
4. Nerdctl
5. Local（需要 `SANDBOX_ALLOW_LOCAL_RUNTIME=true` 显式启用）

如果没有容器运行时可用且未启用 Local，则抛出异常（fail-closed 安全策略）。

### 14.3 支持的语言

| 语言           | Docker 镜像                |
| ------------ | ------------------------ |
| Python       | `python:3.11-slim`       |
| Python + VNC | `vnc-gui-browser:latest` |
| JavaScript   | `node:18-slim`           |
| Java         | `openjdk:11-jre-slim`    |
| C++          | `gcc:latest`             |
| Go           | `golang:1.21-alpine`     |
| Rust         | `rust:1.75-slim`         |

### 14.4 资源限制

| 限制项      | 默认值   |
| -------- | ----- |
| 最大内存     | 256MB |
| 最大 CPU   | 50%   |
| 最大执行时间   | 30 秒  |
| 最大文件大小   | 10MB  |
| 最大依赖安装时间 | 300 秒 |
| 最大进程数    | 10    |

***

## 15. Serve 层

### 15.1 统一架构模式

所有 Serve 模块遵循统一的目录结构：

```
dbgpt_serve/<module>/
  ├── config.py         # ServeConfig（继承 BaseServeConfig）
  ├── serve.py          # Serve 类（继承 BaseServe），生命周期管理
  ├── dependencies.py   # 依赖注入
  ├── api/
  │   ├── endpoints.py  # FastAPI 路由
  │   └── schemas.py    # 请求/响应模型
  ├── models/
  │   └── models.py     # 数据库实体（SQLAlchemy Model）
  ├── service/
  │   └── service.py    # 业务逻辑（继承 BaseService）
  └── tests/
```

### 15.2 已注册的 15 个 Serve 模块

| 模块                     | 功能                              |
| ---------------------- | ------------------------------- |
| **PromptServe**        | 提示词模板管理                         |
| **ConversationServe**  | 对话管理                            |
| **FlowServe (AWEL)**   | AWEL 工作流编排，变量加密存储               |
| **RagServe**           | 知识空间、文档、分块管理                    |
| **DatasourceServe**    | 数据源连接管理                         |
| **FeedbackServe**      | 聊天反馈管理                          |
| **DbgptsHubServe**     | DbGpts 市场/Hub                   |
| **DbgptsMyServe**      | 用户自建 DbGpts                     |
| **FileServe**          | 文件存储（本地/OSS/S3）                 |
| **EvaluateServe**      | 评估系统（Benchmark，支持 LLM/Agent 评测） |
| **LibroServe**         | Jupyter Notebook 集成             |
| **ModelServe**         | 模型管理                            |
| **ConnectorServe**     | 外部连接器（MCP 集成）                   |
| **ScheduledTaskServe** | 定时任务（cron 聊天重放）                 |
| **ChatServe**          | Agent 聊天服务                      |

***

## 16. 数据流总结

### 5 条核心数据流路径

**1. 知识摄取流**

```
文件上传 → FileServe 存储 → RagServe create_document → KnowledgeFactory 解析
→ ChunkManager 分块 → EmbeddingAssembler 向量化 → VectorStore 持久化
```

**2. 知识检索流**

```
用户 Query → KnowledgeSpaceRetriever → 选择检索模式(Semantic/Keyword/Tree/Hybrid)
→ RetrieverChain(QARetriever + EmbeddingRetriever) → 可选 QueryRewrite + Rerank → 返回 Chunks
```

**3. 对话流**

```
用户消息 → API V1/V2 → Scene(chat_normal/chat_db/chat_data) 或 AWEL Flow
→ LLM 调用（流式输出）→ 返回响应
```

**4. Agent 协作流**

```
UserProxyAgent → AutoPlanChatManager → PlannerAgent 任务分解
→ 分配给专业 Agent → Thinking-Review-Act-Verify 循环
→ Agent 间消息传递 → 记忆读写 → 返回结果
```

**5. AWEL 编排流**

```
FlowServe 可视化编排 DAG → DAGManager 加载和注册
→ Operator(MapOperator/JoinOperator/RetrieverOperator 等) 按 DAG 拓扑执行
→ 支持流式输出和触发器

**6. 消息模型流**

```
用户输入 → HumanMessage(BaseMessage) → OnceConversation.add_user_message()
    → OnceConversation.get_model_messages()
        ├─ 过滤 pass_to_model=False 的消息（ViewMessage）
        └─ BaseMessage → ModelMessage 转换
    → ModelMessage 列表 → LLMClient.generate() / generate_stream()
    → AI 响应 → AIMessage → OnceConversation.add_ai_message()
    → StorageConversation.save_to_storage() 持久化
```

***

## 17. 常见配置与运维操作

### 17.1 切换模型

**场景1：切换已配置的模型（不需重启）**

- 配置文件里定义的模型启动后都会注册到系统
- 在 Web UI 聊天界面顶部下拉切换，即时生效

**场景2：新增模型**

- 通过 Web UI 的「Model Management」页面在线添加（推荐）
- 或手动改 TOML 配置后重启

**场景3：配置多个模型随时切换**

```toml
[[models.llms]]
name = "glm-4-plus"
provider = "proxy/zhipu"
api_base = "https://open.bigmodel.cn/api/paas/v4"
api_key = "${env:ZHIPUAI_API_KEY:-sk-xxx}"

[[models.llms]]
name = "glm-4-air"
provider = "proxy/zhipu"
api_base = "https://open.bigmodel.cn/api/paas/v4"
api_key = "${env:ZHIPUAI_API_KEY:-sk-xxx}"
```

### 17.2 启动命令

```bash
# 用 profile 配置启动（推荐）
uv run dbgpt start webserver --profile glm

# 用指定配置文件启动
uv run dbgpt start webserver --config /path/to/config.toml

# 后台守护进程启动
uv run dbgpt start webserver --profile glm --daemon

# 停止服务
uv run dbgpt stop webserver
```

### 17.3 配置文件位置

| 文件                                | 用途                          |
| --------------------------------- | --------------------------- |
| `~/.dbgpt/configs/<profile>.toml` | 实际使用的配置（由 `dbgpt setup` 生成） |
| `~/.dbgpt/config.toml`            | 全局配置（记录活跃 profile）          |
| `configs/*.toml`（仓库内）             | 官方提供的配置模板/示例                |

### 17.4 安装相关

```bash
# 安装（指定 profile）
bash scripts/install/install.sh --profile glm --repo-dir "$(pwd)" --yes

# 安装（使用中国镜像加速）
bash scripts/install/install.sh --profile glm --repo-dir "$(pwd)" --mirror china --yes

# 安装后确保 uv 在 PATH 中
export PATH="$HOME/.local/bin:$PATH"
# 或永久生效
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

### 17.5 常见问题排查

**问题：`ValueError: Unknown type value: proxy/zhipu`（embedding 报错）**

原因：代码中未注册 `proxy/zhipu` 作为 embedding provider（只有 `proxy/openai` 等少数几个）。

解决：将 TOML 配置中 embedding 的 `provider` 改为 `proxy/openai`（因为 ZhipuAI 的 embedding 接口是 OpenAI 兼容的）：

```toml
[[models.embeddings]]
provider = "proxy/openai"    # 而非 "proxy/zhipu"
api_url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
```

**问题：`zsh: command not found: uv`**

原因：安装脚本中临时添加的 PATH 在新终端中失效。

解决：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**问题：`--repo-dir must point to a DB-GPT git checkout`**

原因：ZIP 下载的代码没有 `.git` 目录。

解决：使用 `git clone` 重新下载，或初始化 git 仓库：

```bash
git init
git remote add origin https://github.com/eosphoros-ai/DB-GPT.git
```

***

*文档基于 DB-GPT v0.8.1 源码分析生成。*

***

## 18. MCP 与连接器系统

### 18.1 MCP 传输层

MCP 传输层位于 `packages/dbgpt-core/src/dbgpt/agent/util/mcp_utils.py`，提供两种传输协议。

**SSE 客户端**（第 25-203 行，自研实现）:

- 使用 `anyio` 创建双流模型：`read_stream`（输出 SessionMessage）+ `write_stream`（接收并 POST）
- 内部通过 `anyio.create_task_group()` 运行两个任务：
  - `sse_reader`：消费来自 `httpx_sse.aconnect_sse` 的 SSE 事件
  - `post_writer`：从写入流读取 SessionMessage → 解包 JSONRPCMessage → POST 到端点 URL
- **死锁防护**: `started_flag` 机制区分 ClientSession 未建立 vs 稳态运行时，防止零缓冲区 rendezvous 流死锁
- **端点来源验证**: SSE "endpoint" URL 的 `netloc` 和 scheme 必须与原始连接 URL 一致
- 超时配置：连接建立 5s，SSE 读取空闲 300s

**Streamable HTTP 客户端**（第 226-275 行）:

- 懒加载 `mcp.client.streamable_http.streamablehttp_client`（需要 mcp >= 1.8.0）
- 丢弃 `get_session_id` 回调以保持与 SSE client 的 yield 形状兼容
- **已知限制**: `verify=False` 对 streamable_http 静默无效（官方 httpx 客户端自建）

**传输归一化** (`_normalise_transport`): `"streamable_http"`/`"streamableHttp"`/`"Streamable-HTTP"` 全部统一为 `"streamablehttp"`。

### 18.2 MCPToolPack — 工具包装器

`packages/dbgpt-core/src/dbgpt/agent/resource/tool/pack.py` 第 291-476 行。

**初始化参数**:
- `mcp_servers`: 字符串（`;` 分隔）或列表
- `headers`: 按 server URL 索引的 header 字典
- `ssl_verify`/`ssl_ca_cert`: SSL 策略
- `transport`: 默认 `"sse"`（不能混用）
- `overwrite_same_tool`: 同名工具是否覆盖，默认 True

**`preload_resource()` — 工具发现流程**:
```
对每个 server:
  1. 建立 mcp_transport_client 连接
  2. 创建 ClientSession，调用 initialize()
  3. 调用 list_tools() 获取工具清单
  4. 对每个 tool:
     a. 记录 tool_server_map[tool_name] = server
     b. 通过 switch_mcp_input_schema 转换 JSON Schema
     c. 定义 call_mcp_tool 闭包
     d. 通过 add_command 注册到 ToolPack
  5. 设置 _loaded = True
```

**`call_mcp_tool` 闭包** — **每次调用新建连接**，无连接池化，每次都会完成完整的 MCP 握手。

**`switch_mcp_input_schema()`**: 将 MCP 的 `inputSchema`（JSON Schema）转换为内部 ToolParameter 格式，description 回退链: `description` → `items` → `anyOf` → 整个 value。

### 18.3 ConnectorManager — 运行时管理

`packages/dbgpt-core/src/dbgpt/agent/resource/connector/manager.py`

**核心数据结构**:
- `_active_packs: Dict[str, MCPToolPack]` — connector_id → 活跃工具包
- `_statuses: Dict[str, ConnectorStatus]` — connector_id → status 枚举
- `_salts: Dict[str, str]` — 加密盐

**`ConnectorStatus` 枚举**: `active`, `error`, `disconnected`

**`create_connector()` 完整流程**:
1. 生成 connector_id (`secrets.token_hex(16)`)
2. 解析 catalog entry（custom_mcp 跳过）
3. 确定传输协议: `extra_config.transport > catalog > "sse"`
4. 统一 auth_type: bearer 自动补 "Bearer " 前缀
5. 加密凭证
6. 创建 MCPToolPack 实例
7. `asyncio.wait_for(pack.preload_resource(), timeout=15s)` 握手
8. 计算工具前缀 → 应用前缀 → 存入 `_active_packs`
9. **永不抛出异常** — 失败体现在 `_statuses` 中

**工具命名空间前缀**（格式 `mcp__{prefix}__{original_name}`）:
- 内置单实例: `{connector_type}`（如 `github`）
- 内置多实例: `{connector_type}-{slug(display_name)}`（如 `github-acme`）
- 自定义: `{slug(display_name)}`

**工具摘要去重**: 按 `original_name` 去重，优先保留带前缀版本。

### 18.4 ConnectorService — 持久化与重启恢复

`packages/dbgpt-serve/src/dbgpt_serve/connector/service/service.py`

**凭证加密体系**:
- `CredentialStore` 使用 `FernetEncryption`（基于 cryptography 库）
- 主密钥: `dbgpt.app.global.encrypt_key` > `ENCRYPT_KEY` 环境变量 > 临时随机密钥
- 密钥派生: PBKDF2HMAC (SHA256, 800000 次迭代)
- 每个连接器有独立的 64 字符 hex salt

**进程重启恢复** (`after_start`):
1. 查询 DB 中所有 `status="active"` 的连接器
2. 解密凭证
3. 调用 manager.create_connector（复用原 connector_id）
4. 缺少 server_uri → DB 状态改为 `needs_reactivation`
5. 其他失败 → 仅记录警告日志

**`update_connector` 凭证合并策略**: 新凭证**覆盖**同名字段，旧字段**保留**；空字典/None 表示不修改凭证。

**`test_connection`**: 重新执行 `preload_resource()`（10 秒超时），成功后调用 `_heal_status_to_active()` 进行**状态自愈**。

**工具参数截断**: `_TOOL_ARGS_BYTE_CAP = 8192`，超过 8KB 的 args 替换为 `{"_truncated": True}`。

### 18.5 catalog.json 内置连接器

`packages/dbgpt-ext/src/dbgpt_ext/connector/catalog.json`

| 类型 | 传输 | 分类 | 确认动作数 |
|------|------|------|-----------|
| feishu (飞书) | sse | communication | 3 |
| dingtalk (钉钉) | sse | communication | 2 |
| yuque (语雀) | sse | document | 3 |
| github | streamable_http | project | 3 |
| notion | streamable_http | document | 5 |
| linear | streamable_http | project | 5 |
| tavily | streamable_http | search | 0 |
| deepwiki | streamable_http | dev | 0 |

加上生成的 `custom_mcp`，共 9 种类型。

### 18.6 其他边界情况

- **连接器激活超时**: 握手 15s，测试连接 10s，确认等待 300s
- **SSL 不对称**: SSE 支持 `verify=False` 和自定义 CA；Streamable HTTP 需通过环境变量 `SSL_CERT_FILE` 或 `REQUESTS_CA_BUNDLE` 配置
- **MCP Toolbox 协议选择**: `streamable_http` vs `sse` 由 MCP 服务器决定，误配会导致激活失败
- **工具冲突**: 同一 pack 内由 `overwrite_same_tool` 控制，跨连接器由 `mcp__{prefix}__` 前缀隔离

***

## 19. 可视化系统 (Vis)

### 19.1 架构层次

位于 `packages/dbgpt-core/src/dbgpt/vis/`，共 14 个 Vis 子类：

| 类 | vis_tag() | 说明 |
|----|-----------|------|
| `VisChart` | `vis-db-chart` | **图表渲染核心** |
| `VisDashboard` | `vis-dashboard` | 仪表盘 |
| `VisCode` | `vis-code` | 代码展示 |
| `VisAgentPlans` | `agent-plans` | Agent 计划 |
| `VisAgentMessages` | `agent-messages` | Agent 消息 |
| `VisPlugin` | `vis-plugin` | 插件 |
| `VisAppLink` | `vis-app-link` | 应用链接 |
| `VisApiResponse` | `vis-api-response` | API 响应 |
| `VisThinking` | `vis-thinking` | 思考过程（特殊：用三个反引号包裹） |
| `VisReportGeneration` | `report-generation` | 报告生成 |

### 19.2 Vis 协议基类

`Vis`（`base.py` L9-L55）定义了渲染协议：

- **`render_prompt()`**: 返回提示词，告诉 LLM 如何输出 Vis 协议格式
- **`generate_param()`**: 异步生成 Vis 协议的参数字典
- **`display()`**: 核心渲染 — 将参数序列化为 JSON 包裹在 markdown 代码块 ` ```{vis_tag()}\n{json_content}\n``` `
- **`vis_tag()`**: 类方法，返回标签名

### 19.3 VisChart — 图表渲染核心

`tags/vis_chart.py` 支持 8 种图表类型：

| 类型 | 用途 |
|------|------|
| `response_line_chart` | 趋势分析 |
| `response_pie_chart` | 比例/分布 |
| `response_table` | 多列或非数字列 |
| `response_scatter_chart` | 变量关系探索 |
| `response_bubble_chart` | 多变量关系 |
| `response_donut_chart` | 层级结构 |
| `response_area_chart` | 时间序列对比 |
| `response_heatmap` | 大规模数据集 |

### 19.4 VisClient 注册中心

`client.py` 全局单例 `vis_client`，以 `vis_tag()` 为 key 注册所有 Vis 子类。`vis_name_change()` 函数将旧 `vis-chart` 标签兼容映射为 `vis-db-chart`。

### 19.5 从前端到后端的数据流

```
LLM 输出: <api-call><name>response_table</name><args><sql>SELECT...</sql></args></api-call>
  → ApiCall.display_sql_llmvis() 解析 <api-call> 标签
    → 执行 SQL 获取 DataFrame
      → api_view_context() 选择 Vis 协议渲染
        → 生成 <chart-view content='{"type":"response_table","data":[...]}'> XML
          或 ```vis-db-chart\n{json}``` markdown
```

***

## 20. 场景系统 (Scene)

### 20.1 ChatScene 枚举

`packages/dbgpt-app/src/dbgpt_app/scene/base.py` 定义了 14 个枚举值：

| 场景 | code | param_types | is_inner |
|------|------|-------------|----------|
| ChatWithDbExecute | `chat_with_db_execute` | DB Select | **否** |
| ChatWithDbQA | `chat_with_db_qa` | DB Select | **否** |
| ChatExcel | `chat_excel` | File Select | **否** |
| ExcelLearning | `excel_learning` | 无 | **是**（内部场景） |
| ChatNormal | `chat_normal` | 无 | **否** |
| ChatDashboard | `chat_dashboard` | DB Select | **否** |
| ChatKnowledge | `chat_knowledge` | Knowledge Space Select | **否** |
| ChatAgent | `chat_agent` | Plugin Select | **否** |
| ChatFlow | `chat_flow` | Flow Select | **否** |
| 其他 (5 个) | Extract 类 | Extract Select | **是** |

### 20.2 ChatFactory — 场景分发器

`ChatFactory.get_implementation()`:
1. 懒加载 import 注册所有场景的 prompt 到 `PromptTemplateRegistry`
2. 遍历 `BaseChat.__subclasses__()` 找到匹配的类
3. 解析场景配置 + 实例化

### 20.3 BaseChat — 所有场景的基类

核心执行流程：

```
1. __init__: 获取 prompt template + 初始化对话存储
2. prepare_input_values(): 生成 prompt 变量
3. _build_model_request(): 合并 prompt + history + 用户输入 → ModelRequest
4. stream_call() / nostream_call(): 调用 LLM
5. _handle_final_output():
   a) output_parser.parse_model_nostream_resp() 解析 LLM 输出
   b) do_action() 执行具体业务（如执行 SQL）
   c) parse_view_response() 生成前端视图
```

### 20.4 chat_db 场景详解

**chat_with_db_execute（Chat Data）**:
- `generate_input_values()` 获取 DB schema、方言、display_type 列表
- `do_action()` 返回 `self.database.run_to_df`（SQL 执行函数）
- `DbChatOutputParser` 解析 LLM 的 JSON 输出 `{thoughts, direct_response, sql, display_type}`
- 兼容纯 SQL 输出（`is_sql_statement()` 检测）
- 支持 PCA 降维用于向量图表

**chat_with_db_qa（Chat DB QA）**: 纯问答场景，不执行 SQL，用户问全量元信息时拒绝。

### 20.5 chat_data/chat_excel 两阶段流程

**阶段1: ExcelLearning（内部场景）**:
- 自动分析数据结构，生成标准化的列名映射和分析方案
- temperature=0.8, stream_out=False
- 输出: `{data_analysis, column_analysis, analysis_program}`

**阶段2: ChatExcel（主场景）**:
- `prepare()`: 没有历史消息时自动触发 ExcelLearning
- 使用 DuckDB 作为查询引擎
- LLM 输出 `<api-call>` XML 格式，temperature=0.3

### 20.6 Prompt 注册机制

**`PromptTemplateRegistry`**（`core/_private/prompt_registry.py`）:
- 双层嵌套: `{scene_name: {model_name: {language: template}}}`
- 默认键: `_DEFAULT_MODEL_KEY` 和 `_DEFAULT_LANGUAGE_KEY`
- 查找优先级: proxyllm_backend → model_name → `_DEFAULT_MODEL_KEY`

**注册时机**: 每个场景的 `prompt.py` 在 import 时执行注册，通过 `ChatFactory` 的懒加载触发。

**每场景的典型 Prompt 参数**:
- chat_normal: temperature 默认, 无 response_format
- chat_db_execute: temperature=0.5, JSON schema response_format
- chat_excel: temperature=0.3, DuckDB 特殊语法规则
- excel_learning: temperature=0.8, stream_out=False

***

## 21. 资源系统 (Resource)

### 21.1 ResourceType 枚举

`packages/dbgpt-core/src/dbgpt/agent/resource/base.py` 定义 14 种资源类型:

| 类型 | 说明 |
|------|------|
| DB | 数据库连接 |
| Knowledge | 知识库 |
| Internet | 网络搜索 |
| Tool | 工具 |
| Skill | 技能 |
| Plugin | 插件 |
| TextFile/ExcelFile/ImageFile/AudioFile/VideoFile | 文件类型 |
| AWELFlow | 工作流 |
| App | 应用 |
| Pack | 资源包 |
| Connector | 外部连接器 |

### 21.2 Resource 抽象基类

关键抽象方法:

| 方法 | 说明 |
|------|------|
| `type()` (classmethod) | 返回 ResourceType |
| `name` (property) | 资源名称 |
| `get_prompt()` | **抽象**: 返回 prompt 字符串和引用字典 |
| `execute()` / `async_execute()` | 执行动作 |
| `from_resource()` (classmethod) | 从另一个 Resource 中提取特定类型子资源 |
| `sub_resources` (property) | 子资源列表 |
| `get_resource_by_type()` | 按类型查找子资源 |
| `apply()` | 对资源递归应用变换函数 |

### 21.3 ResourcePack

`pack/pack.py` L21-L174，内部用 `_resources: Dict[str, Resource]` 管理多个资源：
- `get_prompt()`: 遍历所有子资源，用分隔符拼接
- `execute()/async_execute()`: 必须传入 `resource_name` 指定执行目标
- `apply()`: 递归对子资源应用变换函数

### 21.4 ResourceManager

`manage.py` L76-L294:
- 双索引: `_resources` (按 key) 和 `_type_to_resources` (按 type)
- `register_resource()`: 注册类或实例
- `build_resource_by_type()`: 按类型和 AgentResource 构建实例
- `build_resource()`: 批量构建，单个返回 Resource，多个返回 ResourcePack

### 21.5 具体资源实现

**DBResource**（`database.py` L31-L142）: 泛型基类，有 RDBMS 和 SQLite 子类，`get_prompt()` 用 `TTLCache` 缓存 10 秒。

**RetrieverResource**（`knowledge.py` L30-L185）: 支持可选的 rerank 流水线，`get_prompt()` 使用 TTL 缓存。

**AppResource**（`app.py` L21-L178）: `resource_parameters_class()` 动态生成参数类，从真实 app 列表中填充 valid_values。

**SkillResource**（`skill_resource.py` L15-L74）: 通过 SkillManager 加载 skill，只读封装不可执行。

***

## 22. 工具系统 (Tool)

### 22.1 BaseTool 抽象类

`packages/dbgpt-core/src/dbgpt/agent/resource/tool/base.py` L64-L137:

- `type()` 固定返回 `ResourceType.Tool`
- 抽象属性: `description` (str), `args` (Dict[str, ToolParameter])
- `get_prompt()`: 支持两种 prompt 类型：
  - `prompt_type == "openai"` → OpenAI function-calling 格式 JSON schema
  - 其他 → 简化参数列表 JSON

### 22.2 FunctionTool

`base.py` L140-L229，包装可调用对象为工具：

```python
FunctionTool(name, func, description=None, args=None, args_schema=None)
```
- `execute()`: 同步执行（异步函数抛 ValueError）
- `async_execute()`: 异步执行（同步函数抛 ValueError）
- `parse_execute_args_func`: 可选自定义参数解析函数

### 22.3 @tool 装饰器

`base.py` L232-L284，四种用法：
1. `@tool` — 使用函数名
2. `@tool("name")` — 指定名称
3. `@tool(func)` — 直接装饰
4. `@tool("name", func)` — 带名装饰

在函数上附加 `DB_GPT_TOOL_IDENTIFIER = True` 标记。

### 22.4 参数解析三级 Fallback

`_parse_args()` (L295-L350):
1. 传入 `args` 且全是 `ToolParameter` → 直接使用
2. 传入 `args` 且是 dict → 转换为 ToolParameter
3. 传入 `args_schema`（Pydantic）→ `_parse_args_from_schema()` 解析
4. 否则 → `inspect.signature()` 反射函数签名推断

### 22.5 ToolPack 工具容器

`tool/pack.py` L79-L252:
- 继承 ResourcePack，专门管理工具
- `add_command()`: 兼容 Auto-GPT 插件系统
- `_get_execution_tool()`: 按名称查找，找不到抛 `ToolNotFoundException`
- `_get_call_args()`: 过滤掉工具不认识的额外参数（防御 LLM 传入多余参数）
- `execute()/async_execute()`: 过滤参数后执行

### 22.6 工具异常体系

```
ToolException
  ├── CreateToolException
  ├── ToolNotFoundException
  └── ToolExecutionException
```

### 22.7 特殊 ToolPack 类型

**AutoGPTPluginToolPack** (L255-L288): 加载 Auto-GPT 插件，异步扫描注册。

**MCPToolPack** (L291-L476): 通过 MCP 协议连接远程工具服务器（见第 18 章）。

***

## 23. Agent Profile 系统

### 23.1 Profile 抽象接口

`packages/dbgpt-core/src/dbgpt/agent/core/profile/base.py`:

抽象方法: `get_name()`, `get_role()`, `get_system_prompt_template()`, `get_user_prompt_template()`, `get_write_memory_template()`

可选方法: `get_goal()`, `get_retry_goal()`, `get_constraints()`, `get_description()`, `get_expand_prompt()`, `get_examples()`

**`format_system_prompt()`**: 使用 Jinja2 沙箱渲染模板，自动收集 `pass_vars`（名称/角色/目标/约束等），支持子模板二次渲染。

### 23.2 内置 System Prompt 模板

7 个内置模板常量（L27-L147），中英文各一套：

| 模板 | 说明 |
|------|------|
| `_DEFAULT_SYSTEM_TEMPLATE` | 英文系统模板 |
| `_DEFAULT_SYSTEM_TEMPLATE_ZH` | 中文系统模板 |
| `_DEFAULT_USER_TEMPLATE` | 英文用户模板 |
| `_DEFAULT_USER_TEMPLATE_ZH` | 中文用户模板 |
| `_DEFAULT_WRITE_MEMORY_TEMPLATE` | 中文记忆写入模板 |

**重要约束**（系统模板 L33-L35）: 严禁在任务计划中直接调用任何 resource 中的 tool，所有 tool 调用必须通过 ToolExpert agent。

### 23.3 ProfileConfig — 核心配置类

`L529-L672`，所有字段使用 `DynConfig()` 类型注解，支持从静态值或 ConfigInfo 动态查询：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name`, `role` | **必需** | agent 名称和角色 |
| `goal`, `retry_goal` | 可选 | 目标和重试目标 |
| `constraints`, `retry_constraints` | 可选 (is_list=True) | 约束列表 |
| `system_prompt_template` | `_DEFAULT_SYSTEM_TEMPLATE` | 系统 prompt |
| `user_prompt_template` | `_DEFAULT_USER_TEMPLATE` | 用户 prompt |
| `factory` | 可选 | ProfileFactory 实例 |

**`create_profile()` 方法**（L578-L668）:
1. **TTL 缓存**: `@cachetools.cached(TTLCache(maxsize=100, ttl=10))` — 10 秒内重复调用命中缓存
2. 遍历所有字段，若为 `ConfigInfo` 则调用 `.query()` 动态获取
3. 若有 `factory`，调用工厂方法创建
4. 返回 `DefaultProfile` 实例

### 23.4 DynConfig 机制

`dbgpt.util.configure.DynConfig` 工厂函数创建 `ConfigInfo`：
- 静态值 → 直接使用
- ConfigInfo → 运行时通过 `query()` 动态查询环境变量/配置服务/提示词管理器
- `is_list=True` → 自动分割字符串为列表

### 23.5 ProfileFactory 体系

| 工厂 | 说明 |
|------|------|
| `ProfileFactory` | 抽象基类 |
| `LLMProfileFactory` | 用 LLM 自动生成 profile（TODO） |
| `DatasetProfileFactory` | 从数据集创建（TODO） |
| `CompositeProfileFactory` | 组合多个工厂（TODO） |

***

## 24. Skills 技能集成

### 24.1 双体系架构

DB-GPT 存在两套并行的技能抽象：
1. **核心 Skill 体系**（`agent/skill/`）：标准化接口
2. **Claude 风格 FileBasedSkill 体系**（`agent/claude_skill/`）：SKILL.md 文件格式

两者通过 `loader.py` 桥接。

### 24.2 SkillType 枚举

```python
class SkillType(str, Enum):
    Coding = "coding"
    DataAnalysis = "data_analysis"
    WebSearch = "web_search"
    KnowledgeQA = "knowledge_qa"
    Chat = "chat"
    Custom = "custom"
```

### 24.3 SkillManager

`agent/skill/manage.py` L57-L1149，注册和管理所有 skill：

核心方法:

| 方法 | 说明 |
|------|------|
| `register_skill()` | 注册 skill 类或实例 |
| `get_skill()` | 按名称/类型查找 |
| `build_skill_from_parameters()` | 从 SkillParameters 构建 |
| `get_skill_content()` | 获取 SKILL.md 内容 |
| `get_skill_resource()` | 统一资源读取（文件/脚本/图片） |

**三种脚本执行路径**:

| 路径 | 方法 | 说明 |
|------|------|------|
| 路径一 | `execute_script()` | 执行 config 中内联定义的脚本 |
| 路径二 | `execute_skill_script_file()` | **主推荐**: 执行 scripts/ 目录的脚本文件，通过子进程执行 |
| 路径三 | `get_skill_resource()` | 统一资源访问 |

### 24.4 SKILL.md 解析

`agent/claude_skill/__init__.py`:

YAML frontmatter 格式：
```markdown
---
name: skill-name
description: Skill description
required_tools: [tool1, tool2]
config:
  scripts:
    - name: script_name
      code: "..."
---
Instructions here...
```

**`_parse_metadata()`**: 优先 PyYAML 解析，fallback 到按行解析。

**名称验证**: `_validate_skill_name` 要求 `^[a-z0-9]+(-[a-z0-9]+)*$`。

### 24.5 渐进式披露 (Progressive Disclosure)

**三层加载设计**:
1. **metadata 常驻**: 所有技能的 name+description 注入系统提示词
2. **SKILL.md 按需**: LLM 根据任务匹配后通过 `load_skill` 读取完整指令
3. **辅助资源按需**: scripts/references/templates 在执行时才访问

**SkillsMiddleware** (`skill/middleware.py` L301-L493):
- `load_skills()`: 从多个来源目录扫描 SKILL.md，后加载的覆盖同名
- `format_skills_list()`: 展示元数据（名称+描述），不加载全文
- `match_skills()`: 基于关键词的工具名称匹配
- `create_skills_prompt_section()`: 生成系统提示中的技能章节

### 24.6 安全机制

- **路径安全**: `_is_personal_skill_path()` 检测 user 目录 + realpath 双重验证（防御符号链接攻击）
- **脚本执行控制**: 环境变量 `DBGPT_DISABLE_PERSONAL_SKILL_SCRIPT_EXECUTION` 禁用个人 skill 的脚本执行
- **参数大小限制**: 工具参数截断上限 8KB
- **文件大小限制**: `MAX_SKILL_FILE_SIZE = 10MB`, `MAX_SKILL_NAME_LENGTH = 64`, `MAX_SKILL_DESCRIPTION_LENGTH = 1024`

### 24.7 Connector 与 Skill 集成

`resource/connector/skill_integration.py`:
- `resolve_skill_connectors()`: 根据 skill 的 `required_tools` 解析 MCPToolPack 实例
- `check_skill_connector_availability()`: 检查所需 connector 的可用性（available/missing）
- 缺失类型不阻断执行，仅记录 warning

### 24.8 文件路径防篡改

LLM 有时会破坏上传文件路径（如 `dbgpt-app` → `dbgpt_app`），系统用 `react_state["file_path"]` 强制覆盖 args 中的路径类键（input_file, file_path, data_path, csv_path 等）。

### 24.9 标记数据自动捕获

正则 `###([A-Z0-9_]+)_START###...(.*?)...###\1_END###`，脚本输出中用 `###CHART_DATA_JSON_START###...###CHART_DATA_JSON_END###` 标记的数据块会被自动提取。

***

## 25. API V1 深度分析

### 25.1 请求生命周期

`POST /v1/chat/completions` 完整流程（`api_v1.py` L526-L642）:

```
1. 接收 ConversationVo + 用户认证
2. adapt_native_app_model 适配
3. 检查 knowledge_space → 可能切换到 ChatKnowledge 模式
4. 设置 SSE Stream 响应头
5. 路由分发:
   ├── ChatAgent → multi_agents.app_agent_chat()
   ├── ChatFlow → flow_service.chat_stream_flow_str()
   ├── domain_type → chat_with_domain_flow()
   └── 其他 → get_chat_instance() → stream_generator/no_stream_generator
6. 异常处理: yield 错误信息为 SSE
7. finally: 记录最近使用应用
```

### 25.2 流式/非流式路径

**非流式** (`no_stream_generator` L730-L734): `chat.nostream_call()` → 完整响应 → yield SSE

**流式** (`stream_generator` L737-L820): `chat.stream_call()` → 异步迭代 chunk → `ChatCompletionStreamResponse` → `data: {json}\n\n` → `data: [DONE]\n\n`

**增量/全量**：通过 `incremental` 参数控制，增量模式只返回新增内容。

### 25.3 Editor API — SQL 编辑器

端点速览:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/editor/db/tables` | GET | 获取数据库表结构 |
| `/v1/editor/sql/rounds` | GET | 获取聊天轮次列表 |
| `/v1/editor/sql/run` | POST | 执行 SQL |
| `/v1/editor/chart/run` | POST | 执行图表 SQL |

**`sanitize_sql` 函数**（L98-L175）**内置 SQL 注入防护**:
- 移除注释
- 阻止多条语句
- 阻止危险操作 (DROP DATABASE, GRANT, REVOKE 等)
- DuckDB 额外拦截 COPY, EXPORT, INSTALL, PRAGMA
- 参数化字符串常量

### 25.4 Feedback API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/feedback/find` | GET | 查找反馈 (conv_uid + conv_index) |
| `/v1/feedback/commit` | POST | 创建/更新反馈 |

`ChatFeedBackDao`: 先查询 → 存在则 setattr 更新，否则 merge 新建。

### 25.5 Agentic Data API — Agent 数据 API

`agentic_data_api.py` 中的 `_select_connector_tools()` (L199-L236):
- 迭代用户选择的 `connector_ids`
- 调用 `connector_manager.get_connector_tools(cid)` 获取 MCPToolPack
- 扁平化为 `BaseTool` 列表注入到 Agent tool_pack
- 缺失的 connector 记录警告（优雅降级）

系统提示注入: 调用 `_cm.list_active()` 获取每个连接器的工具摘要，仅包含用户选择的连接器。

***

## 26. 数据源系统详情

### 26.1 连接器继承体系

```
BaseConnector (ABC)                        # 抽象基类 (datasource/base.py L12)
  └── RDBMSConnector                       # RDBMS 通用实现 (datasource/rdbms/base.py L114)
        ├── MySQLConnector                 # MySQL/PyMySQL
        ├── PostgreSQLConnector            # PostgreSQL/psycopg2
        ├── SQLiteConnector                # SQLite
        │     └── SQLiteTempConnector      # 内存临时 SQLite
        ├── DuckDbConnector                # DuckDB
        ├── ClickhouseConnector            # ClickHouse
        ├── DorisConnector                 # Apache Doris
        ├── MSSQLConnector                 # SQL Server
        ├── OracleConnector                # Oracle
        ├── StarRocksConnector             # StarRocks
        ├── HiveConnector                  # Hive
        ├── GaussDBConnector               # GaussDB
        ├── openGaussConnector             # openGauss
        ├── OceanBaseConnector             # OceanBase
        └── VerticaConnector               # Vertica
  └── Neo4jConnector / TuGraphConnector    # 图数据库
  └── SparkConnector                       # Spark
```

共支持 **16+ 种**数据库连接器。

### 26.2 连接池管理

`RDBMSDatasourceParameters`（`datasource/rdbms/base.py` L52-L111）：

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `pool_size` | 5 | 连接池大小 |
| `max_overflow` | 10 | 最大溢出连接数 |
| `pool_timeout` | 30 | 连接池超时 (秒) |
| `pool_recycle` | 3600 | 连接回收时间 (秒) |
| `pool_pre_ping` | True | 连接前健康检查 |

通过 `engine_args()` 方法将参数传递给 SQLAlchemy `create_engine()`。

### 26.3 SQL 执行流程

`RDBMSConnector.run()`（L620-L653）：

```
1. sqlparse 解析 SQL 获取 token 类型和 SQL 类型
2. DML (SELECT) → _query() 返回结果列表
3. DML (INSERT/UPDATE/DELETE) → _write() 执行写入
   → convert_sql_write_to_select() 将写入转为 SELECT 获取插入结果
4. DDL (CREATE/DROP) → 执行 DDL → get_simple_fields() 获取表结构
```

### 26.4 超时控制 (按方言差异化)

`RDBMSConnector.query_ex()`（L481-L612）：

| 数据库 | 超时机制 | 精度 |
|--------|---------|------|
| MySQL | `SET SESSION MAX_EXECUTION_TIME` | 毫秒 |
| PostgreSQL | `SET statement_timeout` | 毫秒 |
| OceanBase | `SET ob_query_timeout` | **微秒** |
| MSSQL | `sql.execution_options(timeout=...)` | — |
| DuckDB | `ThreadPoolExecutor` + `future.result(timeout=...)` | — |

### 26.5 Schema 检索

`_sync_tables_from_db()`（L225-L245）：使用 `inspect(engine).get_table_names()`，支持按 dialect 排除系统 schema。

`get_table_info()`（L324-L370）：生成符合 Rajkumar et al. 2022 论文最佳实践的格式，包含 CREATE TABLE 语句、采样行和索引信息。

### 26.6 边界情况

- **`convert_sql_write_to_select()`**（L681-L743）：对 INSERT/DELETE/UPDATE 正则解析转换，格式不匹配抛 `ValueError`
- **DBType 枚举**（`dbgpt-ext/datasource/schema.py` L17-L59）：定义了 16 种数据库类型
- **`DatasourceOperator`**（`datasource/operators/datasource_operator.py` L13）：AWEL 算子封装

### 26.7 Kyuubi 连接器与 Trino 兼容性

Kyuubi 是兼容 HiveServer2 Thrift 协议的多租户服务端，DB-GPT 通过 `KyuubiConnector`（`dbgpt-ext/datasource/rdbms/conn_kyuubi.py`）支持连接，复用 `pyhive` + `SQLAlchemy` 的 Hive 路径，在其上叠加两项 Kyuubi 特性：**ZooKeeper 服务发现** 和 **引擎类型会话配置**。

#### 继承体系

```
RDBMSConnector
  └── HiveConnector                  # 复用 Hive 协议层
        └── KyuubiConnector          # 增强: ZK 发现 + Trino 兼容

HiveParameters
  └── KyuubiParameters               # 增强: engine_type / service_discovery_mode
```

#### 连接入口与参数

`KyuubiParameters.from_persisted_state(config)` 从 SQLite 读取配置后构建 `KyuubiParameters`，由 `create_connector()` 调用 `KyuubiConnector.from_parameters(parameters)` 完成连接。

参数示例（ZK + Trino 场景）：

| 参数 | 值 |
|------|----|
| host | `zk1:2181,zk2:2181,zk3:2181` |
| database | `iceberg` |
| service_discovery_mode | `zooKeeper` |
| zoo_keeper_namespace | `kyuubi_adhoc` |
| engine_type | `TRINO` |

#### 两种连接模式

**直连模式**（host 不含逗号或 service_discovery_mode 不为 zooKeeper）：
- URL: `hive://[user:pass@]host:port/database`
- `connect_args.configuration` 注入 `{"kyuubi.engine.type": "TRINO"}`，由 pyhive 透传到 Thrift `TOpenSessionRequest`，Kyuubi 服务端据此启动对应引擎

**ZK 服务发现模式**（host 含逗号且 mode=zooKeeper）：
- URL: `hive:///database?serviceDiscoveryMode=zooKeeper&zooKeeperNamespace=xxx`（仅占位）
- 返回 `creator` 闭包函数作为 `engine_args.creator`，由 SQLAlchemy 在真正需要连接时延迟调用
- `creator()` 内部：`KazooClient` 连接 ZK → 读取 `/{namespace}` 下子节点 → 过滤 `serverUri=` 节点 → 随机选一个 → 调用 `pyhive.hive.connect(host, port, configuration={kyuubi.engine.type})`

#### Trino 引擎的三个 Monkey-Patch

当 `engine_type == "TRINO"` 时，pyhive 的一些硬编码与 Trino 不兼容，模块导入时执行三个补丁：

| 补丁 | 函数 | 作用 |
|------|------|------|
| USE 语句反引号替换 | `_patch_pyhive_for_trino` | `USE \`db\`` → `USE "db"` |
| Identifier Preparer | `_apply_trino_identifier_preparer` | 替换 `HiveIdentifierPreparer`，把 `initial_quote='`'` 改成 `'"'`，让反射 SQL 用双引号 |
| get_columns / get_indexes | `_patch_pyhive_get_columns_for_trino` | 兼容 Trino `DESCRIBE` 返回 4 列的情况；`get_indexes` 短路返回 `[]` |

#### `KyuubiConnector.__init__` 的 Trino 特殊处理

```python
if self._kyuubi_engine_type == "TRINO":
    _apply_trino_identifier_preparer(engine)        # 1. 替换 preparer
    # 2. 临时禁用 MetaData.reflect，避免 Trino 视图反射炸掉整个初始化
    _MetaData.reflect = _noop_reflect
    try:
        super().__init__(engine, **kwargs)          # 3. 调父类 (RDBMSConnector.__init__)
    finally:
        _MetaData.reflect = _orig_reflect            # 4. 恢复 reflect
```

**为什么禁用 reflect**：Trino 的 `SHOW TABLES` 返回视图、物化视图、临时表等无法被 `DESCRIBE` 的对象，`MetaData.reflect()` 遇到第一个失败就抛 `NoSuchTableError` 中断整个初始化。但 `RDBMSConnector.__init__` 依赖 `_sync_tables_from_db()` 获取表名列表（走 `inspector.get_table_names()`，不需要 reflect），所以可以安全跳过。

#### Trino 专有 Override 方法

| 方法 | 文件位置 | 作用 |
|------|---------|------|
| `get_table_comment` | `conn_kyuubi.py#L522-L553` | 直接查 `information_schema.tables.table_comment`，不走 SQLAlchemy inspector（HiveDialect 对 Trino 不生效） |
| `get_current_db_name` | `conn_kyuubi.py#L555-L564` | 从 `self._engine.url.database` 取，不发 `SELECT DATABASE()`（Trino 不支持这个语法） |

**`get_table_comment` 的关键作用**：向量化主路径 `_parse_table_summary_with_metadata` 调用此方法拿表注释，拼到 `table_str` 里向量化存入 ChromaDB。之前 Trino 下此方法失效，导致表注释无法进入向量库。

### 26.8 项目初始化与向量化全流程

#### 阶段 1：应用启动触发自动向量化（一次性）

```
dbgpt start webserver --profile glm
  │
  ├── initialize_app(param)
  │   └── initialize_components()
  │       └── register(ConnectorManager)            # 注册数据源管理组件
  │
  └── run_uvicorn()
      └── uvicorn.run()
          └── lifespan → startup_event()
              └── async_db_summary(system_app)       # base.py#L28-L34
                  └── thread.start(client.init_db_summary)
                      │
                      │  # 后台线程异步执行,不阻塞 uvicorn 启动
                      ▼
                  init_db_summary()                  # db_summary_client.py#L116
                  │
                  ├── db_mange.get_db_list()          # 从 SQLite 拉所有已配置的 db
                  │       (st_embed, kyuubi, ...)
                  │
                  └── for item in dbs:
                      └── db_summary_embedding(db_name, db_type)  # 逐个向量化
```

**触发条件**：应用每次启动都会跑一遍，对所有已配置数据库做向量化。

#### 阶段 2：单个数据库的向量化流程

```
db_summary_embedding("st_embed", "kyuubi")          # db_summary_client.py#L69
  │
  ├── _get_db_index_lock("st_embed").acquire()      # 加锁防止同一 db 并发向量化
  │
  ├── create_summary_client(dbname, db_type)
  │   └── ConnectorManager.get_connector("st_embed")  # 触发 connector 构建
  │       │
  │       │  # 缓存为空,构建新 connector
  │       └── _build_connector("st_embed")
  │           │
  │           ├── 读 SQLite: SELECT * FROM connect_config WHERE db_name='st_embed'
  │           ├── 取出配置(host=zk1,zk2,zk3, engine_type=TRINO, ...)
  │           ├── param_cls = KyuubiParameters
  │           ├── param = KyuubiParameters.from_persisted_state(config)
  │           └── param.create_connector()
  │               └── KyuubiConnector.from_parameters(param)
  │                   ├── parameters.db_url()            # hive:///iceberg?serviceDiscoveryMode=zooKeeper&...
  │                   ├── parameters.engine_args()       # {creator: _build_zk_creator()}
  │                   └── create_engine(db_url, **engine_args)
  │                       └── KyuubiConnector.__init__(engine, engine_type="TRINO")
  │                           ├── 存 self._kyuubi_engine_type = "TRINO"
  │                           ├── _apply_trino_identifier_preparer(engine)  # 反引号→双引号
  │                           ├── 临时禁用 MetaData.reflect
  │                           ├── super().__init__(engine)
  │                           │   └── RDBMSConnector.__init__
  │                           │       ├── self._inspector = inspect(engine)
  │                           │       ├── self._db_sessions = scoped_session(...)
  │                           │       ├── self._metadata.reflect()     # 空操作(已禁用)
  │                           │       └── self._all_tables = _sync_tables_from_db()
  │                           │           └── inspector.get_table_names()   # [t1, t2, ...]
  │                           └── 恢复 MetaData.reflect
  │
  │   # connector 已就绪,继续向量化
  │
  └── init_db_profile(db_summary_client, "st_embed")  # db_summary_client.py#L131
      │
      ├── _get_vector_connector_by_db("st_embed")     # 拿 Chroma 向量存储连接
      │   ├── table_vector_connector   (集合: st_embed_profile)
      │   └── field_vector_connector   (集合: st_embed_field_profile)
      │
      ├── vector_name_exists()?                         # 检查是否已向量化过
      │   ├── 已存在 → 跳过(不重复向量化,节省 embedding API 成本)
      │   └── 不存在 ↓
      │
      ├── DBSchemaAssembler.load_from_connection(connector, ...)
      │   │
      │   ├── 遍历 connector.get_table_names()         # [t1, t2, t3, ...]
      │   │
      │   └── for table_name in [t1, t2, ...]:
      │       └── _parse_table_summary_with_metadata(conn, table_name)
      │           │
      │           ├── conn.get_columns(table_name)      # DESCRIBE "table_name"
      │           │   └── 返回 [{name, type, comment, ...}, ...]
      │           │
      │           ├── conn.get_indexes(table_name)      # Trino 返回 []
      │           │
      │           ├── conn.get_table_comment(table_name) # ← KyuubiConnector override 的方法
      │           │   │
      │           │   ├── if TRINO:
      │           │   │   └── SELECT table_comment FROM information_schema.tables
      │           │   │       WHERE table_schema='iceberg' AND table_name='xxx'
      │           │   │       → {"text": "订单表"}
      │           │   │
      │           │   └── else:
      │           │       └── super().get_table_comment()  # inspector API
      │           │
      │           └── 拼成 table_str:
      │               "table_name(col1(col1 comment),col2(col2 comment),
      │                and index keys, and table comment: 订单表)"
      │
      ├── chunk_parameters = ChunkParameters(text_splitter=...)
      │
      └── db_assembler.persist()
          │
          ├── embeddings.embed_documents(chunks)       # 调用 Embedding API 向量化
          │   └── POST https://api.openai.com/v1/embeddings
          │
          └── vector_store_connector.persist(vectors)
              └── ChromaDB 写入 (pilot/data/chromadb/)
                  ├── collection: st_embed_profile       (表级向量)
                  └── collection: st_embed_field_profile (字段级向量)
```

**关键细节**：
- **锁机制**：`_get_db_index_lock` 确保同一 db 不会被并发向量化
- **幂等性**：`vector_name_exists()` 检查 ChromaDB 集合是否存在，已存在则跳过，避免重复消耗 embedding API
- **双集合**：每个 db 生成两个 ChromaDB 集合，`{db}_profile` 存表级 schema，`{db}_field_profile` 存字段级
- **表注释流转**：`get_table_comment` 返回 `{"text": "xxx"}` → `_parse_table_summary_with_metadata` 拼到 `table_str` → 向量化进 ChromaDB，后续用户问题语义检索能召回

#### 阶段 3：用户查询时的检索与使用流程

```
用户问"dwd_fa_ecc_die_di 这张表是用来干什么的"
  │
  ├── POST /api/v1/chat/react-agent
  │   └── ext_info.database_name = "st_embed"
  │
  └── _react_agent_stream(dialogue)
      │
      ├── ConnectorManager.get_connector("st_embed")
      │   │
      │   │  # 30 分钟内,直接返回缓存的 connector
      │   └── return cached_connector
      │
      ├── DBSummaryClient(system_app)
      │   └── get_similar_tables(query, "st_embed", topk=5)
      │       │
      │       ├── DBSchemaRetriever(table_store, field_store)
      │       │
      │       ├── table_docs = retriever.retrieve(query)
      │       │   │
      │       │   ├── embedding.embed_query(query)    # 把用户问题向量化
      │       │   │   └── POST /v1/embeddings {query}
      │       │   │
      │       │   └── ChromaDB.similarity_search(vector, top_k=5)
      │       │       └── 返回最相关的 5 张表的 table_str
      │       │           (包含表名、列、注释: "dwd_fa_ecc_die_di(id,col2,...),
      │       │            and table comment: 订单事实表")
      │       │
      │       └── return [doc.content for doc in table_docs]
      │
      └── 拼到 LLM Prompt:
          """
          ## 数据库信息
          - 数据库名: st_embed
          - 可用表: ...
          - 表结构: dwd_fa_ecc_die_di(id,col2,...), and table comment: 订单事实表
          - 使用 'sql_query' 工具执行 SQL 查询
          """
          → LLM 理解表结构和注释 → 生成正确 SQL
```

**检索优势**：表注释进入向量库后，用户用自然语言问"订单表是哪张"时，语义检索能通过"订单"召回注释为"订单事实表"的 `dwd_fa_ecc_die_di` 表，而不依赖表名硬匹配。

#### 阶段 4：运行期间 30 分钟 TTL 过期后的自动刷新

`ConnectorManager.get_connector` 的缓存机制（详见 26.2 节）配合 schema-change detection 实现：

```
某次 chat 请求 → get_connector("st_embed")
  │
  ├── 缓存过期 (>30 分钟)
  │
  ├── prev_tables = cached_connector.get_table_names()  # 旧表列表快照
  │       = {t1, t2, t3}
  │
  ├── _build_connector("st_embed")                      # 重建 connector
  │   └── KyuubiConnector.__init__ → _sync_tables_from_db()
  │       └── new_tables = {t1, t2, t3, t4_new}          # t4_new 是新增的表
  │
  ├── if new_tables != prev_tables:                      # 集合不一致
  │   └── _trigger_schema_embedding("st_embed")
  │       ├── executor.submit(db_summary_embedding, "st_embed", "kyuubi")
  │       │   # 异步触发向量库刷新,不阻塞当前用户请求
  │       │
  │       └── 后台执行阶段 2 的完整流程
  │           └── ChromaDB 被重新填充,包含 t4_new 的 schema 和注释
  │
  └── return new_connector                              # 用户请求照常返回
```

**设计要点**：
- **零常态开销**：30 分钟缓存有效期内直接走缓存，不做任何检测
- **异步刷新**：`ThreadPoolExecutor` 提交后台任务，不阻塞用户请求
- **Best-effort**：刷新失败只记 warning 日志，不影响 chat 主流程
- **冷启动不误触发**：首次缓存为空时 `prev_tables is None`，跳过检测（不算"变化"）
- **作用域**：只在 `ConnectorManager.get_connector` 路径触发，其他直接构造 connector 的场景不触发

### 26.9 Schema 自动感知与向量库刷新

#### 问题背景

原架构存在两个 gap：

1. **表注释缺失**：`get_table_comment` 在 Trino 下走 SQLAlchemy inspector，HiveDialect 实现对 Trino 不生效，返回空，导致表注释无法进入向量库
2. **向量库不自动更新**：`ConnectorManager` 30 分钟 TTL 过期后会重建 connector 刷新 `_all_tables`，但向量库（ChromaDB）不会跟着刷新，新增表/字段不会进入向量检索范围

#### 修复方案

| 问题 | 修复点 | 文件位置 |
|------|--------|---------|
| 表注释缺失 | Override `get_table_comment`，Trino 模式直接查 `information_schema.tables` | `conn_kyuubi.py#L522-L553` |
| `SELECT DATABASE()` 失败 | Override `get_current_db_name`，Trino 模式从 `engine.url.database` 取 | `conn_kyuubi.py#L555-L564` |
| 向量库不自动更新 | `get_connector` 中对比新旧 table_names，变化时异步触发 `db_summary_embedding` | `connector_manager.py#L211-L296` |

#### `get_table_comment` 的异常兜底设计

```python
def get_table_comment(self, table_name: str) -> Dict:
    if self._kyuubi_engine_type != "TRINO":
        return super().get_table_comment(table_name)
    try:
        db_name = self.get_current_db_name()
        with self.session_scope() as session:
            cursor = session.execute(text(
                f"SELECT table_comment FROM information_schema.tables "
                f"WHERE table_schema = '{db_name}' AND table_name = '{table_name}'"
            ))
            row = cursor.fetchone()
            return {"text": row[0] if row else None}
    except Exception as e:
        logger.warning("Kyuubi get_table_comment failed for %s: %s", table_name, e)
        return {"text": None}
```

**设计考虑**：
- 返回 `{"text": "xxx"}` 保持与父类返回格式一致，让调用方 `_parse_table_summary_with_metadata` 的 `comment.get("text")` 正常工作
- 单表注释查询失败不中断整个向量化的流程，只记 warning 日志

#### Schema-change detection 的实现

`ConnectorManager.get_connector` 在缓存过期重建时执行：

1. **snapshot 旧表名**：重建前从旧 connector 拿 `get_table_names()`
2. **重建 connector**：走 `_build_connector` 流程，新 connector 的 `_all_tables` 是最新表名列表
3. **对比集合**：`set(new_tables) != set(prev_tables)` 判断是否变化
4. **异步触发**：变化则 `executor.submit(db_summary_embedding, db_name, db_type)` 刷新向量库

**为什么不直接在 `_sync_tables_from_db` 里加检测**：`_sync_tables_from_db` 在 `RDBMSConnector` 基类，属于 core 层，不应该感知 serve 层的 `DBSummaryClient`。放在 `ConnectorManager` 是因为它是 serve 层组件，能访问 `system_app` 拿到 `DBSummaryClient`。

***

## 27. 缓存系统

### 27.1 核心数据模型

`LLMCacheKey`（`storage/cache/llm_cache.py` L83-L118）：

缓存 key 由以下字段组合生成：
- `prompt` (string)
- `model_name` (string)
- `temperature` (float, default 0.7)
- `max_new_tokens` (int)
- `model_type` (string, default "huggingface")

**Hash 算法**：`int(hashlib.sha256(serialize_bytes).hexdigest(), 16)`

`LLMCacheValue`（L120-L138）：存储 `ModelOutput` 或 `List[ModelOutput]`，支持单输出和流式多输出。

### 27.2 三种存储后端

| 后端 | 文件 | 实现 | 特点 |
|------|------|------|------|
| **Memory** | `storage/base.py` L194-L267 | `OrderedDict` | LRU/FIFO 淘汰，最大 256MB，`EXACT_MATCH` 策略 |
| **Disk** | `disk/disk_storage.py` L49-L100 | RocksDB (`rocksdict.Rdict`) | Key/value 均为 bytes，持久化到磁盘 |
| **Valkey** | `dbgpt-ext/valkey_cache.py` L25-L327 | valkey-glide 客户端 | 同步/异步，可配 TTL，SSL 支持 |

### 27.3 AWEL Operator 集成

| Operator | 文件/行号 | 功能 |
|----------|----------|------|
| `ModelCacheBranchOperator` | `operators.py` L98-L160 | 分支决策：检查缓存命中 |
| `CachedModelOperator` | L63-L95 | 从缓存读取 Map 模式输出 |
| `CachedModelStreamOperator` | L25-L60 | 从缓存流式输出 |
| `ModelSaveCacheOperator` | L206-L235 | 保存单次模型输出 |
| `ModelStreamSaveCacheOperator` | L163-L203 | 保存流式输出（仅成功 output） |

**关键流**：
```
ModelRequest → _parse_cache_key_dict() → LLMCacheKey (SHA-256)
  → ModelCacheBranchOperator 分支
    → 命中: CachedModelOperator / CachedModelStreamOperator
    → 未命中: 模型推理 → ModelSaveCacheOperator (error_code == 0 才保存)
```

***

## 28. 全文搜索与图存储

### 28.1 Elasticsearch 全文搜索

核心文件：`packages/dbgpt-ext/src/dbgpt_ext/storage/full_text/elasticsearch.py`

**索引配置**：
- 命名规则：默认小写；含中文时十六进制编码（`"dbgpt_" + name.encode("utf-8").hex()`）
- BM25 相似度参数：`k1=2.0`, `b=0.75`（可配置）
- 字段映射：`content` 为 text 类型（custom_bm25 相似度），`metadata` 为 object 类型（动态）

**文档索引**（`load_document()` L136-L166）：使用 ES `bulk` API 批量索引，每个 chunk 映射为 `{_index, _id, content, metadata}`。

**全文搜索**（`similar_search_with_scores()` L198-L238）：
- 查询：`{"bool": {"must": [{"match": {"content": text}}]}}`
- 支持 `score_threshold` 过滤（默认 0.3）
- 返回 `Chunk` 对象，含 BM25 `_score`

**元数据过滤**：将 `MetadataFilters` 转换为 ES `bool` query，支持 EQ/IN/NE/AND/OR。

### 28.2 图存储

**图元素类型**（`graph_store/graph.py` L15-L48）：
- 顶点：`DOCUMENT`、`CHUNK`、`ENTITY`
- 边：`RELATION`、`INCLUDE`、`NEXT`
- 复合边：`DOCUMENT_INCLUDE_CHUNK`、`CHUNK_INCLUDE_ENTITY`、`CHUNK_NEXT_CHUNK` 等

**MemoryGraph 实现**（L285-L580）：
- 三个 defaultdict 索引：`_vs`（顶点）、`_oes`（出边）、`_ies`（入边）
- BFS 搜索（`search()` L460-L513）：支持 `depth`（深度限制）、`fan`（出度限制）、`limit`（边数限制），`_visited` set 避免环
- `graphviz()` 生成 DOT 格式可视化

**三种存储后端**：

| 后端 | 文件 | 特点 |
|------|------|------|
| `MemoryGraphStore` | `memgraph_store.py` L18-L28 | 内存实现 |
| `Neo4jStore` | `dbgpt-ext/neo4j_store.py` L150-L191 | 支持社区摘要、相似度搜索 |
| `TuGraphStore` | `dbgpt-ext/tugraph_store.py` L145-L230 | 支持插件上传（如 leiden 算法） |

**工厂模式**：`GraphStoreFactory`（`factory.py` L12-L50）通过字符串类型名动态创建。

***

## 29. 嵌入模型管理

### 29.1 EmbeddingFactory 体系

`DefaultEmbeddingFactory`（`rag/embedding/embedding_factory.py` L58-L208）提供三种创建方式：

| 方法 | 行号 | 说明 |
|------|------|------|
| `default(model_name)` | L158-L176 | 通过 `get_embedding_adapter("hf", ...)` 加载本地 HuggingFace 模型 |
| `remote(api_url, api_key, model_name)` | L178-L208 | 创建 `OpenAPIEmbeddings`，默认 `http://localhost:8100/api/v1/embeddings` |
| `openai(api_url, api_key, model_name)` | L118-L155 | 创建 OpenAI API embeddings，默认 `https://api.openai.com/v1/embeddings` |

`WrappedEmbeddingFactory`（L211-L241）：包装另一个 factory，用于在创建前后插入自定义逻辑。

### 29.2 嵌入模型后端

| 类 | 后端 | 库依赖 | 关键特性 |
|---|------|-------|---------|
| `HuggingFaceEmbeddings` | SentenceTransformers | `sentence-transformers` | 通用模型，多 GPU |
| `HuggingFaceInstructEmbeddings` | InstructorEmbedding | `InstructorEmbedding` | 指令感知 |
| `HuggingFaceBgeEmbeddings` | SentenceTransformers + BGE | `sentence-transformers` | BGE 模型，中英文查询指令 |
| `HuggingFaceInferenceAPIEmbeddings` | HuggingFace Inference API | `requests` | 远程 API 调用 |
| `OpenAPIEmbeddings` | OpenAI 兼容 API | `requests` + `aiohttp` | 异步支持，trace ID 传递 |

### 29.3 Rerank 模型

| 类 | 后端 | 算法 |
|---|------|------|
| `CrossEncoderRerankEmbeddings` | sentence-transformers CrossEncoder | Cross-Encoder 评分 |
| `QwenRerankEmbeddings` | Qwen3-Reranker (CausalLM) | yes/no logits 对比 |
| `OpenAPIRerankEmbeddings` | OpenAI 兼容 Rerank API | HTTP POST |
| `SiliconFlowRerankEmbeddings` | 硅基流动 Rerank API | 专有 `relevance_score` |
| `TeiRerankEmbeddings` | Text Embeddings Inference | TEI `/rerank` 端点 |
| `InfiniAIRerankEmbeddings` | InfiniAI Rerank API | 专有 `relevance_score` |

**QwenRerank 算法**（`rerank.py` L351-L359）：
1. 构造 `prefix_tokens + tokenized(instruction+query+doc) + suffix_tokens`
2. 填充到 `max_length=8192`，left padding
3. 通过 CausalLM 计算 logits
4. 取最后一个 token 的 `token_true_id` 和 `token_false_id` logits
5. log_softmax 后取 `yes` 概率作为分数

### 29.4 模型注册机制

（`embeddings.py` L918-L1004）：通过 `register_embedding_adapter()` 将特定模型名（如 `thenlper/gte-large-zh`、`moka-ai/m3e-base`、`text-embedding-3-small`）注册到对应嵌入类。

**调用流程**：
```
EmbeddingFactory.create(model_name)
  → get_embedding_adapter(provider, model_name)
  → adapter.model_param_class() → EmbeddingDeployModelParameters
  → adapter.load_from_params(params) → Embeddings instance
  → embeddings.embed_documents(texts) / embeddings.embed_query(text)
```

***

## 30. 评估与基准测试系统

### 30.1 核心架构

`Service`（`packages/dbgpt-serve/src/dbgpt_serve/evaluate/service/service.py` L45）和 `BenchmarkService`（`benchmark/benchmark_service.py` L77）分别管理评估和基准测试。

### 30.2 评估场景

`EvaluationScene` 枚举（`api/schemas.py` L9）：

| 场景 | 说明 |
|------|------|
| `RECALL` | RAG 召回评估 |
| `APP` | Agent 应用评估 |

**RECALL 场景流程**（L106-L145）：
1. 获取 `EmbeddingFactory`
2. 加载知识空间
3. 创建 `RetrieverEvaluator` + `SpaceRetrieverOperator`
4. 选择指标：`RetrieverSimilarityMetric`（余弦相似度）+ `metric_manage` 插件
5. 对每个数据集，加载 chunk 内容作为上下文
6. `evaluator.evaluate(datasets, metrics, parallel_num)`

**APP 场景流程**（L146-L180）：
1. 创建 `AgentEvaluator` + `AgentOutputOperator`
2. 选择指标：`AnswerRelevancyMetric`（LLM 判断答案相关性）+ 插件
3. 预取知识资源
4. `evaluator.evaluate(dataset, metrics, parallel_num)`

### 30.3 基准测试

`BenchmarkService` 将基准测试作为 **FastAPI BackgroundTasks** 运行：
- 支持 `BenchmarkLLMTask`（LLM 基准）和 `BenchmarkAgentTask`（Agent 基准）
- 文件解析：`ext/falcon_file_parse.py`、`ext/excel_file_parse.py`
- 数据对比：`data_compare_service.py`
- 结果存储：`BenchmarkResultDao`
- 数据集管理：`BenchmarkDataManager`

### 30.4 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/evaluation` | POST | 运行评估 |
| `/execute_benchmark_task` | POST | 启动基准测试（后台任务） |
| `/benchmark/result/{evaluate_code}` | GET | 获取每轮 accuracy/execRate |
| `/benchmark_task_list` | GET | 分页任务列表 |
| `/benchmark/list_datasets` | GET | 浏览数据集 |

***

## 31. 链路追踪系统

### 31.1 Span 生命周期

核心文件：`packages/dbgpt-core/src/dbgpt/util/tracer/`

**`SpanType` 枚举**（`base.py` L23）：`BASE`、`RUN`、`CHAT`、`AGENT`

**Span 创建**（`DefaultTracer.start_span`, `tracer_impl.py` L46）：
1. `trace_id` = 随机 128 位 hex 或从 `parent_span_id` 提取
2. `span_id` = `f"{trace_id}:{64位随机hex}"`
3. 根据 `SpanStorageType`（`ON_CREATE` / `ON_END` / `ON_CREATE_END`）决定何时写入存储
4. 推入 `ContextVar` span 栈

**Span 结束**（`base.py` L77）：记录 `end_time` → 可选更新 metadata → 调用 `_end_callers`。

**上下文传播**：`_parse_span_id()`（`base.py` L316）从请求头 `DB-GPT-Trace-Span-Id` 或 `span_id` 字段提取 span_id。

### 31.2 Span 存储

| 存储 | 特点 |
|------|------|
| `MemorySpanStorage` | 内存列表 |
| `FileSpanStorage` | JSONL 文件，**每日滚动**（`{prefix}_{YYYY-MM-DD}{suffix}`） |
| `SpanStorageContainer` | 批处理容器：`queue.Queue` 缓冲，后台线程按 `batch_size` 或 `flush_interval` 刷新 |

### 31.3 追踪覆盖范围

| 位置 | Span 名称 |
|------|----------|
| AWEL workflow | `"dbgpt.awel.workflow.run_workflow"`, `"dbgpt.awel.workflow.run_operator"` |
| AWEL operator | `"dbgpt.awel.operator.call"`, `"dbgpt.awel.operator.call_stream"` |
| HTTP trigger | `"dbgpt.core.trigger.http.run_dag"` |
| Worker manager | `"WorkerManager.generate_stream"`, `"WorkerManager.embeddings"` 等 |
| Model controller | `"dbgpt.model.controller.register_instance"` 等 |

### 31.4 @trace 装饰器

`@trace`（`tracer_impl.py` L207）：包装同步/异步函数，自动提取函数参数为 metadata（排除 `self`/`cls`），`operation_name` 从函数名或 `ClassName.func_name` 派生。

***

## 32. 对话管理系统

### 32.1 初始化

`ConversationServe.init_app()`（`serve.py` L60）：
- `on_init()`：注册 `ChatHistoryEntity` 和 `ChatHistoryMessageEntity` 数据库模型
- `before_start()`：创建两个 `SQLAlchemyStorage` — 对话存储（`DBStorageConversationItemAdapter`）和消息存储（`DBMessageStorageItemAdapter`）

### 32.2 对话生命周期

| 操作 | 端点 | 说明 |
|------|------|------|
| 创建 | `POST /new` | 生成 `conv_uid`（`uuid.uuid1()`） |
| 查询 | `POST /query` | 按 `ServeRequest` 过滤 |
| 列表 | `GET /list` | 按 `gmt_created DESC` 分页 |
| 历史 | `GET /messages/history` | 返回 `MessageVo` 列表 |
| 删除 | `POST /delete` | 删除对话 |
| 清除 | `POST /clear` | 保留对话，清除消息 |
| 导出 | `GET /export_messages` | 导出所有对话和消息 |

### 32.3 消息历史增强

`Service.get_history_messages()`（`service/service.py` L187）：
1. 调用 `_append_view_messages(conv.messages)` 追加系统/视图消息
2. 从 `feedback_service` 丰富反馈数据
3. 应用于 `vis_name_change()` 视觉组件渲染
4. 附加 `model_name`（从 `ServeConfig.default_model` 获取）

### 32.4 数据模型

| 实体 | 表 | 唯一约束 |
|------|-----|---------|
| `ChatHistoryEntity` | — | `conv_uid` |
| `ChatHistoryMessageEntity` | — | `(conv_uid, index)` |

**向后兼容**：支持旧消息格式（`messages` 列在 `ChatHistoryEntity` 上），通过 `_parse_old_messages()` 从最终轮的 chat data 中提取 `param_value`。

### 32.5 双层存储架构

- **对话存储**：`StorageConversation` 存储对话容器
- **消息存储**：`MessageStorageItem` 存储每个对话的消息
- 后备链：注入存储 → `Serve.call_on_current_serve()` → `InMemoryStorage`（

`ServePreChatHistoryLoadOperator` AWEL 算子）

***

## 33. 模型集群与 Worker 管理

### 33.1 核心类型

| 类型 | 说明 |
|------|------|
| `WorkerType` | LLM / TEXT2VEC / RERANKER |
| `WorkerRunData` | 封装 worker、参数、`asyncio.Semaphore(concurrency)`（并发控制）、`stop_event` |

### 33.2 Worker 生命周期

**启动**（`LocalWorkerManager.start()`, `worker/manager.py` L148）：
1. 若有已注册 workers → `_start_all_worker()`
2. 注册 manager 自身（`register_func`）
3. 启动心跳发送器（20s 间隔）
4. 若 `model_storage` 存在 → 重新加载持久化模型

**模型启动**（`model_startup()`, L279）：
1. 解析配置为 `LLMDeployModelParameters` / `EmbeddingDeployModelParameters` / `RerankerDeployModelParameters`
2. `_build_worker()` 构建 worker
3. `add_worker()` 加载并创建 `WorkerRunData`（含 `asyncio.Semaphore(concurrency)`）
4. `worker_apply(START)` 启动
5. 保存到 `model_storage`
6. **失败 → 移除 worker + 抛出**

**模型关闭**（`model_shutdown()`, L352）：创建 `WorkerApplyRequest(STOP)` → `_stop_all_worker()` → 可选从 `model_storage` 删除。

### 33.3 心跳与健康检查

`EmbeddedModelRegistry`（`registry.py` L127）：
- 线程 `_heartbeat_checker` 每 `heartbeat_interval_secs`（默认 60s）轮询
- `now - last_heartbeat > heartbeat_timeout_secs`（默认 120s）→ 标记 `healthy = False`

### 33.4 负载均衡

当前实现：`_simple_select()`（`worker/manager.py` L405）使用 **`random.choice()`**（L413），按 `asyncio.Semaphore` 控制每个 worker 并发。

### 33.5 远程 Worker 模式

`RemoteWorkerManager`（`worker/remote_manager.py` L17）：继承 `LocalWorkerManager`，覆写 `get_model_instances()` 查询 `ModelRegistry` 而非本地字典。通过 `httpx` 代理 HTTP 请求到远程 worker 端点。

### 33.6 Worker Manager REST API

File：`worker/manager.py` L879-L960

| 端点 | 方法 | 说明 |
|------|------|------|
| `/worker/generate_stream` | POST | 流式生成 |
| `/worker/generate` | POST | 非流式生成 |
| `/worker/embeddings` | POST | 嵌入 |
| `/worker/count_token` | POST | Token 计数 |
| `/worker/model_metadata` | POST | 模型元数据 |
| `/worker/apply` | POST | 启动/停止/重启/更新参数 |
| `/worker/models/startup` | POST | 启动模型 |
| `/worker/models/shutdown` | POST | 关闭模型 |

### 33.7 ModelController

`LocalModelController` 包装 `ModelRegistry`，`_RemoteModelController` 通过 HTTP 客户端实现远程模型注册。Controller 路由：`/controller/models` (POST/GET/DELETE)、`/controller/heartbeat`。

***

## 34. 客户端 SDK

### 34.1 核心连接

`Client`（`packages/dbgpt-client/src/dbgpt_client/client.py` L52-L395）：
- 默认 API 地址：`http://localhost:5670/api/v2`
- 从环境变量 `DBGPT_API_BASE` 和 `DBGPT_API_KEY` 读取配置
- API Key 通过 `Authorization: Bearer {api_key}` 传递
- 使用 `httpx.AsyncClient` 作为 HTTP 客户端

### 34.2 主要 API

| 方法 | 说明 |
|------|------|
| `chat()` | 非流式 Chat Completion（POST `/api/v2/chat/completions`） |
| `chat_stream()` | 流式 Chat Completion（SSE 解析，`data: [DONE]` 结束） |
| `get()` / `post()` / `put()` / `delete()` | 通用 REST 操作 |

### 34.3 模块化封装

| 模块 | 功能 |
|------|------|
| `knowledge.py` | 知识空间/文档 CRUD（L1-L231） |
| `datasource.py` | 数据源 CRUD（L1-L121） |
| `flow.py` | AWEL Flow 管理和执行（L1-L300） |

### 34.4 CLI 接口

支持 `dbgpt flow chat` 和 `dbgpt flow cmd` 命令，`--local` 标志支持本地 AWEL 文件执行，`--interactive` 支持交互式对话。自动生成 `conv_uid`（UUID4）用于多轮对话。

***

## 35. 补充子系统

### 35.1 国际化 (i18n)

核心文件：`packages/dbgpt-core/src/dbgpt/util/i18n_utils.py`

**实现机制**：基于 GNU gettext，默认 domain 为 `"dbgpt"`。`set_default_language()` 可运行时切换语言（`"zh"` 标准化为 `"zh_CN"`）。自定义 `_find()` 在 `localedir/lang/LC_MESSAGES/` 下定位 `.mo` 文件。

**`LazyTranslatedString` 类**（L211-L291）：继承 `str`，存储原始消息和 domain 引用，仅在 `__str__()` 访问时惰性翻译。支持 `__hash__`、`__eq__`、`__bool__`、`__add__` 等完整 str 接口。**关键**：跟踪 `_last_language`，语言切换后自动重新翻译。包含自定义 Pydantic 序列化器以兼容 `SchemaSerializer`。

**全局 `_` 函数**（L294-L298）返回 `LazyTranslatedString`。`_install()` 将其注入 `builtins._`。

### 35.2 CLI 系统完整命令树

主入口：`packages/dbgpt-core/src/dbgpt/cli/cli_scripts.py` L17-L26

| 父级 | 命令 | 功能 |
|------|------|------|
| `cli` | `start` | 启动服务器（默认 `web`/`webserver`） |
| `cli` | `stop` | 停止服务器 |
| `cli` | `db` | 管理数据库和数据源 |
| `cli` | `new` | 创建新模板/组件 |
| `cli` | `app` | 管理 dbgpts 应用（install/uninstall/list） |
| `cli` | `repo` | 管理 dbgpt 仓库 |
| `cli` | `run` | 运行 dbgpts |
| `cli` | `net` | 网络转发工具 |
| `cli` | `tool` | DB-GPT 工具 |
| `cli` | `setup` | 配置向导（支持 `--yes` 非交互） |
| `cli` | `profile` | 管理配置概览（list/show/create/switch/delete） |
| `cli` | `model` | 模型集群管理（start/stop/list/restart/chat） |
| `cli` | `trace` | 追踪分析（list/chat/tree，读取 JSONL 日志） |
| `start` | `webserver`/`web`/`controller`/`worker`/`apiserver` | 启动特定服务 |
| `stop` | `all`/`webserver`/`controller`/`worker`/`apiserver` | 停止服务 |

**特点**：各子系统导入通过 try/except ImportError 块包裹，失败时优雅降级。`add_command_alias()` 实现命令别名（深拷贝实现）。

### 35.3 动态导入与模块扫描

核心文件：`packages/dbgpt-core/src/dbgpt/util/module_utils.py`

- `import_from_string(module_path)`（L16-L30）：将点分隔路径解析为模块和类名，动态导入
- `import_from_checked_string(module_path, supper_cls)`（L33-L39）：额外验证继承关系

**`ModelScanner`**（L63-L303）：全功能模块扫描器，支持：
- 扫描 Python 包中的具体类（排除抽象类）
- 按基类和自定义过滤函数过滤
- 递归目录扫描和特定文件扫描
- 子注册解引用（通过 `__scan_config__` 和 `__is_already_scanned__`）
- `_registered_items` 字典维护已注册项

### 35.4 实用工具

| 工具 | 文件 | 说明 |
|------|------|------|
| `Singleton` 元类 | `util/singleton.py` | ABCMeta+type 元类，`_instances` 字典 |
| `is_all_chinese` / `contains_chinese` | `util/string_utils.py` | 中文字符检测 |
| `EnhancedJSONEncoder` | `util/json_utils.py` | 序列化 dataclass/datetime/date/time |
| `find_json_objects()` | `util/json_utils.py` L50 | 从混合文本中提取 JSON 对象（含 markdown 代码块） |
| `StrictFormatter` | `util/formatting.py` | 拒绝多余 kwargs 的格式化器 |
| `FixedSizeDict` | `util/custom_data_structure.py` | 最大大小受限的 OrderedDict |
| `PriorityAPIRouter` | `util/fastapi.py` | 按优先级排序路由的 FastAPI Router |
| `@PublicAPI(stability="beta")` | `util/annotations.py` | 公共 API 稳定性标记装饰器 |

### 35.5 消息模型层次

核心文件：`packages/dbgpt-core/src/dbgpt/core/interface/message.py`

| 类 | `type` 属性 | `pass_to_model` | 说明 |
|-----|-------------|-----------------|------|
| `BaseMessage` | 抽象 | True | Pydantic 消息基类，`content` 支持 `Union[str, List[MediaContent]]` |
| `HumanMessage` | `"human"` | True | 用户消息 |
| `AIMessage` | `"ai"` | True | AI 回复 |
| `SystemMessage` | `"system"` | True | 系统指令 |
| `ViewMessage` | `"view"` | **False** | 仅前端渲染，不传给模型 |

**`ModelMessage`**（L183）：核心 LLM 传输格式，含 `role` 和 `round_index`。
- `from_base_messages()`：将 `BaseMessage` 列表转换
- `from_openai_messages()`：解析 OpenAI ChatCompletion 格式
- `to_common_messages()`：转换为 OpenAI 兼容格式（支持 `type_mapping`）
- `parse_model_messages()`（L630）：将消息分组为 `(user_prompt, system_messages, history)`

**`OnceConversation`**（L713）：单次对话的内存表示，跟踪 `chat_mode`、`chat_order`、消息列表。

**`StorageConversation`**（L1170）：`OnceConversation` 的持久化版本，与 `StorageInterface` 集成，支持增量 `save_to_storage()` / `load_from_storage()`。

**消息流**：`BaseMessage` 子类 → `OnceConversation.get_model_messages()` → `ModelMessage` 列表 → 传入 `LLMClient.generate()` / `generate_stream()`。

### 35.6 Prompt 管理系统

核心文件：`packages/dbgpt-serve/src/dbgpt_serve/prompt/`

**模板层次**（`core/interface/prompt.py`）：

| 类 | 说明 |
|-----|------|
| `BasePromptTemplate` | 基础类，`input_variables` 列表 |
| `PromptTemplate` | 支持 `f-string` 和 `jinja2` 格式，可选 `response_format`（JSON schema），`template_is_strict` 标志 |
| `ChatPromptTemplate` | 由聊天模板/占位符列表构建的复合模板 |
| `SystemPromptTemplate` / `HumanPromptTemplate` | 生成 `SystemMessage` / `HumanMessage` |
| `MessagesPlaceholder` | 聊天历史占位符 |
| `StoragePromptTemplate` | 可持久化表示，组合 `PromptTemplateIdentifier` |

**`PromptManager`**（L481）：
- `save()`：持久化到数据库
- `prefer_query()`：分层查询（精确匹配 prompt_name → 按语言过滤 → 按模型过滤）
- `query_or_save()`：原子化懒加载

**调试端点**（`api/endpoints.py`）：`POST /template/debug` 将变量格式化到提示模板中，流式输出 LLM 响应。

### 35.7 序列化系统

核心文件：`packages/dbgpt-core/src/dbgpt/core/interface/serialization.py`

| 类 | 角色 |
|-----|------|
| `Serializable` (ABC) | 序列化抽象基类，声明 `to_dict()`、`serialize()` |
| `Serializer` (ABC) | 序列化器抽象基类，声明 `serialize(obj)`、`deserialize(data, cls)` |
| `JsonSerializer` | JSON 序列化/反序列化，作为资源注册 |
| `JsonSerializable` (ABC) | 便捷基类：`serialize()` 自动 `json.dumps(self.to_dict())` |

**`EnhancedJSONEncoder`**（`util/json_utils.py` L19）：自定义 `json.JSONEncoder`，序列化 dataclass（`asdict`）、datetime、date、time。

**序列化检查**（`util/serialization/check.py` L75）：`check_serializable()` 使用 `cloudpickle.dumps()` 验证。`inspect_serializability()` 递归检查属性、闭包、非局部变量。

**存储序列化流**：`StorageInterface` 默认使用 `JsonSerializer`，数据以 `Serializable → to_dict() → json.dumps → bytes` 保存，加载时 `bytes → json.loads → cls(**dict)`。

***

## 36. Chat 请求全链路

本章追踪从用户发送 Chat 消息到 LLM 返回的完整端到端调用链路，覆盖 4 种 chat 模式。

### 36.1 Chat 入口分布

Chat 入口分布在三个 FastAPI router 文件中：

| 文件 | 路由 | 场景 |
|------|------|------|
| `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py` | `/v1/chat/completions`、`/v1/chat/db/*` | V1 入口 |
| `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py` | `/v1/chat/react-agent` | React Agent 入口 |
| `packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py` | `/v2/chat/completions` | V2 OpenAI 兼容入口 |

ChatScene 枚举定义在 [base.py:29-110](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/base.py#L29-L110)，关键值：
- `ChatWithDbExecute` → `"chat_with_db_execute"`
- `ChatDashboard` → `"chat_dashboard"`
- `ChatAgent` → `"chat_agent"`
- `ChatNormal` → `"chat_normal"`

### 36.2 模式 1: chat_react_agent

#### HTTP 入口

[agentic_data_api.py:4373-4407](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L4373-L4407) `chat_react_agent()`：

```python
@router.post("/v1/chat/react-agent")
async def chat_react_agent(dialogue: ConversationVo = Body(), ...):
    ...
    return StreamingResponse(_react_agent_stream(dialogue),
                              headers=headers, media_type="text/event-stream")
```

#### 端到端调用栈

1. **HTTP 入口**（[agentic_data_api.py:4374](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L4374)）：解析 `dialogue.ext_info`，提取 `file_path / skill_name / knowledge_space / database_name / connector_ids`（行 1020-1032），包装为 `StreamingResponse`

2. **流生成器**（[agentic_data_api.py:987](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L987)）`_react_agent_stream(dialogue)`：
   - **Step 1**（行 1213-1215）：`load_skills_from_dir(DEFAULT_SKILLS_DIR, recursive=True)` 预加载所有 skills
   - **Step 2**（行 1218-1227）：从 `get_resource_manager(CFG.SYSTEM_APP)` 获取业务工具
   - **Step 3**（行 1230-1260）：若 `knowledge_space` 存在，加载 `KnowledgeSpaceRetrieverResource`
   - **Step 4**（行 1263-1289）：若 `database_name` 存在，调用 **ConnectorManager** 获取 connector 并拼接 schema 上下文
     ```python
     local_db_manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
     database_connector = local_db_manager.get_connector(database_name)
     ```
   - **Connector 工具注入**（行 3186-3213）：`_select_connector_tools(connector_ids, _connector_manager)` 仅注入用户显式选择的 connector
   - **System prompt 注入**（行 3524-3601）：列出激活的 connector 工具写入 prompt
   - **Agent 构建**（行 3612-3621）：
     ```python
     agent_builder = (ReActAgent(max_retry_count=30)
         .bind(context).bind(agent_memory).bind(llm_config)
         .bind(tool_pack).bind(workflow_prompt_template))
     agent = await agent_builder.build()
     ```
   - **流式 queue 桥接**（行 3625-3648）：创建 `asyncio.Queue`，定义 `stream_callback` 把 agent 事件 push 到 queue；`agent_task = asyncio.create_task(run_agent())`

3. **ReActAgent 主循环**：[react_agent.py:96-268](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/expand/react_agent.py#L96-L268)
   - `ReActAgent` 继承 `ConversableAgent`，`run_mode = AgentRunMode.LOOP`（行 98），`max_retry_count=30`
   - `_init_actions([ReActAction, Terminate])`（行 126）
   - 重写 `act()`（行 231-267）：用 `ReActOutputParser.parse_current_step` 解析 LLM 输出，每次只允许一个 action

4. **generate_reply 主循环（LOOP 模式）**：[base_agent.py:436-736](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L436-L736)
   - **thinking 阶段**（行 546-609）：调用 `self.thinking(thinking_messages, sender, stream_callback=_llm_stream_callback)` → 通过 `_emit_stream("thinking_chunk", {...})` 推送增量
   - **review 阶段**（行 611-622）：`self.review(llm_reply, self)` — 默认实现返回 `(True, None)`（行 791-793）
   - **act 阶段**（行 630-659）：调用 `ReActAgent.act()` → `ConversableAgent.act()`（行 795-839） → `real_action.run(...)` 执行具体工具
   - **verify 阶段**（行 661-675）：`self.verify(reply_message, sender, reviewer)`
   - **循环终止**（行 704-706）：`if self.run_mode != AgentRunMode.LOOP or act_out.terminate: break`
   - **LLM 调用**（行 738-789）：`thinking()` → `self.llm_client.create(..., stream_callback=stream_callback)` — 自动重试 3 次

5. **LLM Client 流式输出**：[llm_client.py:190-250](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/util/llm/llm_client.py#L190-L250)
   - `LLMClient.create()` 接收 `stream_callback`，每个 token chunk 通过 `_emit_stream_callback` 回调

6. **SSE 事件循环**：[agentic_data_api.py:3702-4078](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L3702-L4078)
   - 主循环 `while True` 从 `stream_queue` 取事件（行 3702-3706）
   - 事件类型分发：
     - `context.status`（行 3711-3713）：上下文管理状态
     - `thinking`（行 3714-3747）：解析 `Thought/Action/Action Intention/Action Reason`，缓冲到 `pending_thoughts`
     - `thinking_chunk`（行 3749-3776）：流式思考增量，创建 "思考中" step
     - `act`（行 3778-4077）：核心 — 创建 step card，发射 `step.start`、`step.meta`、`step.chunk`（code/markdown/text/table/chart/json）、`step.done`
   - **特殊处理**：
     - `terminate` action（行 3801-3814）：跳过 step 显示，自动完成所有 todos
     - `todowrite` action（行 3817-3921）：发射 `plan.update` SSE 事件
     - `code_interpreter`（行 3996-4003）：把代码作为 `step.chunk` 类型 `code` 推送
   - **SSE 编码**：所有事件通过 `_sse_event(payload)` (行 983-984) 编码为 `data: {json}\n\n`

7. **终止点**（行 4079-4148）：
   - `reply = await agent_task`
   - 若 `reply.action_report.terminate`：从 `Action Input` 中提取 `result` 字段作为 `final_content`
   - 否则：取最后一步的 observation/thoughts 作为 final_content
   - 发射 `{"type": "final", "content": final_content}` 和 `{"type": "done"}` 事件
   - 失败路径（行 4081-4099）：捕获异常 → 存储错误到 `storage_conv` → 发射 `final` + `done`

#### 异常处理路径

- **HTTP 入口层**（行 4397-4407）：捕获异常返回 `error_text` StreamingResponse
- **agent_task 异常**（行 4081-4099）：写入 StorageConversation 后 yield error 事件
- **LLM `LLMChatError`** 含 `context_too_long`（[base_agent.py:572-596](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L572-L596)）：触发 `reactive_compact` 压缩上下文重新调用
- **thinking 重试** 3 次（[base_agent.py:757-784](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L757-L784)）

### 36.3 模式 2: chat_with_db_execute

#### HTTP 入口

[api_v1.py:526-642](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L526-L642) `chat_completions()`

#### 端到端调用栈

1. **HTTP 入口**（[api_v1.py:527](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L527)）`chat_completions(dialogue, flow_service, user_token)`：
   - 行 537：`dialogue = adapt_native_app_model(dialogue)` 适配原生 app model
   - 行 540-545：若 `chat_mode==ChatNormal` 且 `ext_info.knowledge_space` 存在，切换到 `ChatKnowledge` 模式
   - 行 553：`domain_type = _parse_domain_type(dialogue)` 解析知识库 domain_type

2. **分支选择**（行 554-622）：
   - `ChatAgent`（行 554-573）：转交 `multi_agents.app_agent_chat(...)` — 走 multi-agent Hub 路径
   - `ChatFlow`（行 574-592）：转交 `flow_service.chat_stream_flow_str(dialogue.select_param, flow_req)` — 走 AWEL Flow
   - `domain_type is not None`（行 593-598）：走 `chat_with_domain_flow(dialogue, domain_type)`（行 852-893）— 通过 DAGManager 加载知识库 domain DAG
   - **默认**（chat_with_db_execute 走此路径，行 600-622）：
     ```python
     chat: BaseChat = await get_chat_instance(dialogue)
     if not chat.prompt_template.stream_out:
         return StreamingResponse(no_stream_generator(...), media_type="text/event-stream")
     else:
         return StreamingResponse(stream_generator(chat, ...), media_type="text/plain")
     ```

3. **get_chat_instance**：[api_v1.py:469-505](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L469-L505)
   - 构建 `ChatParam`（行 484-497），`select_param=dialogue.select_param`（即 db_name）
   - `chat_mode=ChatScene.of_mode(dialogue.chat_mode)` → `ChatScene.ChatWithDbExecute`
   - 调用 `CHAT_FACTORY.get_implementation(dialogue.chat_mode, CFG.SYSTEM_APP, chat_param=chat_param)`

4. **ChatFactory**：[chat_factory.py:8-65](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_factory.py#L8-L65)
   - 行 48：`BaseChat.__subclasses__()` 找到所有子类
   - 行 51：匹配 `cls.chat_scene == chat_mode`
   - 行 56-62：调用 `parse_config` 解析 app config，实例化 `ChatWithDbAutoExecute(chat_param=chat_param, system_app=system_app)`

5. **ChatWithDbAutoExecute**：[chat.py:17-92](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_db/auto_execute/chat.py#L17-L92)
   - **`__init__`**（行 26-47）：
     - 行 35：`self.db_name = chat_param.select_param`
     - 行 45-46：`ConnectorManager.get_instance(self.system_app).get_connector(self.db_name)` → 缓存 30 分钟
   - **`generate_input_values`**（行 49-88）：
     - 行 59：`client = DBSummaryClient(system_app=self.system_app)`
     - 行 62-68：`client.get_db_summary(self.db_name, user_input, self.curr_config.schema_retrieve_top_k)` — 检索相关表 schema
     - 行 69-78：失败 fallback 到 `self.database.table_simple_info` 并按 `schema_max_tokens` 截断
   - **`do_action`**（行 90-92）：`return self.database.run_to_df` — 返回可执行函数（实际执行由 prompt output_parser 触发）

6. **stream_call**：[base_chat.py:408-527](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/base_chat.py#L408-L527)
   - 行 412：`payload = await self._build_model_request()` → 调用 `generate_input_values` 填充 prompt
   - 行 426：`async for output in self.call_streaming_operator(payload):`
   - 行 430-434：`self.prompt_template.output_parser.parse_model_stream_resp_ex(output, text_output=False)` 解析流式响应
   - 行 486-488：`_handle_final_output` 调用 `do_action(prompt_response)` 执行 SQL → `parse_view_response` 渲染视图
   - 行 505-507：`add_ai_message` / `add_view_message` 持久化

7. **stream_generator**：[api_v1.py:737-820](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L737-L820)
   - 行 767-769：`async for chunk in chat.stream_call(text_output=text_output, incremental=incremental):`
   - 行 774-811：openai 格式包装为 `ChatCompletionStreamResponse` → `data: {json}\n\n`
   - 行 814：末尾发射 `data: [DONE]\n\n`

8. **终止点**：[api_v1.py:815](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L815) `span.end()` 或行 816-820 异常路径 `data: [SERVER_ERROR]...`

#### 与 react-agent 路径的区别

| 维度 | chat_with_db_execute | chat_react_agent |
|------|---------------------|------------------|
| 入口文件 | `api_v1.py:527` | `agentic_data_api.py:4373` |
| 实现类 | `ChatWithDbAutoExecute` (BaseChat 子类) | `ReActAgent` (ConversableAgent 子类) |
| 控制流 | 单轮 LLM 调用 + 1 次 do_action | LOOP 模式，最多 30 轮 thinking→act→verify |
| 工具调用 | SQL 直接执行（`database.run_to_df`） | 通过 ToolPack 注册的工具（sql_query、code_interpreter 等） |
| 流式格式 | OpenAI 兼容 `data: {json}\n\n` + `[DONE]` | 自定义 SSE：`step.start/chunk/meta/done` + `final` + `done` |
| Connector 获取 | `__init__` 中 `ConnectorManager.get_connector(db_name)` | 若 `ext_info.database_name` 存在才获取；同时通过 `_select_connector_tools` 注入 MCP connector 工具 |
| Schema 检索 | `DBSummaryClient.get_db_summary` 在 `generate_input_values` 中调用 | 不调用 DBSummaryClient；直接用 `connector.get_table_info_no_throw` 拼接到 prompt |

### 36.4 模式 3: dashboard

注意：DB-GPT 没有独立的 `/v1/chat/dashboard` 路由，dashboard 模式通过 `/v1/chat/completions` 路由传入 `chat_mode=chat_dashboard` 进入。

#### 端到端调用栈

1. **HTTP 入口**：[api_v1.py:527](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L527) `chat_completions()` — 走默认分支（行 600-622）

2. **ChatDashboard**：[chat.py:23-128](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_dashboard/chat.py#L23-L128)
   - **`__init__`**（行 32-51）：
     - 行 41：`self.db_name = chat_param.select_param`
     - 行 47-48：`ConnectorManager.get_instance(self.system_app).get_connector(self.db_name)`
     - 行 49：`self.curr_config = chat_param.real_app_config(ChatDashboardConfig)`
     - 行 51：`self.dashboard_template = self.__load_dashboard_template("report")` — 从 `template/report/dashboard.json` 加载支持的图表类型
   - **`generate_input_values`**（行 62-98）：
     - 行 70：`client = DBSummaryClient(system_app=self.system_app)`
     - 行 72-78：`client.get_db_summary(self.db_name, user_input, self.curr_config.schema_retrieve_top_k)` 检索相关表
     - 行 80-89：失败 fallback 到 `self.database.table_simple_info` 并按 `schema_max_tokens` 截断
     - 返回 `input / dialect / table_info / supported_chat_type`
   - **`do_action`**（行 100-128）：
     - 行 104：`DashboardDataLoader()` 实例化
     - 行 105-120：遍历 `prompt_response`（LLM 生成的 ChartItem 列表）
     - 行 107-108：`dashboard_data_loader.get_chart_values_by_conn(self.database, chart_item.sql)` 执行每个 SQL 获取数据
     - 行 110-119：构造 `ChartData(chart_uid, chart_name, chart_type, chart_desc, chart_sql, column_name, values)`
     - 行 123-128：返回 `ReportData(conv_uid, template_name, charts=chart_datas)`

3. **图表配置生成**：
   - LLM 通过 prompt（[prompt.py:72-75](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_dashboard/prompt.py#L72-L75)，`stream_out=True`，`output_parser=ChatDashboardOutputParser()`）输出 `List[ChartItem]`
   - `ChartItem` 定义在 [dashboard_action.py:17-36](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/expand/actions/dashboard_action.py#L17-L36)，包含 `title / display_type / sql / thought`
   - **可用的 display_type**：从 `dashboard_template["supported_chart_type"]` 读取

### 36.5 模式 4: chat_data

`chat_data` 是 V2 API 的别名，实际会被映射到 `ChatWithDbExecute` scene。

#### HTTP 入口

[api_v2.py:71-167](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L71-L167) `chat_completions()`

#### 端到端调用栈

1. **HTTP 入口**（[api_v2.py:72](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L72)）`chat_completions(request, service)`
   - 行 93：`check_chat_request(request)` — 校验 `chat_param / model / messages`（行 315-359）
   - 行 94-95：若 `conv_uid is None`，生成 UUID
   - 行 125-132：判断 chat_mode ∈ {`CHAT_NORMAL`, `CHAT_KNOWLEDGE`, `CHAT_DATA`, `CHAT_DB_QA`, `CHAT_DASHBOARD`} 走默认路径

2. **get_chat_instance（V2 版本）**：[api_v2.py:170-210](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L170-L210)
   - **行 187-188**：
     ```python
     if dialogue.chat_mode == "chat_data":
         dialogue.chat_mode = ChatScene.ChatWithDbExecute.value()
     ```
   - 行 197：`select_param=dialogue.chat_param` — db_name 通过 chat_param 传入
   - 行 203-209：`CHAT_FACTORY.get_implementation(dialogue.chat_mode, system_app, chat_param=chat_param)` — 后续走 `ChatWithDbAutoExecute`（同模式 2）

3. **流式/非流式分支**（[api_v2.py:140-154](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L140-L154)）：
   - 非流式：`no_stream_wrapper(request, chat)` (行 213-232) → `chat.nostream_call()` → 包装为 `ChatCompletionResponse`
   - 流式：`stream_generator(chat, request.incremental, request.model, text_output=False, openai_format=True)` (行 144-154) — 调用 V1 的 `stream_generator`（`api_v1.py:737`），media_type=`text/event-stream`

### 36.6 流式输出实现

#### 三种流式格式

1. **V1 chat_completions 默认流式**（[api_v1.py:613-622, 737-820](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L613-L622)）
   - media_type=`text/plain`
   - 通过 `stream_generator` 包装为 OpenAI 兼容格式：`data: {json: ChatCompletionStreamResponse}\n\n` + `data: [DONE]\n\n`
   - 每个 chunk 是 `ModelOutput`，通过 `output.has_text / has_thinking` 分离正文与思考

2. **V2 chat_completions 流式**（[api_v2.py:144-154](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L144-L154)）
   - media_type=`text/event-stream`
   - 复用 V1 的 `stream_generator`，但强制 `text_output=False, openai_format=True`

3. **React Agent 流式**（[agentic_data_api.py:987, 3702-4078](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L987)）
   - media_type=`text/event-stream`
   - 自定义 SSE 事件协议（`_sse_event` 编码 `data: {json}\n\n`）：
     - `step.start / step.chunk / step.meta / step.done` — 步骤卡片
     - `plan.update` — todo 列表更新
     - `context.status` — 上下文管理状态
     - `thinking / thinking_chunk` — LLM 思考增量（内部缓冲，不直接发射）
     - `final` — 最终答案
     - `done` — 终止信号
   - 实现机制：`asyncio.Queue` 桥接 — agent 在 `asyncio.create_task` 中运行，通过 `stream_callback` 把事件 push 到 queue，主循环从 queue 取事件 yield

#### 底层 LLM 流式

- `BaseChat.stream_call`（[base_chat.py:408-527](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/base_chat.py#L408-L527)）：通过 `call_streaming_operator` → `build_cached_chat_operator(self.llm_client, True, ...)` → `LLMClient.create(stream_callback=...)`
- `ConversableAgent.thinking`（[base_agent.py:738-789](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L738-L789)）：`self.llm_client.create(..., stream_callback=stream_callback)` — 同样走 LLMClient
- `LLMClient.create`（[llm_client.py:190-250](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/util/llm/llm_client.py#L190-L250)）：每个 token 通过 `_emit_stream_callback` 回调上层

### 36.7 ConnectorManager / DBSummaryClient 调用点

#### ConnectorManager 调用点

| 调用点 | 文件:行号 | 用途 |
|--------|----------|------|
| ChatDashboard.__init__ | [chat_dashboard/chat.py:47-48](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_dashboard/chat.py#L47-L48) | 获取 db connector 用于执行图表 SQL |
| ChatWithDbAutoExecute.__init__ | [chat_db/auto_execute/chat.py:45-46](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_db/auto_execute/chat.py#L45-L46) | 获取 db connector 用于执行 SQL |
| _react_agent_stream Step 4 | [agentic_data_api.py:1267-1268](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L1267-L1268) | 若 `database_name` 存在，获取 connector 拼接 schema 上下文 |
| _react_agent_stream connector 工具注入 | [agentic_data_api.py:3186-3213](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L3186-L3213) | 通过 `_select_connector_tools` 注入用户选择的 MCP connector 工具包 |
| _react_agent_stream system prompt 注入 | [agentic_data_api.py:3524-3601](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L3524-L3601) | 列出激活 connector 的工具描述写入 prompt |
| execute_tool 内部 fallback | [agentic_data_api.py:1676-1681](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L1676-L1681) | 当 ResourceManager 未注册工具时，从 ConnectorManager active packs 查找 |

#### DBSummaryClient 调用点

| 调用点 | 文件:行号 | 用途 |
|--------|----------|------|
| ChatDashboard.generate_input_values | [chat_dashboard/chat.py:70-78](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_dashboard/chat.py#L70-L78) | 检索与用户输入相关的表 schema |
| ChatWithDbAutoExecute.generate_input_values | [chat_db/auto_execute/chat.py:59-68](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_db/auto_execute/chat.py#L59-L68) | 检索与用户输入相关的表 schema |
| ConnectorManager._trigger_schema_embedding | [connector_manager.py:264-296](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L264-L296) | 检测到 schema 变化时异步刷新向量库 |
| async_db_summary_embedding | [api_v1.py:231-233](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L231-L233) | `/v1/chat/db/summary` 接口触发 |

#### DBSummaryClient.get_db_summary

[db_summary_client.py:98-114](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/db_summary_client.py#L98-L114)：
- 行 102-104：`_get_vector_connector_by_db(dbname)` 获取表/字段向量连接器
- 行 105-110：`DBSchemaRetriever(top_k=topk, ...)` 实例化检索器
- 行 112-114：`retriever.retrieve(query)` → 返回相关表的 content 列表

### 36.8 异常处理路径汇总

#### HTTP 入口层
- **chat_completions**（[api_v1.py:623-633](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L623-L633)）：捕获异常 → 返回 `StreamingResponse(error_text(str(e)), media_type="text/plain")`
- **chat_react_agent**（[agentic_data_api.py:4397-4407](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L4397-L4407)）：同上
- **V2 chat_completions**（[api_v2.py:156-167](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L156-L167)）：抛 `HTTPException(status_code=400)` with OpenAI 风格 error 结构

#### 流生成器层
- **stream_generator**（[api_v1.py:816-820](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L816-L820)）：捕获异常 → `yield f"data: [SERVER_ERROR]{str(e)}\n\n"` + `data: [DONE]\n\n`
- **BaseChat.stream_call**（[base_chat.py:509-524](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/base_chat.py#L509-L524)）：捕获异常 → yield `ModelOutput.build(str(e), error_code=-1)` 或 HTML 错误视图

#### Agent 层
- **generate_reply**（[base_agent.py:728-736](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L728-L736)）：捕获异常 → 返回 `AgentMessage(content=str(e), success=False)`
- **thinking**（[base_agent.py:757-789](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L757-L789)）：`LLMChatError` 重试 3 次，每次间隔 10s；最终抛 `ValueError(last_err)`
- **LLM context overflow**（[base_agent.py:572-596](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/agent/core/base_agent.py#L572-L596)）：检测 `context_too_long / context_length_exceeded / maximum context length` → 调用 `_ctx_mgr.reactive_compact` 压缩上下文重试

#### ConnectorManager 异常处理
- **`_trigger_schema_embedding`**（[connector_manager.py:264-296](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L264-L296)）：best-effort，失败仅 warning 不传播
- **`invalidate_connector` / `clear_connector_cache`**（行 298-319）：`_dispose_connector` 失败仅 debug 日志

#### DBSummaryClient 失败 fallback
- [chat_dashboard/chat.py:80-89](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_dashboard/chat.py#L80-L89) 和 [chat_db/auto_execute/chat.py:69-78](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/scene/chat_db/auto_execute/chat.py#L69-L78)：`get_db_summary` 失败时 fallback 到 `self.database.table_simple_info` 并按 `schema_max_tokens` 截断

### 36.9 4 种模式对照表

| 模式 | HTTP 入口 | 实现 类 | 调用链关键节点 | 终止点 |
|------|----------|--------|--------------|-------|
| **chat_react_agent** | [agentic_data_api.py:4373](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L4373) `chat_react_agent` | `ReActAgent` (LOOP) | `chat_react_agent` → `_react_agent_stream` → `ReActAgent.build` → `agent.generate_reply` (循环 thinking→act→verify) → `stream_callback` → SSE queue → `data: {final}\n\n` + `data: {done}\n\n` | [agentic_data_api.py:4101-4148](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py#L4101-L4148) 发射 `final` + `done` |
| **chat_with_db_execute** | [api_v1.py:526](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L526) `chat_completions` (默认分支) | `ChatWithDbAutoExecute` | `chat_completions` → `get_chat_instance` → `ChatFactory.get_implementation` → `ChatWithDbAutoExecute.__init__`(ConnectorManager) → `stream_generator` → `BaseChat.stream_call` → `generate_input_values`(DBSummaryClient) → `call_streaming_operator` → `do_action`(database.run_to_df) | [api_v1.py:814](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L814) `data: [DONE]\n\n` |
| **dashboard** | [api_v1.py:526](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L526) `chat_completions` (chat_mode=chat_dashboard) | `ChatDashboard` | `chat_completions` → `get_chat_instance` → `ChatDashboard.__init__`(ConnectorManager) → `stream_generator` → `BaseChat.stream_call` → `generate_input_values`(DBSummaryClient) → `do_action`(DashboardDataLoader.get_chart_values_by_conn) → `ReportData` | [api_v1.py:814](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L814) `data: [DONE]\n\n` |
| **chat_data** | [api_v2.py:71](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v2.py#L71) `chat_completions` (V2) | `ChatWithDbAutoExecute`（映射自 chat_data） | `chat_completions` → `check_chat_request` → `get_chat_instance`(映射 chat_data→chat_with_db_execute) → `ChatFactory.get_implementation` → `ChatWithDbAutoExecute` → `stream_generator` / `no_stream_wrapper` | 流式: `data: [DONE]\n\n`；非流式: `ChatCompletionResponse` JSON |

***

## 37. 数据库连接配置全流程

本章追踪从前端"新增数据库"到 `connect_config` 表写入、ConnectorManager 动态选择 connector、测试连接及错误返回的完整端到端流程。

### 37.1 两套并行的 API 体系

仓库中存在两套并行的数据库连接 API：

| API 体系 | 路由前缀 | 入口文件 | Service 层 | 当前状态 |
|---|---|---|---|---|
| **旧 API（v1）** | `/api/v1/chat/db/*` | [api_v1.py:192-246](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L192-L246) | 走 `CFG.local_db_manager`（调用 `ConnectorManager` 已 `@Deprecated` 的 `add_db`/`edit_db`/`test_connect` 方法） | 已废弃，仍可路由 |
| **新 API（v2，Serve 层）** | `/api/v2/serve/datasources/*` | [endpoints.py](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py) | `Service`（[service.py](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py)）+ `ConnectorManager` | **前端实际使用** |

**前端实际调用的是新 API（v2 Serve 层）**，证据见 `web/client/api/request.ts:82-101`：
- `GET /api/v2/serve/datasources` → 列表
- `POST /api/v2/serve/datasources` → 新增
- `PUT /api/v2/serve/datasources` → 编辑
- `POST /api/v2/serve/datasources/test-connection` → 测试
- `DELETE /api/v2/serve/datasources/{id}` → 删除
- `POST /api/v2/serve/datasources/{id}/refresh` → 刷新
- `GET /api/v2/serve/datasource-types` → 支持类型

### 37.2 前端发起

#### 前端页面组件

**主页面**：`web/pages/construct/database.tsx`
- 列表展示：`getDbList()`（第 50 行）→ 渲染数据库卡片
- 支持类型：`getDbSupportType()`（第 44 行）→ `GET /api/v2/serve/datasource-types`
- 点击"Add Datasource"按钮（第 169-180 行）打开模态框 `FormDialog`
- 编辑/删除/刷新操作分别调用 `postDbEdit`/`postDbDelete`/`postDbRefresh`

**表单组件**：`web/components/database/database-form.tsx`
- 关键提交逻辑 `handleSubmit`（第 66-108 行）：
  1. 组装请求数据 `{ type: selectedType, params: values, description, id? }`
  2. **先调用测试连接** `postDbTestConnect(data)`（第 93 行）→ 若失败直接 return
  3. 测试通过后再调用 `postDbAdd(data)` 或 `postDbEdit(data)`（第 95 行）
- 表单字段动态渲染：通过 `ConfigurableForm`（第 133 行）根据 `dbTypeList[...].parameters` 动态生成，参数定义来自后端 `/datasource-types` 接口

#### 请求体格式

新增/编辑/测试共用同一格式（`DatasourceCreateRequest`，定义于 [schemas.py:59-92](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/schemas.py#L59-L92)）：

```json
{
  "type": "mysql",           // db_type，必填
  "params": {                // 动态参数，键名匹配 param_cls 的字段
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "xxx",
    "database": "test"
  },
  "description": "可选描述",
  "id": 123                  // 仅编辑时传入
}
```

### 37.3 API 层处理（新 API v2）

#### 路由注册链

1. `packages/dbgpt-app/src/dbgpt_app/initialization/serve_initialization.py:182-193` 注册 `DatasourceServe`
2. [serve.py:30](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/serve.py#L30) 定义 `api_prefix = "/api/v2/serve"`
3. `serve.py:47-48` 执行 `app.include_router(router, prefix=self._api_prefix, ...)`，最终路径为 `/api/v2/serve/datasources`
4. `serve.py:53` 调用 `init_endpoints(system_app, config)`，在 [endpoints.py:271-275](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py#L271-L275) 中注册 `Service` 组件到 `SystemApp`

#### 端点函数

入口文件：[endpoints.py](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py)

| 端点 | 行号 | 调用 Service 方法 |
|---|---|---|
| `POST /datasources`（create） | 99-118 | `service.create(request)` |
| `PUT /datasources`（update） | 121-139 | `service.update(request)` |
| `DELETE /datasources/{id}` | 142-159 | `service.delete(datasource_id)` |
| `GET /datasources/{id}` | 162-179 | `service.get(datasource_id)` |
| `GET /datasources`（list） | 182-203 | `service.get_list(db_type)` |
| `GET /datasource-types` | 206-216 | `service.datasource_types()` |
| `POST /datasources/test-connection` | 219-242 | `service.test_connection(request)` |
| `POST /datasources/{id}/refresh` | 245-268 | `service.refresh(datasource_id)` |

所有端点都通过 `blocking_func_to_async(global_system_app, service.xxx, ...)`（[endpoints.py:117](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py#L117) 等）将同步 Service 方法包装为异步执行。`check_api_key`（第 47-84 行）做 Bearer Token 鉴权（若配置了 `api_keys`）。

### 37.4 Serve 层处理

#### Service.create（新增，写入 connect_config 表）

文件：[service.py:101-163](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L101-L163)

完整调用栈：

1. **入口** `Service.create(request)`（[service.py:101](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L101)）
2. **构建参数对象**（[service.py:121-123](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L121-L123)）：
   ```python
   connector_params: BaseDatasourceParameters = self.datasource_manager._create_parameters(request)
   ```
   调用 `ConnectorManager._create_parameters`（[connector_manager.py:419-432](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L419-L432)）：
   - `DBType.of_db_type(request.type)` 校验类型（[schema.py:47-60](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/schema.py#L47-L60)）
   - `self._supported_types()[db_type.value()]` 拿到 connector 类
   - `cls.param_class().from_dict(request.params, ignore_extra_fields=True)` 构造参数对象
3. **提取持久化状态**（[service.py:124](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L124)）：
   ```python
   persisted_state = connector_params.persisted_state()
   ```
   `BaseDatasourceParameters.persisted_state()`（[parameter.py:52-75](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/parameter.py#L52-L75)）将参数字段映射到表列：
   - `host` → `db_host`、`port` → `db_port`、`user` → `db_user`、`password` → `db_pwd`、`database` → `db_name`、`path` → `db_path`（映射表见 [parameter.py:78-91](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/parameter.py#L78-L91) 的 `_persisted_state_mapping`）
   - 未映射字段塞入 `ext_config`（dict）
   - 文件型 DB（SQLite/DuckDB/Spark）若 `db_name` 为空，从 `db_path` 解析：`{db_type}_{basename}`（[parameter.py:68-74](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/parameter.py#L68-L74)）
4. **处理 ext_config**（[service.py:129-134](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L129-L134)）：dict → JSON 字符串
5. **重名校验**（[service.py:137-142](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L137-L142)）：`self._dao.get_by_names(db_name)`，存在则抛 `HTTPException(400)`
6. **二次校验 db_type**（[service.py:144-148](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L144-L148)）：`DBType.of_db_type(str_db_type)`
7. **写入 connect_config 表**（[service.py:150](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L150)）：
   ```python
   res = self._dao.create(persisted_state)
   ```
   - `self._dao` 是 `ConnectConfigDao`（[service.py:64](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L64) 初始化）
   - `ConnectConfigDao` 继承 `BaseDao`（[connect_config_db.py:58](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connect_config_db.py#L58)），`create` 由 `BaseDao` 提供，将 dict 转为 `ConnectConfigEntity` 并 ORM 插入
8. **异步触发向量库嵌入**（[service.py:152-160](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L152-L160)）：通过 `ExecutorFactory` 提交 `self._db_summary_client.db_summary_embedding(db_name, str_db_type)` 到后台线程
9. **返回** `_to_query_response(res)`（[service.py:163](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L163)，见第 264-278 行）：将 entity 转回 `DatasourceQueryResponse`

#### ConnectConfigEntity（connect_config 表结构）

文件：[connect_config_db.py:28-55](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connect_config_db.py#L28-L55)

表名 `connect_config`，字段：
- `id`（PK，自增）
- `db_type`（String 255，非空）
- `db_name`（String 255，非空，**唯一约束 `uk_db`**）
- `db_path`（String 255，文件型 DB 路径）
- `db_host`/`db_port`/`db_user`/`db_pwd`（非文件型连接信息）
- `comment`（Text，描述）
- `sys_code`/`user_id`/`user_name`（索引）
- `gmt_created`/`gmt_modified`（DateTime）
- `ext_config`（Text，JSON 字符串，存放 schema/service_name/zooKeeperNamespace 等扩展字段）
- 索引：`idx_q_db_type`

#### Service 其他方法

- **update**（[service.py:165-214](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L165-L214)）：与 create 类似，构建 `persisted_state` → `self._dao.update({"id": datasources.id}, persisted_state)` → **关键**：`self.datasource_manager.invalidate_connector(db_name)`（第 213 行）使缓存失效
- **delete**（[service.py:230-247](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L230-L247)）：`self._dao.delete({"id": datasource_id})` + `invalidate_connector` + 删除向量库 profile
- **test_connection**（[service.py:288-297](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L288-L297)）：直接委托 `self.datasource_manager.test_connection(request)`
- **refresh**（[service.py:299-325](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L299-L325)）：删除 profile + `invalidate_connector` + 重新嵌入
- **get_list**（[service.py:249-262](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L249-L262)）：`self.dao.get_list(query_request)` 逐条转 response

### 37.5 ConnectorManager 构建

文件：[connector_manager.py](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py)

#### 组件注册

- `component_configs.py:26-38`：`system_app.register(ConnectorManager)`，作为 `BaseComponent` 注册到 `SystemApp`
- `component_configs.py:232-249` 另注册了一个**外部** `ExternalConnectorManager`（来自 `dbgpt.agent.resource.connector.manager`），用于 MCP-based connectors，**与 SQL datasource 的 ConnectorManager 是分开的两个组件**
- `ConnectorManager.on_init`（第 66-112 行）导入所有 connector 类（`RDBMSConnector` + 各具体子类），触发 `__subclasses__()` 注册

#### 根据 db_type 动态选择 connector 类

核心方法：`_supported_types`（[connector_manager.py:174-183](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L174-L183)）

```python
def _supported_types(self) -> Dict[str, Type[BaseConnector]]:
    chat_classes = self._get_all_subclasses(BaseConnector)  # 递归 __subclasses__()
    support_types = {}
    for cls in chat_classes:
        if cls.db_type and cls.is_normal_type():   # 排除图数据库
            db_type = DBType.of_db_type(cls.db_type)
            if db_type:
                support_types[db_type.value()] = cls
    return support_types
```

**选择机制要点**：
1. 通过 `BaseConnector.__subclasses__()` 递归发现所有已导入的子类
2. **过滤条件 1**：`cls.db_type` 非空（抽象基类 `db_type = "__abstract__db_type__"`，被排除）
3. **过滤条件 2**：`cls.is_normal_type()` 返回 True（Neo4j/TuGraph `is_graph_type()` 返回 True，被排除）
4. **过滤条件 3**：`DBType.of_db_type(cls.db_type)` 能匹配上枚举（[schema.py:17-37](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/schema.py#L17-L37) 的 18 种类型）

#### db_type → connector 类映射表

| db_type | Connector 类 | 文件 | param_cls | 是否文件型 |
|---|---|---|---|---|
| mysql | `MySQLConnector` | [conn_mysql.py:40](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_mysql.py#L40) | `MySQLParameters` | 否 |
| postgresql | `PostgreSQLConnector` | `conn_postgresql.py` | `PostgreSQLParameters` | 否 |
| sqlite | `SQLiteConnector` | `conn_sqlite.py` | `SQLiteParameters` | 是 |
| duckdb | `DuckDbConnector` | [conn_duckdb.py:46](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_duckdb.py#L46) | `DuckDbConnectorParameters` | 是 |
| spark | `SparkConnector` | [conn_spark.py:46](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_spark.py#L46) | `SparkParameters` | 是 |
| oracle | `OracleConnector` | `conn_oracle.py` | `OracleParameters` | 否 |
| mssql | `MSSQLConnector` | `conn_mssql.py` | `MSSQLParameters` | 否 |
| clickhouse | `ClickhouseConnector` | `conn_clickhouse.py` | — | 否 |
| doris | `DorisConnector` | `conn_doris.py` | — | 否 |
| starrocks | `StarRocksConnector` | `conn_starrocks.py` | — | 否 |
| vertica | `VerticaConnector` | `conn_vertica.py` | — | 否 |
| hive | `HiveConnector` | [conn_hive.py:113](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_hive.py#L113) | `HiveParameters` | 否 |
| **kyuubi** | `KyuubiConnector` | [conn_kyuubi.py:456](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_kyuubi.py#L456) | `KyuubiParameters`（继承 `HiveParameters`） | 否 |
| gaussdb | `GaussDBConnector` | `conn_gaussdb.py` | — | 否 |
| openGauss | `openGaussConnector` | `conn_openGauss.py` | — | 否 |
| oceanbase | `OceanBaseConnector` | `conn_oceanbase.py` | — | 否 |
| neo4j | `Neo4jConnector` | [conn_neo4j.py:61](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/graphdb/conn_neo4j.py#L61) | — | 否（**is_graph_type，被排除**） |
| tugraph | `TuGraphConnector` | [conn_tugraph.py:61](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/graphdb/conn_tugraph.py#L61) | — | 否（**is_graph_type，被排除**） |

**param_cls 与 connector 的关联**：每个 connector 类通过 `@classmethod param_class()` 返回其配对的参数类（如 `MySQLConnector.param_class()` → `MySQLParameters`，[conn_mysql.py:49-51](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_mysql.py#L49-L51)）。参数类用 `@auto_register_resource` 装饰，通过 `RegisterParameters` + `PolymorphicMeta` 元类注册到 `_type_registry`，类型值由 `__type__` 属性决定（如 `MySQLParameters.__type__ = "mysql"`）。

#### get_connector 与 30 分钟缓存 TTL

核心方法：[connector_manager.py:196-262](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L196-L262)

**TTL 常量**：`_CONNECTOR_CACHE_DEFAULT_TTL = 1800`（第 41 行，30 分钟）

**缓存数据结构**：
- `self._connector_cache: Dict[str, Tuple[float, BaseConnector]]`（第 52 行）：`db_name → (created_at_unix_ts, connector)`
- `self._connector_cache_lock: threading.Lock`（第 53 行）：保护 dict 的全局锁
- `self._connector_creation_locks: Dict[str, threading.Lock]`（第 57 行）：**每 db_name 一把锁**，防止并发冷启动时多次反射

**完整流程**（[get_connector](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L196-L262)）：

1. **第一次检查（无锁快路径）**（第 221-225 行）：`with _connector_cache_lock` 读 cache，若存在且 `now - cached[0] < ttl`，直接返回
2. **获取创建锁**（第 227 行）：`creation_lock = self._get_connector_creation_lock(db_name)`（第 321-327 行，每 db_name 一把锁）
3. **双重检查锁定**（第 228-234 行）：进入创建锁后再次检查 cache（防止等锁期间其他线程已填充）
4. **快照旧表名集合**（第 236-247 行）：`with _connector_cache_lock` 取出旧 connector，调用 `cached[1].get_table_names()` 记录 `prev_tables`（用于 schema 变更检测）
5. **构建新 connector**（第 249 行）：`connector = self._build_connector(db_name)`
6. **写入缓存**（第 250-251 行）：`self._connector_cache[db_name] = (time.time(), connector)`
7. **Schema 变更检测**（第 253-261 行）：若 `prev_tables` 非空，取新 connector 的 `get_table_names()`，与 `prev_tables` 比较集合；**不同则触发** `self._trigger_schema_embedding(db_name)`
8. 返回 connector

**注释中明确的设计动机**（第 36-41、198-216 行）：`RDBMSConnector.__init__` 调用 `MetaData.reflect(bind=engine)`（[base.py:166](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/datasource/rdbms/base.py#L166)），对大 schema（如 900 表的 MSSQL）要 60s+，缓存后只有冷启动或 TTL 过期才慢。

#### _build_connector（根据 db_type 分支构建）

文件：[connector_manager.py:344-417](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L344-L417)

分支逻辑：
1. **读取配置**（第 351 行）：`db_config = self.storage.get_db_config(db_name)`（[connect_config_db.py:202](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connect_config_db.py#L202)）
2. **密码环境变量解析**（第 353-355 行）：`_resolve_env_vars(pwd)`（支持 `${ENV_VAR}` / `${ENV_VAR:-default}` 语法）
3. **校验 db_type**（第 357-359 行）：`DBType.of_db_type`
4. **获取 connector 类**（第 360 行）：`connect_instance = self.get_cls_by_dbtype(db_type.value())`（第 185-194 行，遍历子类匹配 `db_type`）
5. **文件型 DB 分支**（第 361-363 行）：`is_file_db()` → `connect_instance.from_file_path(db_path)`（SQLite/DuckDB/Spark）
6. **Oracle 特殊分支**（第 364-376 行）：从 `ext_config` 解析 `service_name`/`sid`，调用 `from_uri_db(host, port, user, pwd, service_name)`
7. **Kyuubi ZooKeeper 特殊分支**（第 396-408 行）：当 `db_type == "kyuubi"` 且 host 含逗号（ZK 多节点）时，走 `param_cls.from_persisted_state(parsed_config)` + `param.create_connector()`，因为 plain `from_uri_db` 无法解析 ZK URL
8. **默认分支**（第 410-417 行）：解析 `ext_config` 中的 `schema`，调用 `connect_instance.from_uri_db(host, port, user, pwd, db_name, schema)`

**`from_uri_db` 实现**（[base.py:182-205](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/datasource/rdbms/base.py#L182-L205)）：
```python
db_url = f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{port}/{db_name}"
return cls.from_uri(db_url, engine_args, **kwargs)
```
最终 `from_uri`（第 208-213 行）调用 `create_engine(database_uri, **_engine_args)` 构造 SQLAlchemy engine，传入 `RDBMSConnector.__init__`，在其中执行 `MetaData.reflect(bind=self._engine)`（第 166 行）。

#### Schema 变更检测（新加机制）

`_trigger_schema_embedding`（[connector_manager.py:264-296](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L264-L296)）：
1. 从 `self.storage.get_db_config(db_name)` 读 `db_type`
2. 通过 `ExecutorFactory` 提交 `self.db_summary_client.db_summary_embedding(db_name, db_type)` 到后台
3. **Best-effort**：失败只 log warning 不抛异常（第 291-296 行），避免影响触发它的 chat 请求

`db_summary_embedding`（[db_summary_client.py:69-96](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/db_summary_client.py#L69-L96)）：
- 通过 `_get_db_index_lock(dbname)` 做**per-db 串行化**（`lock.acquire(blocking=False)`，获取不到说明已有进行中的嵌入，跳过避免竞态）
- 调用 `DBSchemaAssembler`（`dbgpt_ext/rag/assembler/db_schema`）将表/字段信息写入向量库（chroma），供 `DBSchemaRetriever` 检索

#### 缓存失效

`invalidate_connector(db_name)`（[connector_manager.py:298-311](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L298-L311)）：
- `self._connector_cache.pop(db_name, None)`
- 调用 `_dispose_connector`（第 329-342 行）尝试 `engine.dispose()` 释放 SQLAlchemy 连接池
- **被以下场景调用**：
  - `Service.update`（[service.py:213](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L213)）—— 编辑后
  - `Service.delete`（[service.py:246](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L246)）—— 删除后
  - `Service.refresh`（[service.py:315](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L315)）—— 刷新前

`clear_connector_cache`（第 313-319 行）：清空全部缓存（测试/关闭用）。

### 37.6 测试连接端到端流程

#### 调用栈

1. **前端** `database-form.tsx:93`：`apiInterceptors(postDbTestConnect(data))`
2. **前端 API** `request.ts:97-98`：`POST /api/v2/serve/datasources/test-connection`
3. **路由** [endpoints.py:224-242](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py#L224-L242)：`test_connection(request, service)`
4. **异步包装** [endpoints.py:239-241](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py#L239-L241)：`blocking_func_to_async(global_system_app, service.test_connection, request)`
5. **Service 层** [service.py:288-297](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L288-L297)：`return self.datasource_manager.test_connection(request)`
6. **ConnectorManager** [connector_manager.py:490-518](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L490-L518)：`test_connection(request)`

#### ConnectorManager.test_connection 实现

文件：[connector_manager.py:490-518](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L490-L518)

```python
def test_connection(self, request: DatasourceCreateRequest) -> bool:
    try:
        pwd = request.params.get("password")
        if pwd:
            request.params["password"] = _resolve_env_vars(pwd)  # 环境变量解析
        param = self._create_parameters(request)   # 构造 BaseDatasourceParameters
        _connector = self.create_connector(param)  # 实际创建 connector
        return True
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Test connection Failure!{str(e)}\n{tb}")
        raise ValueError(f"Test connection Failure!{str(e)}")
```

**实际建立连接的路径**：
- `create_connector(param)`（第 442-444 行）→ `param.create_connector()`
- 每个 `XXXParameters.create_connector()` 调用 `XXXConnector.from_parameters(self)`
- `from_parameters` 调用 `cls.from_uri(parameters.db_url(), engine_args=parameters.engine_args())`
- `from_uri` 调用 `create_engine(database_uri, **_engine_args)` + `cls(engine, **kwargs)`
- `RDBMSConnector.__init__`（[base.py:117-168](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/datasource/rdbms/base.py#L117-L168)）执行 `inspect(engine)` 和 `MetaData.reflect(bind=self._engine)`——**这是实际建连 + 反射的瞬间**，连不上会抛 `sqlalchemy.exc.OperationalError` 等异常

**特殊：Kyuubi 的 `create_connector`**（[conn_kyuubi.py:451-453](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_kyuubi.py#L451-L453)）→ `KyuubiConnector.from_parameters(self)`，在 ZK 模式下通过 `engine_args` 返回 `{"creator": self._build_zk_creator()}`（[conn_kyuubi.py:344-359](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_kyuubi.py#L344-L359)），creator 先做 ZK 服务发现再 `hive.connect`。

**测试连接不写入缓存**：注意 `test_connection` 调用的是 `create_connector`（第 442 行，直接 `param.create_connector()`），**不是** `get_connector`，因此测试连接不会污染 `_connector_cache`，测试完 connector 对象即被丢弃。

### 37.7 错误处理和返回前端的方式

#### 后端错误返回格式

统一用 `Result` 模型（`packages/dbgpt-app/src/dbgpt_app/openapi/api_view_model.py:13-29`）：

```python
class Result(BaseModel, Generic[T]):
    success: bool
    err_code: Optional[str] = None
    err_msg: Optional[str] = None
    data: Optional[T] = None
    host_name: Optional[str] = socket.gethostname()
```

#### 全局异常处理器

文件：`packages/dbgpt-serve/src/dbgpt_serve/core/schemas.py:25-69`

通过 `add_exception_handler(app)` 注册三个处理器：
1. **`RequestValidationError`**（第 25-35 行）→ `Result.failed(msg=message, err_code="E0001")`，HTTP 400
2. **`HTTPException`**（第 38-44 行）→ `Result.failed(msg=str(exc.detail), err_code=str(exc.status_code))`，HTTP `exc.status_code`
3. 通用 `Exception`（第 47-62 行）→ `Result.failed(msg=err_msg, err_code="E0003")`，HTTP 400

#### 测试连接的错误链路

1. `ConnectorManager.test_connection` 抛 `ValueError(f"Test connection Failure!{str(e)}")`（[connector_manager.py:518](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L518)）
2. `Service.test_connection` 不 catch，继续向上抛（[service.py:297](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L297) 直接 return）
3. `endpoints.py` 的 `blocking_func_to_async` 抛出
4. **被全局 `common_exception_handler` 捕获**（`schemas.py:47`）→ `Result.failed(msg=err_msg, err_code="E0003")`，HTTP 400

#### Service.create 的错误处理

`Service.create`（[service.py:143-162](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L143-L162)）有两层错误：
- 重名 → `HTTPException(status_code=400, detail=f"datasource name:{db_name} already exists")`（第 139-142 行）→ 走 `http_exception_handler`
- 不支持类型 → `HTTPException(status_code=400, ...)`（第 146-148 行）
- 其他异常 → `raise ValueError("Add db connect info error!" + str(e))`（第 162 行）→ 走 `common_exception_handler`

#### 前端错误接收

文件：`web/client/api/tools/interceptors.ts:12-49`

`apiInterceptors` 函数处理两类响应：
1. **HTTP 200 但 `data.success === false`**（第 22-31 行）：`notification.error({ message: 'Request error', description: data.err_msg })`，返回 `[null, data.data, data, response]`
2. **HTTP 非 2xx 或网络错误**（第 34-48 行）：从 `err.request.response` 解析 `err_msg`，`notification.error` 弹窗，返回 `[err, null, null, null]`

在 `database-form.tsx:93-95`：
```typescript
const [testErr] = await apiInterceptors(postDbTestConnect(data));
if (testErr) return;   // 测试失败，弹窗已由 interceptors 显示，直接 return
const [err] = await apiInterceptors((editValue ? postDbEdit : postDbAdd)(data));
```
测试连接失败时，错误消息通过 antd `notification.error` 全局弹窗展示，表单不继续提交。

### 37.8 完整端到端调用栈总结

#### 新增数据库（前端点击到 connect_config 表写入）

```
[前端] web/components/database/database-form.tsx:93-95
  postDbTestConnect(data)  → POST /api/v2/serve/datasources/test-connection
    ↓ (测试通过后)
  postDbAdd(data)          → POST /api/v2/serve/datasources

[API 层] packages/dbgpt-serve/src/dbgpt_serve/datasource/api/endpoints.py:104-118
  create(request) → blocking_func_to_async(global_system_app, service.create, request)

[Service 层] packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py:101-163
  Service.create(request):
    ├─ self.datasource_manager._create_parameters(request)  [connector_manager.py:419-432]
    │    └─ DBType.of_db_type(request.type)                 [schema.py:47-60]
    │    └─ _supported_types()[db_type.value()]             [connector_manager.py:174-183]
    │    └─ cls.param_class().from_dict(request.params)     [e.g. conn_mysql.py:49-51]
    ├─ connector_params.persisted_state()                   [parameter.py:52-75]
    │    └─ 字段映射 host→db_host, password→db_pwd, ...     [parameter.py:78-91]
    ├─ self._dao.get_by_names(db_name)  重名校验            [connect_config_db.py:61-68]
    ├─ DBType.of_db_type(str_db_type)  二次校验
    ├─ self._dao.create(persisted_state)  ★写入 connect_config 表
    │    (ConnectConfigEntity, 表名 connect_config, 唯一约束 uk_db)
    └─ executor.submit(db_summary_embedding, db_name, str_db_type)  异步嵌入向量库

[返回] DatasourceQueryResponse → Result.succ(res) → HTTP 200
```

#### ConnectorManager 根据 db_type 选择 connector（含 kyuubi/duckdb/spark）

```
get_connector(db_name)                          [connector_manager.py:196-262]
  ├─ 检查 _connector_cache（TTL=1800s=30min）    [第 221-234 行, 双重检查锁定]
  ├─ 快照 prev_tables = cached.get_table_names() [第 236-247 行]
  ├─ _build_connector(db_name)                   [connector_manager.py:344-417]
  │    ├─ storage.get_db_config(db_name)         [connect_config_db.py:202-231]
  │    ├─ _resolve_env_vars(db_pwd)              [manager.py:195-224]
  │    ├─ DBType.of_db_type(db_type)             [schema.py:47-60]
  │    ├─ get_cls_by_dbtype(db_type.value())     [connector_manager.py:185-194]
  │    │    └─ 遍历 BaseConnector.__subclasses__() 递归
  │    │    └─ 匹配 cls.db_type == db_type and cls.is_normal_type()
  │    ├─ 分支选择:
  │    │    ├─ is_file_db() (sqlite/duckdb/spark)
  │    │    │    → connect_instance.from_file_path(db_path)
  │    │    │       e.g. DuckDbConnector.from_file_path  [conn_duckdb.py:65-70]
  │    │    │            create_engine("duckdb:///" + file_path)
  │    │    ├─ db_type == "oracle"
  │    │    │    → from_uri_db(host,port,user,pwd,service_name)  [第 364-376 行]
  │    │    ├─ db_type == "kyuubi" and "," in db_host  (ZK 模式)
  │    │    │    → param_cls.from_persisted_state(parsed_config) [第 396-408 行]
  │    │    │    → param.create_connector()
  │    │    │       → KyuubiConnector.from_parameters
  │    │    │       → engine_args 含 ZK creator         [conn_kyuubi.py:344-359, 451-453]
  │    │    └─ 默认 (mysql/pg/mssql/...)
  │    │         → from_uri_db(host,port,user,pwd,db_name,schema) [base.py:182-205]
  │    │              create_engine(f"{driver}://user:pwd@host:port/db")
  │    └─ RDBMSConnector.__init__(engine)        [base.py:117-168]
  │         └─ MetaData.reflect(bind=engine)  ★昂贵操作，缓存动机
  ├─ 写入 _connector_cache[db_name] = (now, connector)  [第 250-251 行]
  ├─ Schema 变更检测:
  │    new_tables = connector.get_table_names()
  │    if new_tables != prev_tables:
  │       _trigger_schema_embedding(db_name)    [connector_manager.py:264-296]
  │         → executor.submit(db_summary_embedding, db_name, db_type)
  └─ return connector
```

#### 测试连接端到端

```
[前端] database-form.tsx:93
  postDbTestConnect(data) → POST /api/v2/serve/datasources/test-connection

[API] endpoints.py:224-242
  test_connection(request) → blocking_func_to_async(..., service.test_connection, request)

[Service] service.py:288-297
  Service.test_connection(request) → self.datasource_manager.test_connection(request)

[ConnectorManager] connector_manager.py:490-518
  test_connection(request):
    ├─ _resolve_env_vars(request.params["password"])   [第 500-502 行]
    ├─ _create_parameters(request)                     [第 504 行]
    │    └─ cls.param_class().from_dict(request.params)
    ├─ create_connector(param)                         [第 505 行, 第 442-444 行]
    │    └─ param.create_connector()
    │         → XXXConnector.from_parameters(param)
    │         → cls.from_uri(param.db_url(), engine_args=param.engine_args())
    │         → create_engine(url, **engine_args)
    │         → RDBMSConnector.__init__(engine)
    │              └─ MetaData.reflect(bind=engine)  ★实际建连+反射，失败抛异常
    └─ return True  (异常则 raise ValueError)

[异常路径]
  raise ValueError(...)  →  common_exception_handler  [schemas.py:47-62]
    → Result.failed(msg=err_msg, err_code="E0003"), HTTP 400
    → 前端 interceptors.ts:34-48 → notification.error 弹窗
    → database-form.tsx:94 if (testErr) return; 阻止后续 add/edit
```

#### 错误处理与返回前端的方式汇总

| 错误来源 | 抛出位置 | 异常类型 | 处理器 | err_code | HTTP 状态 |
|---|---|---|---|---|---|
| 请求体校验失败 | FastAPI | `RequestValidationError` | `validation_exception_handler` | E0001 | 400 |
| Service 主动抛 | [service.py:139,146,201,205,310](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L139) | `HTTPException` | `http_exception_handler` | `str(status_code)` | `status_code` |
| 测试连接失败 | [connector_manager.py:518](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py#L518) | `ValueError` | `common_exception_handler` | E0003 | 400 |
| create 其他异常 | [service.py:162](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/service.py#L162) | `ValueError` | `common_exception_handler` | E0003 | 400 |
| 旧 API test | [api_v1.py:246](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/api_v1.py#L246) | 直接 `Result.failed(code="E1001", msg=str(e))` | — | E1001 | 200（success=false） |

前端 `apiInterceptors`（`interceptors.ts`）对 HTTP 200 + `success=false` 和 HTTP 4xx/5xx 两种情况都通过 antd `notification.error` 全局弹窗展示 `err_msg`，并返回 `[err, null, null, null]` 供调用方判断。

***

## 38. RAG 知识库摄取全流程

> 本章追踪用户从前端创建知识空间、上传文档，到文档被分块、向量化、持久化到 ChromaDB 的完整调用链，以及后续的检索过程。

### 38.1 API 路由注册

RAG Serve 层的 API 前缀为 `/api/v2/serve/knowledge`，在 [serve.py:30](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/rag/serve.py#L30) 中声明：

```python
api_prefix: Optional[str] = "/api/v2/serve/knowledge"
```

通过 `system_app.app.include_router(router, prefix=self._api_prefix)` 注册到 FastAPI 应用。核心端点如下：

| 端点 | 方法 | 处理函数 | 功能 |
|---|---|---|---|
| `/spaces` | POST | `create_space` | 创建知识空间 |
| `/spaces` | PUT | `update_space` | 更新知识空间 |
| `/spaces/{space_id}` | GET | `get_space` | 查询空间详情 |
| `/documents` | POST | `create_document` | 创建文档（上传文件或文本） |
| `/documents/sync` | POST | `sync_documents` | 批量同步文档到向量库 |
| `/documents/{document_id}/sync` | POST | `sync_document` | 单文档同步 |
| `/spaces/{space_id}/retrieve` | POST | `retrieve` | 知识检索 |
| `/documents/{document_id}` | DELETE | `delete_document` | 删除文档 |

### 38.2 创建知识空间

```
[前端] 知识库管理页面
  POST /api/v2/serve/knowledge/spaces
  body: { name: "my_space", vector_type: "Chroma", ... }

[API] endpoints.py:111-126
  create_space(request) → blocking_func_to_async(service.create, request)

[Service] service.py:131-139
  Service.create(request):
    ├─ 校验 name 唯一性（_dao.get_knowledge_space）
    ├─ 构建 KnowledgeSpaceEntity
    └─ _dao.create_knowledge_space(request)   → 写入 knowledge_space 表
```

`vector_type` 决定向量存储引擎（Chroma / Milvus / Weaviate / KnowledgeGraph / FullText），后续 StorageManager 会根据此类型创建不同的存储连接器。

### 38.3 文档上传与创建

```
[前端] 文档上传组件
  POST /api/v2/serve/knowledge/documents
  Content-Type: multipart/form-data
  Fields: doc_name, doc_type, space_id, content?, doc_file?

[API] endpoints.py:229-256
  create_document(doc_name, doc_type, space_id, content, doc_file)
  → 构建 DocumentServeRequest
  → blocking_func_to_async(service.create_document, request)

[Service] service.py:161-206
  Service.create_document(request):
    ├─ 校验 space 存在
    ├─ 校验 doc_name 不重复
    ├─ 如果 doc_file 存在且 doc_type == DOCUMENT:
    │    ├─ safe_filename = os.path.basename(doc_file.filename)   ★安全处理，防止路径遍历
    │    ├─ custom_metadata = {space_name, doc_name, doc_type}
    │    ├─ self.get_fs().save_file("dbgpt_knowledge_file", safe_filename, doc_file.file, custom_metadata)
    │    │    → 返回 file_uri（如 "dbgpt://file_dbgpt_knowledge_file/xxx.pdf"）
    │    └─ request.content = file_uri
    ├─ 构建 KnowledgeDocumentEntity:
    │    doc_name, doc_type, space, chunk_size=0,
    │    status=SyncStatus.TODO, last_sync=datetime.now(),
    │    content=file_uri 或 文本内容, result=""
    └─ _document_dao.create_knowledge_document(document)   → 写入 knowledge_document 表
```

**关键点**：`create_document` 只是将文件保存到 FileServe 并创建数据库记录，**不会触发向量化**。需要后续调用 `sync_document` 才会开始分块和 embedding。

### 38.4 文档同步（向量化入口）

```
[前端] 文档列表 → 点击"同步"按钮
  POST /api/v2/serve/knowledge/documents/{document_id}/sync
  body: { chunk_parameters: { chunk_strategy: "Automatic", ... } }

[API] endpoints.py:341-358
  sync_document(document_id, request)
  ├─ 如果 request.chunk_parameters 为空，设置默认值 ChunkParameters(chunk_strategy="Automatic")
  └─ service.sync_document([request])

[Service] service.py:208-248
  Service.sync_document(requests):
    for sync_request in requests:
      ├─ 从 _document_dao 获取 doc 记录
      ├─ 校验 doc.status 不是 RUNNING/FINISHED（防止重复同步）
      ├─ 如果 chunk_strategy != CHUNK_BY_SIZE:
      │    从 space_context 读取 chunk_size / chunk_overlap 覆盖默认值
      └─ await _sync_knowledge_document(space_id, doc, chunk_parameters)
```

### 38.5 知识文档同步核心方法

[service.py:500-551](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_serve/rag/service/service.py#L500) 是整个摄取流程的枢纽：

```
Service._sync_knowledge_document(space_id, doc, chunk_parameters):
  ├─ 获取 space 信息和 storage_connector
  │    storage_connector = storage_manager.get_storage_connector(space.name, space.vector_type)
  │    → 根据 vector_type 创建 ChromaStore / MilvusStore / KnowledgeGraph / FullTextStore
  │
  ├─ 处理文件下载（doc_type == DOCUMENT 且 content 以 "dbgpt://" 开头）
  │    local_file_path, file_meta = await self.get_fs().download_file(knowledge_content)
  │    knowledge_content = local_file_path
  │
  ├─ 创建 Knowledge 对象（KnowledgeFactory 工厂）
  │    knowledge = KnowledgeFactory.create(
  │        datasource=knowledge_content,
  │        knowledge_type=KnowledgeType.get_by_value(doc.doc_type)
  │    )
  │
  ├─ 更新 doc.status = RUNNING
  │
  └─ asyncio.create_task(async_doc_process(...))   ★异步任务，不阻塞 API 返回
       → 立即返回 doc_id，向量化在后台进行
```

**KnowledgeFactory 工厂分发**（[factory.py:30-71](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_ext/src/dbgpt_ext/rag/knowledge/factory.py#L30)）：

| KnowledgeType | 工厂方法 | 返回的 Knowledge 子类 | 支持的文件格式 |
|---|---|---|---|
| DOCUMENT | `from_file_path` | PDFKnowledge / DocxKnowledge / CSVKnowledge / ExcelKnowledge / MarkdownKnowledge / TXTKnowledge / HTMLKnowledge / PPTXKnowledge / Word97DocKnowledge | pdf/docx/csv/xlsx/md/txt/html/pptx/doc |
| URL | `from_url` | URLKnowledge | 网页 URL |
| TEXT | `from_text` | StringKnowledge | 纯文本字符串 |

文件扩展名 → Knowledge 子类的映射通过 `_select_document_knowledge` 实现：遍历所有 `Knowledge.__subclasses__()`，找到 `document_type().value == extension` 的子类实例化。

### 38.6 异步文档处理（分块 + 向量化 + 持久化）

[service.py:554-638](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_serve/rag/service/service.py#L554) 是异步摄取的核心：

```
Service.async_doc_process(knowledge, chunk_parameters, storage_connector, doc, space, knowledge_content):
  try:
    ├─ 检查是否有自定义 DAG（按 domain_type 标签查找）
    │    dags = dag_manager.get_dags_by_tag(TAG_KEY_KNOWLEDGE_FACTORY_DOMAIN_TYPE, space.domain_type)
    │    if dags and dags[0].leaf_nodes:
    │        → 执行自定义 DAG（高级场景，如领域特化处理）
    │    else:
    │        → 走标准 EmbeddingAssembler 路径
    │
    ├─ 【标准路径】EmbeddingAssembler.aload_from_knowledge()
    │    assembler = await EmbeddingAssembler.aload_from_knowledge(
    │        knowledge=knowledge,
    │        index_store=storage_connector,
    │        chunk_parameters=chunk_parameters,
    │    )
    │
    │    内部流程（BaseAssembler.__init__）:
    │    ├─ knowledge.load()                    → 加载文档为 List[Document]
    │    │    PDF: PyPDFLoader / Docx: python-docx / CSV: csv.reader / ...
    │    └─ chunk_manager.split(documents)       → 分块为 List[Chunk]
    │         ├─ _select_text_splitter()          → 根据策略选择 TextSplitter
    │         └─ text_splitter.split_documents(documents)
    │
    ├─ chunk_docs = assembler.get_chunks()       → 获取分块结果
    ├─ doc.chunk_size = len(chunk_docs)
    │
    └─ vector_ids = await assembler.apersist(
           max_chunks_once_load=max_chunks_once_load,
           max_threads=max_threads,
           file_id=doc.id
       )
       → 内部: index_store.aload_document_with_limit(chunks, max_chunks_once_load, max_threads, file_id)
       → ChromaStore: 批量 embedding + 写入 ChromaDB 集合
  except Exception:
    ├─ doc.status = FAILED
    └─ doc.result = "document embedding failed" + str(e)

  最终:
  ├─ doc.status = FINISHED / FAILED
  ├─ doc.vector_ids = ",".join(vector_ids)        ★记录 chunk 对应的向量 ID
  ├─ 保存 chunk 详情到 document_chunk 表
  │    chunk_entities = [DocumentChunkEntity(doc_name, doc_type, document_id, content, meta_info)]
  │    _chunk_dao.create_documents_chunks(chunk_entities)
  └─ _document_dao.update_knowledge_document(doc)
```

### 38.7 ChunkManager 与分块策略

[chunk_manager.py:123-219](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_ext/src/dbgpt_ext/rag/chunk_manager.py#L123) 管理文档分块：

```python
class ChunkManager:
    def __init__(self, knowledge, chunk_parameter, extractor):
        self._chunk_strategy = chunk_parameter.chunk_strategy or knowledge.default_chunk_strategy().name
        self._text_splitter = chunk_parameter.text_splitter  # 可自定义
        self._splitter_type = chunk_parameter.splitter_type  # langchain / llama-index / user_define

    def split(self, documents: List[Document]) -> List[Chunk]:
        text_splitter = self._select_text_splitter()
        if self._splitter_type == LANGCHAIN:
            documents = text_splitter.split_documents(documents)
            return [Chunk.langchain2chunk(doc) for doc in documents]
        elif self._splitter_type == LLAMA_INDEX:
            nodes = text_splitter.split_documents(documents)
            return [Chunk.llamaindex2chunk(node) for node in nodes]
        else:
            return text_splitter.split_documents(documents)
```

**5 种分块策略**（[base.py:67-145](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/rag/knowledge/base.py#L67)）：

| ChunkStrategy | Splitter 类 | 核心参数 | 适用场景 |
|---|---|---|---|
| `CHUNK_BY_SIZE` | RecursiveCharacterTextSplitter | chunk_size=512, chunk_overlap=50 | 通用默认 |
| `CHUNK_BY_PAGE` | PageTextSplitter | 无 | PDF 按页分割 |
| `CHUNK_BY_PARAGRAPH` | ParagraphTextSplitter | separator="\n" | 按段落分割 |
| `CHUNK_BY_SEPARATOR` | SeparatorTextSplitter | separator, enable_merge | 按自定义分隔符 |
| `CHUNK_BY_MARKDOWN_HEADER` | MarkdownHeaderTextSplitter | 无 | Markdown 按标题层级 |

当 `chunk_strategy = "Automatic"` 时，使用 Knowledge 子类的 `default_chunk_strategy()`，通常为 `CHUNK_BY_SIZE`。

### 38.8 EmbeddingAssembler 向量化

[embedding.py:17-152](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_ext/src/dbgpt_ext/rag/assembler/embedding.py#L17) 负责将分块后的文本向量化并持久化：

```
EmbeddingAssembler 继承 BaseAssembler:
  __init__:
    ├─ 调用 BaseAssembler.__init__(knowledge, chunk_parameters)
    │    ├─ knowledge.load() → 加载文档
    │    └─ chunk_manager.split(documents) → 分块
    └─ 保存 self._index_store = index_store

  apersist():
    ├─ max_chunks_once_load: 每次批量加载的最大 chunk 数
    ├─ max_threads: 并发写入线程数
    └─ index_store.aload_document_with_limit(chunks, max_chunks_once_load, max_threads, file_id)
         → ChromaStore: 调用 embedding_fn 对每个 chunk 文本生成向量
         → 写入 ChromaDB collection
         → 返回 vector_ids 列表
```

### 38.9 StorageManager 与 ChromaStore 持久化

[storage_manager.py:18-108](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/rag/storage_manager.py#L18) 根据空间类型创建存储连接器：

```
StorageManager.get_storage_connector(index_name, storage_type):
  if storage_type in supported_vector_types:    # Chroma / Milvus / Weaviate
    → create_vector_store(index_name)
  elif storage_type == "KnowledgeGraph":
    → create_kg_store(index_name)
  elif storage_type == "FullText":
    → create_full_text_store(index_name)

StorageManager.create_vector_store(index_name):
  ├─ 缓存检查: _store_cache[index_name]
  ├─ embedding_factory.create()  → 获取 embedding 函数
  ├─ vector_store_config.create_store(name=index_name, embedding_fn=embedding_fn, ...)
  │    → ChromaVectorConfig.create_store() → ChromaStore(vector_store_config, name, embedding_fn)
  └─ _store_cache[index_name] = new_store
```

**ChromaStore**（[chroma_store.py:84-158](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_ext/src/dbgpt_ext/storage/vector_store/chroma_store.py#L84)）初始化流程：

```
ChromaStore.__init__(vector_store_config, name, embedding_fn):
  ├─ persist_dir = resolve_root_path(chroma_path) + "/chromadb"
  ├─ collection_name: 如果名称不合法（Chroma 限制 3-63 字符，仅允许 a-z/0-9/_-.），用 SHA256 哈希替代
  ├─ _chroma_client = PersistentClient(path=persist_dir)
  ├─ _build_collection_configuration()  ★配置 HNSW 批量大小（Windows 兼容）
  └─ _collection = create_collection(collection_name, collection_metadata, collection_configuration)
```

持久化目录结构：`{pilot_path}/data/chromadb/{collection_name}/`

### 38.10 4 种检索模式

[knowledge_space.py:25-212](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt_serve/rag/retriever/knowledge_space.py#L25) 实现了 4 种检索模式：

```
KnowledgeSpaceRetriever._aretrieve_with_score(query, score_threshold):
  if retrieve_mode == SEMANTIC:
    → semantic_retrieve(query, score_threshold)
       → _retriever_chain.aretrieve_with_scores()
       → EmbeddingRetriever: 向量相似度检索
       → QARetriever: QA 对匹配（如果知识空间有预设问答对）

  elif retrieve_mode == KEYWORD:
    → full_text_retrieve(query, top_k)
       → storage_connector.afull_text_search(query, top_k)
       → ElasticSearch BM25 检索

  elif retrieve_mode == TREE:
    → tree_index_retrieve(query, top_k)
       → DocTreeRetriever: 关键词提取 + 文档树遍历
       → KeywordExtractor: LLM 提取查询关键词
       → 递归搜索文档树节点

  elif retrieve_mode == HYBRID:
    → 并行执行 Semantic + Keyword + Tree 三路检索
    → asyncio.gather(semantic_retrieve, full_text_retrieve, tree_index_retrieve)
    → 合并去重: unique_candidates = {chunk.content: chunk for chunk in all_candidates}
```

| 检索模式 | 实现类 | 核心算法 | 依赖 |
|---|---|---|---|
| Semantic | EmbeddingRetriever + QARetriever | 向量余弦相似度 | ChromaDB/Milvus |
| Keyword | ElasticDocumentStore | BM25 (TF/IDF) | ElasticSearch |
| Tree | DocTreeRetriever | 关键词匹配 + 树遍历 | LLM 关键词提取 |
| Hybrid | 并行三路 + 合并去重 | 综合 | 以上全部 |

检索模式由知识空间的 `context` 字段中的 `retrieve_mode` 决定，默认为 `Semantic`。

### 38.11 完整端到端调用栈

```
[前端] 上传文件 + 点击同步
  POST /api/v2/serve/knowledge/documents
  → 文件存入 FileServe (dbgpt_knowledge_file bucket)
  → 返回 doc_id

  POST /api/v2/serve/knowledge/documents/{doc_id}/sync
  → 触发向量化

[API] endpoints.py
  → service.sync_document([request])

[Service] service.py
  ├─ sync_document()
  │    └─ _sync_knowledge_document(space_id, doc, chunk_parameters)
  │         ├─ StorageManager.get_storage_connector(space.name, space.vector_type)
  │         │    → ChromaStore(persist_dir, collection_name, embedding_fn)
  │         ├─ KnowledgeFactory.create(datasource, knowledge_type)
  │         │    → PDFKnowledge / DocxKnowledge / ...
  │         ├─ doc.status = RUNNING
  │         └─ asyncio.create_task(async_doc_process(...))
  │
  └─ async_doc_process()  [异步后台]
       ├─ EmbeddingAssembler.aload_from_knowledge(knowledge, index_store, chunk_parameters)
       │    ├─ BaseAssembler.__init__()
       │    │    ├─ knowledge.load()  → List[Document]
       │    │    └─ ChunkManager.split(documents)  → List[Chunk]
       │    │         └─ _select_text_splitter()
       │    │              └─ ChunkStrategy.CHUNK_BY_SIZE.match(chunk_size=512, chunk_overlap=50)
       │    │                   → RecursiveCharacterTextSplitter
       │    └─ 返回 assembler
       ├─ chunk_docs = assembler.get_chunks()
       └─ vector_ids = await assembler.apersist(max_chunks_once_load, max_threads, file_id)
            └─ ChromaStore.aload_document_with_limit(chunks, ...)
                 ├─ embedding_fn(chunks)  → 生成向量
                 └─ collection.add(ids, embeddings, documents, metadatas)  → 写入 ChromaDB

[最终状态]
  ├─ doc.status = FINISHED
  ├─ doc.vector_ids = "id1,id2,id3,..."  → chunk 与向量的映射
  ├─ chunk 记录写入 document_chunk 表
  └─ 向量数据持久化到 {pilot_path}/data/chromadb/
```

### 38.12 错误处理与状态流转

文档同步状态（`SyncStatus` 枚举）：

```
TODO → RUNNING → FINISHED
                  ↘ FAILED
```

| 状态 | 含义 | 触发时机 |
|---|---|---|
| TODO | 初始状态，未同步 | create_document 时设置 |
| RUNNING | 正在向量化 | _sync_knowledge_document 进入时设置 |
| FINISHED | 向量化完成 | apersist 成功后设置 |
| FAILED | 向量化失败 | apersist 异常时设置 |

**关键防护**：
- `sync_document` 校验 `doc.status != RUNNING/FINISHED`，防止重复触发
- `async_doc_process` 在 try/except 中运行，失败只更新状态不抛异常
- StorageManager 使用 `_store_cache` + `_cache_lock` 避免重复创建 ChromaStore 实例
- ChromaStore 的 HNSW `batch_size` 配置避免 Windows 下 hnswlib 崩溃

***

## 39. AWEL 工作流执行流程

> 本章详细追踪 AWEL（Agentic Workflow Expression Language）工作流从 DAG 定义、节点构建、FlowFactory 编排、到 DefaultWorkflowRunner 递归调度执行的完整过程。

### 39.1 DAG 定义与节点体系

AWEL 的核心数据结构是 **DAG（有向无环图）**，定义在 [base.py:788](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/dag/base.py#L788)：

```
DAG
  ├─ dag_id: str                    # 唯一标识
  ├─ dag_name: str                  # 名称
  ├─ _default_dag_variables         # DAG 级变量
  ├─ _save_dag_ctx() / _after_dag_end()  # 生命周期钩子
  │
  ├─ trigger_nodes: List[DAGNode]   # 触发器节点（入口）
  ├─ leaf_nodes: List[DAGNode]      # 叶子节点（出口）
  └─ all_nodes: List[DAGNode]       # 全部节点

DAGNode (抽象基类)
  ├─ node_id: str                   # 节点唯一 ID
  ├─ node_name: str                 # 节点名称
  ├─ upstream: List[DAGNode]        # 上游节点
  ├─ downstream: List[DAGNode]      # 下游节点
  ├─ dag: Optional[DAG]             # 所属 DAG
  └─ metadata: ViewMetadata         # 可视化元数据

BaseOperator(DAGNode)  [operators/base.py:161]
  ├─ system_app: SystemApp
  ├─ _run(dag_ctx, log_id)          # 核心执行方法
  ├─ call(call_data)                # 同步调用入口
  ├─ call_stream(call_data)         # 流式调用入口
  └─ can_skip_in_branch()           # BranchOperator 跳过判定
```

### 39.2 五种核心 Operator

| Operator | 文件位置 | 功能 | 输入 | 输出 |
|---|---|---|---|---|
| **MapOperator** | [common_operator.py:128](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/operators/common_operator.py#L128) | 一对一映射变换 | 单个上游输出 | 变换后的结果 |
| **JoinOperator** | [common_operator.py:26](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/operators/common_operator.py#L26) | 多输入聚合 | 多个上游输出 | 聚合后的结果 |
| **BranchOperator** | [common_operator.py:206](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/operators/common_operator.py#L206) | 条件分支 | 单个上游输出 | 选择下游路径 |
| **StreamifyAbsOperator** | [stream_operator.py:11](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/operators/stream_operator.py#L11) | 非流式→流式 | 非流式数据 | AsyncIterator |
| **UnstreamifyAbsOperator** | [stream_operator.py:52](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/operators/stream_operator.py#L52) | 流式→非流式 | AsyncIterator | 聚合结果 |

此外还有 **Trigger** 系列（继承 `BaseOperator`）：
- **HttpTrigger**：HTTP 请求触发 DAG 执行
- **CommonLLMHttpTrigger**：LLM Chat 请求触发
- **AgentDummyTrigger**：Agent 调用触发

### 39.3 DAGContext 数据传递

[base.py:625](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/dag/base.py#L625) 定义了 DAG 运行时上下文：

```python
class DAGContext:
    _event_loop_task_id: int          # 事件循环任务 ID
    _node_to_outputs: Dict[str, TaskContext]  # node_id → 任务输出
    _share_data: Dict[str, Any]       # 跨节点共享数据
    _streaming_call: bool             # 是否流式调用
    _current_task_context: TaskContext  # 当前正在执行的节点上下文
    _dag_variables: DAGVariables      # DAG 级变量
```

数据在节点间传递的方式：
1. 每个节点执行完毕后，输出写入 `_node_to_outputs[node_id]`
2. 下游节点从 `inputs = [node_outputs[upstream.node_id] for upstream in node.upstream]` 获取上游输出
3. 通过 `DefaultInputContext(inputs)` 封装为统一的输入上下文
4. `BranchOperator` 通过 `skip_node_ids` 集合控制哪些下游节点被跳过

### 39.4 FlowFactory：从 JSON 定义到 DAG

[flow_factory.py:580](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/flow/flow_factory.py#L580) 负责将前端可视化的 JSON 定义转换为可执行的 DAG：

```
FlowFactory.build(flow_panel: FlowPanel) → DAG:
  ├─ 解析 flow_data.nodes:
  │    ├─ key_to_operator_nodes: {node_id: FlowNodeData}  # Operator 节点
  │    └─ key_to_resource_nodes: {node_id: FlowNodeData}  # Resource 节点（模型/工具等）
  │
  ├─ 解析 flow_data.edges:
  │    ├─ key_to_upstream: 每个节点的上游列表
  │    └─ key_to_downstream: 每个节点的下游列表
  │
  ├─ 实例化 Resource 节点:
  │    for resource_node in key_to_resource_nodes:
  │        → 根据 node.data.type 创建对应 Resource 实例
  │        → 注册到 key_to_resource[key]
  │
  ├─ 实例化 Operator 节点:
  │    for operator_node in key_to_operator_nodes:
  │        → 根据 node.data.label 查找注册的 Operator 类
  │        → 注入 Resource 依赖
  │        → 创建 Operator 实例
  │
  ├─ 建立节点连接:
  │    for edge in flow_data.edges:
  │        source_node >> target_node  # >> 操作符建立上下游关系
  │
  └─ 构建 DAG:
       DAG(dag_id, dag_name, nodes=all_operators)
```

### 39.5 DefaultWorkflowRunner 递归深度优先调度

[local_runner.py:24](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/runner/local_runner.py#L24) 是 AWEL 的执行引擎：

```
DefaultWorkflowRunner.execute_workflow(node, call_data, streaming_call, exist_dag_ctx, dag_variables):
  ├─ JobManager.build_from_end_node(node, call_data)
  │    → 从叶子节点反向构建任务图，解析 call_data 到对应节点
  │
  ├─ 创建 DAGContext:
  │    dag_ctx = DAGContext(
  │        event_loop_task_id, node_to_outputs={},
  │        share_data={}, streaming_call,
  │        node_name_to_ids, dag_variables
  │    )
  │
  ├─ job_manager.before_dag_run()  # 前置钩子
  │
  └─ _execute_node(job_manager, node, dag_ctx, node_outputs, skip_node_ids, system_app)

_execute_node(job_manager, node, dag_ctx, node_outputs, skip_node_ids, system_app):
  ├─ 如果 node.node_id in node_outputs: return  ★已执行过，跳过（DAG 去重）
  │
  ├─ 递归执行所有上游节点:
  │    for upstream_node in node.upstream:
  │        await _execute_node(job_manager, upstream_node, dag_ctx, node_outputs, skip_node_ids, system_app)
  │    ★这是深度优先的递归遍历，从叶子节点回溯到触发器节点
  │
  ├─ 收集上游输出:
  │    inputs = [node_outputs[upstream.node_id] for upstream in node.upstream]
  │    input_ctx = DefaultInputContext(inputs)
  │
  ├─ 创建当前节点的 TaskContext:
  │    task_ctx = DefaultTaskContext(node_id, TaskState.INIT, ...)
  │    task_ctx.set_call_data(job_manager.get_call_data_by_id(node_id))
  │    task_ctx.set_task_input(input_ctx)
  │    dag_ctx.set_current_task_context(task_ctx)
  │
  ├─ 检查是否跳过（BranchOperator 逻辑）:
  │    if node.node_id in skip_node_ids:
  │        task_ctx.set_current_state(SKIP)
  │        node_outputs[node_id] = task_ctx
  │        return
  │
  ├─ 执行节点:
  │    await node._run(dag_ctx, log_id)
  │    node_outputs[node_id] = dag_ctx.current_task_context
  │    task_ctx.set_current_state(SUCCESS)
  │
  └─ 处理 BranchOperator 跳过逻辑:
       if isinstance(node, BranchOperator):
           skip_nodes = task_ctx.metadata.get("skip_node_names", [])
           _skip_current_downstream_by_node_name(node, skip_nodes, skip_node_ids)
               → 遍历 BranchOperator 的下游
               → 根据 skip_node_names 将需要跳过的节点 ID 加入 skip_node_ids
               → 递归传播 skip 标记到下游（_skip_downstream_by_id）
               → JoinOperator 只在所有上游都被跳过时才跳过自身
```

**执行顺序示意**（以一个典型的 Chat Flow 为例）：

```
HttpTrigger → PromptBuilder → LLMOperator → OutputFormatter
     ↑                                              ↑
  (入口)                                        (叶子节点)

执行顺序（从叶子节点回溯）:
1. _execute_node(OutputFormatter)  → 发现上游 LLMOperator
2. _execute_node(LLMOperator)      → 发现上游 PromptBuilder
3. _execute_node(PromptBuilder)    → 发现上游 HttpTrigger
4. _execute_node(HttpTrigger)      → 无上游，执行自身
5. HttpTrigger 输出 → PromptBuilder 执行 → LLMOperator 执行 → OutputFormatter 执行
```

### 39.6 从 API 触发执行

AWEL 工作流有两种主要的触发方式：

#### 方式一：HTTP Trigger 自动注册路由

当 DAG 包含 `HttpTrigger` 节点时，系统启动时会自动将 DAG 注册为 FastAPI 路由：

```
HttpTrigger.__init__(endpoint="/my_api", methods=["POST"], http_trigger_body=...):
  → DAG 初始化时，HttpTrigger._register_endpoint()
  → app.add_api_route(endpoint, handler, methods=methods)
  → 外部 HTTP 请求直接触发 DAG 执行
```

#### 方式二：通过 Flow Serve 层 Chat 接口

```
POST /api/v2/serve/flow/chat/{flow_uid}

[Flow Service] service.py:436-547
  safe_chat_stream_flow(flow_uid, request):
    ├─ _get_callable_task(flow_uid)
    │    ├─ 从数据库获取 flow 记录
    │    ├─ dag = dag_manager.dag_map[dag_id]
    │    ├─ leaf_nodes = dag.leaf_nodes
    │    └─ return cast(BaseOperator, leaf_nodes[0])
    │
    └─ safe_chat_stream_with_dag_task(task, request, incremental)
         → task.call_stream(call_data=request)  ★触发 DAG 执行
              → DefaultWorkflowRunner.execute_workflow(node=task, call_data, streaming_call=True)
```

### 39.7 AWEL Serve 层

[service.py:49](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-serve/src/dbgpt_serve/flow/service/service.py#L49) 提供 Flow 的 CRUD 和运行管理：

| 方法 | 功能 |
|---|---|
| `create` | 创建 Flow 记录 |
| `create_and_save_dag` | 创建 Flow + 构建 DAG 并注册到 DAGManager |
| `update_flow` | 更新 Flow 定义 + 重新构建 DAG |
| `load_dag_from_db` | 启动时从数据库加载所有 Flow DAG |
| `load_dag_from_dbgpts` | 从 DBGPTs 插件目录加载预定义 DAG |
| `chat_stream_flow_str` | 流式 Chat（V1 兼容格式） |
| `chat_stream_openai` | 流式 Chat（OpenAI SSE 格式） |
| `safe_chat_stream_flow` | 带异常处理的流式 Chat |
| `debug_flow` | 调试模式执行 Flow |

DAG 生命周期管理：

```
启动时:
  Service.before_start()
    → load_dag_from_db()       # 从 flow 表加载所有 DAG
    → load_dag_from_dbgpts()   # 从插件目录加载预定义 DAG

每次创建/更新 Flow:
  Service.create_and_save_dag()
    ├─ FlowFactory.build(flow_panel)  # 从 JSON 构建 DAG
    ├─ dag_manager.register_dag(dag)   # 注册到 DAGManager
    └─ 保存到数据库

运行时:
  _get_callable_task(flow_uid)
    → dag_manager.dag_map[dag_id]  # 从内存缓存获取 DAG
    → dag.leaf_nodes[0]             # 获取叶子节点（即最终输出 Operator）
```

### 39.8 BranchOperator 跳过机制

BranchOperator 是 AWEL 中最复杂的控制流组件，其跳过机制在 [local_runner.py:215-257](file:///home/taoyuan/projects/DB-GPT-main/packages/dbgpt-core/src/dbgpt/core/awel/runner/local_runner.py#L215) 中实现：

```
BranchOperator 执行后:
  ├─ 根据 decide_fn 判断走哪条分支
  ├─ 在 task_ctx.metadata 中设置 skip_node_names = [不需要执行的分支节点名]
  └─ _skip_current_downstream_by_node_name(branch_node, skip_nodes, skip_node_ids):
       ├─ 遍历 branch_node.downstream
       ├─ 如果 child.node_name in skip_nodes 且 child.can_skip_in_branch():
       │    → skip_node_ids.add(child.node_id)
       └─ 递归 _skip_downstream_by_id(child, skip_node_ids):
            ├─ 如果节点 can_skip_in_branch() == False: 停止传播
            ├─ 如果节点所有上游都在 skip_node_ids 中: 跳过该节点
            │    ★JoinOperator 只在所有上游都被跳过时才跳过
            └─ 继续向下游传播
```

### 39.9 与 Agent 集成

AWEL 与 Agent 系统的集成通过 `AgentOperator` 系列实现：

```
AgentDummyTrigger  →  AgentOperator  →  (输出 Agent 执行结果)

AgentOperator 继承 MapOperator:
  call(call_data):
    ├─ 从 call_data 获取 user_input
    ├─ 构建 Agent 命令
    ├─ 调用 Agent 执行（ReAct / Auto-Plan / ...)
    └─ 返回 Agent 输出
```

在 Flow Service 中，如果 DAG 的触发器是 `AgentDummyTrigger`，则 `_parse_flow_category` 返回 `FlowCategory.CHAT_AGENT`，前端会以 Agent 对话模式展示。

### 39.10 完整端到端调用栈

```
[前端] 工作流编辑器 → 保存 Flow
  POST /api/v2/serve/flow
  body: { flow_data: { nodes: [...], edges: [...] } }

[Flow Service] service.py
  create_and_save_dag(request):
    ├─ FlowFactory.build(flow_panel)
    │    ├─ 解析 nodes → 实例化 Operator / Resource
    │    ├─ 解析 edges → 建立上下游关系 (>>)
    │    └─ 构建 DAG(dag_id, dag_name, nodes=operators)
    ├─ dag_manager.register_dag(dag)    # 注册到 DAGManager
    └─ 保存 Flow 记录到数据库

[运行时] HTTP 请求触发
  POST /my_api_endpoint  (HttpTrigger 注册的路由)
  或
  POST /api/v2/serve/flow/chat/{flow_uid}

  → _get_callable_task(flow_uid) → leaf_node

  → leaf_node.call_stream(call_data)
       → DefaultWorkflowRunner.execute_workflow(node, call_data, streaming_call=True)
            ├─ JobManager.build_from_end_node(node, call_data)
            │    → 反向构建任务图，解析 call_data 到各节点
            ├─ DAGContext 初始化
            └─ _execute_node(job_manager, leaf_node, dag_ctx, node_outputs, skip_node_ids, system_app)
                 ├─ 递归执行上游节点 (深度优先)
                 │    _execute_node(upstream_1)
                 │    _execute_node(upstream_2)
                 │    ...
                 ├─ 收集上游输出 → DefaultInputContext
                 ├─ await node._run(dag_ctx, log_id)
                 │    → node._call / node._call_stream  (具体 Operator 逻辑)
                 └─ node_outputs[node_id] = dag_ctx.current_task_context

[流式输出]
  leaf_node.call_stream 返回 AsyncIterator[ModelOutput]
    → Flow Service 包装为 OpenAI SSE 格式:
         data: {"id":"...","choices":[{"delta":{"content":"Hello"}}],"model":"..."}
         data: {"id":"...","choices":[{"delta":{"content":" World"}}],"model":"..."}
         data: [DONE]
```

### 39.11 运行时错误处理

| 错误场景 | 处理方式 |
|---|---|
| 单个 Operator 执行异常 | `_execute_node` 中 try/except 捕获，设置 `TaskState.FAILED`，向上抛出 |
| DAG 未找到 | `_get_callable_task` 抛出 HTTP 404 |
| DAG 没有叶子节点 | `_get_callable_task` 抛出 ValueError |
| Chat Flow 非流式异常 | `safe_chat_flow` 捕获，返回 `ModelOutput(error_code=1)` |
| Chat Flow 流式异常 | `safe_chat_stream_flow` 捕获，yield `ModelOutput(error_code=1, text=str(e))` |
| FlowFactory 构建 DAG 失败 | 抛出 `FlowMetadataException` 或 `ValueError` |
| BranchOperator 下游全部被跳过 | 正常返回 `SKIP_DATA`，不抛异常 |

### 39.12 AWEL 核心设计总结

| 设计要素 | 实现方式 |
|---|---|
| **DAG 定义** | 声明式 JSON → FlowFactory 构建 |
| **节点通信** | DAGContext._node_to_outputs 字典 |
| **执行策略** | 深度优先递归，从叶子节点回溯到触发器 |
| **控制流** | BranchOperator + skip_node_ids 集合 |
| **流式支持** | StreamifyAbsOperator / UnstreamifyAbsOperator 转换 |
| **触发方式** | HttpTrigger（自动注册路由）/ CommonLLMHttpTrigger（Chat）/ AgentDummyTrigger（Agent） |
| **持久化** | Flow 定义存数据库，DAG 启动时加载到内存 |
| **插件扩展** | DBGPTs 目录预定义 DAG，load_dag_from_dbgpts 加载 |
| **并发安全** | DAGContext 按 event_loop_task_id 隔离 |
