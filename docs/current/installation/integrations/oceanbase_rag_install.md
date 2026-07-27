# OceanBase Vector RAG

在本示例中，我们将展示如何在 DB-GPT RAG 存储中使用 OceanBase Vector。使用向量数据库实现 RAG 可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，你需要安装 `dbgpt OceanBase Vector storage` 库。

```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_obvector" \
--extra "dbgpts"
````

### 准备 OceanBase Vector

准备 OceanBase Vector 数据库服务，参考 [OceanBase Vector](https://open.oceanbase.com/)。

### OceanBase 配置

在 `configs/dbgpt-proxy-openai.toml` 文件中设置以下 rag 存储变量，让 DB-GPT 知道如何连接到 OceanBase Vector。

```
[rag.storage]
[rag.storage.vector]
type = "oceanbase"
uri = "127.0.0.1"
port = "19530"
#username="dbgpt"
#password=19530
```

然后运行以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

你也可以使用以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```
