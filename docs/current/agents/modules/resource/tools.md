# 内置工具

DB-GPT 在 **Agentic Data API** 中提供了一小组内置工具。

这些工具是以下功能的核心执行层：

- 加载可复用的技能
- 运行 Python 分析
- 执行 shell 命令
- 查询结构化数据
- 渲染 HTML 报告

实现来源：

- `packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`

## 内置工具

- [load_skill](./tools/load-skill.md)
- [code_interpreter](./tools/code-interpreter.md)
- [shell_interpreter](./tools/shell-interpreter.md)
- [sql_query](./tools/sql-query.md)
- [html_interpreter](./tools/html-interpreter.md)

## 推荐执行顺序

### 技能驱动的工作流

1. `load_skill`
2. `sql_query` 或 `code_interpreter`
3. `html_interpreter` 用于最终交付

### 结构化数据工作流

1. `sql_query`
2. `code_interpreter`
3. `html_interpreter`

### Shell 辅助工作流

1. `shell_interpreter`
2. `code_interpreter`
3. `html_interpreter`（如果结果需要渲染）

## 工具选择指南

| 工具 | 适用场景 | 避免场景 |
|------|----------|----------|
| `load_skill` | 加载技能指令和工作流定义 | 运行代码或 shell 命令 |
| `code_interpreter` | Python 分析、计算、图表、数据处理 | Shell 命令或最终 HTML 渲染 |
| `shell_interpreter` | CLI 命令和环境检查 | Python 分析或最终报告渲染 |
| `sql_query` | 只读 SQL 探索 | 写入、架构变更、破坏性 SQL |
| `html_interpreter` | 最终 HTML 页面/报告渲染 | 计算或 shell 执行 |
