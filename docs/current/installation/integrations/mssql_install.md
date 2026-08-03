# MSSQL

在本示例中，我们将展示如何在 DB-GPT 数据源中使用 MSSQL。使用 MSSQL 实现数据源可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，你需要安装 `dbgpt mssql datasource` 库。

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_mssql" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 准备 MSSQL

准备 MSSQL 数据库服务，参考 [MSSQL 安装文档](https://docs.microsoft.com/en-us/sql/database-engine/install-windows/install-sql-server?view=sql-server-ver15)。

然后运行以下命令启动 Web 服务器：
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

你也可以使用以下命令启动 Web 服务器：
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### MSSQL 配置
<p align="left">
  <img src={'https://github.com/user-attachments/assets/2798aaf7-b16f-453e-844a-6ad5dec1d58f'} width="1000px"/>
</p>
