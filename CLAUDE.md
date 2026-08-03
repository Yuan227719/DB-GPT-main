# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概述

DB-GPT 是一个开源的智能体 AI 数据助手（v0.8.1），用于构建 AI + 数据产品。它可以连接数据库、CSV/Excel、数据仓库和知识库；用户可以用自然语言提问；系统会在沙箱环境中自动执行 SQL/Python 分析。

## 构建与开发命令

本项目使用 **uv** 管理依赖，使用 **make** 编排任务。需要 Python >= 3.10。

### 环境搭建
```bash
uv sync --all-packages --extra "base" --extra "proxy_openai" --extra "rag" --extra "storage_chromadb" --extra "dbgpts"
uv run pre-commit install
```

### 代码质量
```bash
make fmt          # 格式化代码 + 排序 import（ruff）
make fmt-check    # 仅检查格式，不做修改
make mypy         # 类型检查（仅 dbgpt-core）
make pre-commit   # 依次执行 fmt-check、test、test-doc、mypy
```

### 测试
```bash
make test         # 运行单元测试（pytest --pyargs dbgpt）
make test-doc     # 运行 doctest
make coverage     # 运行测试并生成覆盖率报告
```

测试目录为 `tests/`：`unit_tests/` 覆盖 agent、embedding_engine、graph、llms、vector_store；`intetration_tests/` 覆盖 benchmark、datasource、graph_store、kbqa、transformer、vector_store。

### 构建与发布
```bash
make build        # uv build --all-packages
make publish      # 构建并上传到 PyPI
make clean        # 清理虚拟环境和缓存
```

### Web 前端（`web/`）
```bash
cd web
npm run dev       # 开发服务器（Next.js）
npm run build     # 生产构建
npm run lint      # ESLint 检查
npm run format    # Prettier 格式化
```

## 架构

DB-GPT 是一个 **Python monorepo**，在 `packages/` 下通过 uv workspaces 管理 7 个包：

| 包 | 职责 |
|---------|---------|
| `dbgpt-core` | 核心抽象层：LLM 接口、存储接口、消息、嵌入、AWEL 工作流引擎 |
| `dbgpt-serve` | REST API 服务层（agent、conversation、datasource、flow、model、rag、prompt 等服务） |
| `dbgpt-app` | FastAPI 应用服务器、组件配置、场景管理、初始化/数据库迁移 |
| `dbgpt-client` | 客户端 SDK，提供与 OpenAI 兼容的接口 |
| `dbgpt-ext` | 具体实现层：数据源连接器、存储后端、RAG、LLM 提供商、可视化 |
| `dbgpt-sandbox` | 沙箱化代码/工具执行环境 |
| `dbgpt-accelerator` | 性能加速模块（自动检测、flash attention） |

依赖链：`dbgpt-app` → `dbgpt-serve` → `dbgpt-ext` → `dbgpt-core`。上层依赖核心抽象，不依赖具体实现。

### 核心架构模式

- **SystemApp（组件系统）**：`dbgpt-core` 中的集中式依赖注入容器。组件向 `SystemApp` 注册，由它统一管理生命周期（初始化/启动/停止），消除循环依赖。
- **AWEL（智能体工作流表达语言）**：位于 `dbgpt-core/core/awel/`，基于 DAG 的声明式工作流编排。支持可视化工作流创建、并行/串行执行和事件驱动触发。
- **Provider 模式**：core 定义接口（LLM、存储、嵌入）；`dbgpt-ext` 在这些接口背后提供具体实现。新提供商通过 pyproject.toml 中的 optional extras 注册。
- **插件式可选依赖**：存储后端（ChromaDB、Milvus）、数据源连接器（MySQL 等）和 LLM 提供商作为可选 extras 安装，避免依赖冲突。

### 关键目录
- `configs/` — 18 个示例 TOML 配置文件，对应不同 LLM 后端（OpenAI、DeepSeek、Ollama、vLLM、本地模型等）
- `docs/` — Docusaurus 文档站点
- `examples/` — 示例 notebook 和脚本
- `i18n/` — 国际化
- `docker/` — Docker 构建文件；根目录的 `docker-compose.yml` 用于编排
- `.devcontainer/` — VS Code Dev Container 配置
