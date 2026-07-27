# DuckDB

DuckDB 是一个高性能的分析型数据库系统。它被设计用于快速高效地执行分析型 SQL 查询，并且也可以作为嵌入式分析数据库使用。

在本示例中，我们将展示如何在 DB-GPT 数据源中使用 DuckDB。使用 DuckDB 实现数据源可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，你需要安装 `dbgpt duckdb datasource` 库。

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_duckdb" \
--extra "rag" \
--extra "storage_chromadb" \

```

### 准备 DuckDB

准备 DuckDB 数据库服务，参考 [DuckDB 安装文档](https://duckdb.org/docs/installation)。

然后运行以下命令启动 Web 服务器：
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml

```

你也可以使用以下命令启动 Web 服务器：
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml

```

### DuckDB 配置
<p align="left">
  <img src={'https://github.com/user-attachments/assets/bc5ffc20-4b5b-4e24-8c29-bf5702b0e840'} width="1000px"/>
</p>
