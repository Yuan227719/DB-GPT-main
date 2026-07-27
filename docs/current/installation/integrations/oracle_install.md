# Oracle

在本示例中，我们将展示如何在 DB-GPT 数据源中使用 Oracle。使用 Oracle 实现数据源可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，你需要安装 `dbgpt oracle datasource` 库。

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_oracle" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 准备 Oracle

准备 Oracle 数据库服务，参考 [Oracle 安装文档](https://docs.oracle.com/en/database/oracle/oracle-database/index.html)。

然后运行以下命令启动 Web 服务器：
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

你也可以使用以下命令启动 Web 服务器：
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### Oracle 配置
<p align="left">
  <img src={'https://github.com/user-attachments/assets/c285f8c3-9e99-4fab-bd39-ae34206ec54f'} width="1000px"/>
</p>
