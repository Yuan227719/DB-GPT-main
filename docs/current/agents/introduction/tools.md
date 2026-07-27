# 工具概述

DB-GPT 内置了一小组工具，为**智能体数据 API** 提供支持。这些工具是数据分析、技能驱动工作流、SQL 探索、Shell 访问和 HTML 报告交付的默认执行表面。

当前的源代码位置位于：

- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`

## 内置工具

核心内置工具包括：

- `load_skill`
- `code_interpreter`
- `shell_interpreter`
- `sql_query`
- `html_interpreter`

它们作为智能体工具公开，并由智能体数据工作流使用，以完成从推理到执行再到呈现的流程。

## 工具选择指南

| 工具 | 用于 | 不用于 |
|------|------|--------|
| `load_skill` | 加载技能的指令和工作流 | 运行代码或 shell 命令 |
| `code_interpreter` | Python 分析、图表、数据框逻辑、计算 | Shell 命令或最终 HTML 渲染 |
| `shell_interpreter` | Bash/CLI 命令，如 `ls`、`grep`、`curl`、`git`、`pip` | Python 分析或技能指定的脚本执行（除非技能另有要求） |
| `sql_query` | 针对所选数据源的只读 SQL 查询 | 任何写入/更新/删除等模式变更操作 |
| `html_interpreter` | 最终 HTML 页面/报告渲染 | 通用 Python 计算或 Shell 执行 |

## 典型执行流程

对于大多数智能体数据任务，模式如下：

1. 当任务匹配可复用的技能时，使用 `load_skill`。
2. 使用 `sql_query` 检查结构化数据。
3. 使用 `code_interpreter` 进行 Python 分析、图表生成和数据整理。
4. 仅在需要真正的 Shell/CLI 工作时使用 `shell_interpreter`。
5. 使用 `html_interpreter` 作为报告或网页的最终呈现步骤。

## 重要规则

### 1. `html_interpreter` 是最终呈现工具

当用户要求：

- HTML 报告
- 网页
- 交互式报告
- 渲染后的分析交付物

最终渲染步骤应通过 `html_interpreter` 完成。

### 2. `sql_query` 是只读的

`sql_query` 仅支持安全的查询访问。它专为 `SELECT` 类型的探索而设计，不支持数据修改。

### 3. `code_interpreter` 调用是独立的

每次 `code_interpreter` 调用都独立运行。变量**不会**在调用之间持久化，因此每个代码片段必须包含自己的导入、加载逻辑和输出语句。

### 4. `shell_interpreter` 仅用于 Shell 任务

仅将 `shell_interpreter` 用于 CLI 工作流。如果某个技能特别要求其他执行路径，请遵循该技能的说明。

## 下一步

请参阅[工具资源](../modules/resource/tools.md)了解每个内置工具的详细含义、参数、示例和使用模式。
