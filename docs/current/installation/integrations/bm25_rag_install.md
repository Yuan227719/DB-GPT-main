# BM25 RAG

在此示例中，我们将展示如何在 DB-GPT RAG 存储中使用 Elasticsearch。使用 Elasticsearch 数据库实现 RAG 可以在一定程度上缓解由 Elasticsearch 数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，您需要安装 `dbgpt elasticsearch storage` 库。

```bash
uv sync --all-packages --frozen \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_elasticsearch" \
--extra "dbgpts"
````

### 准备 Elasticsearch

准备 Elasticsearch 数据库服务，参考 - [Elasticsearch 安装](https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html)。

### Elasticsearch 配置

在 `configs/dbgpt-bm25-rag.toml` 文件中设置以下 rag 存储变量，让 DB-GPT 知道如何连接到 Elasticsearch。

```
[rag.storage]
[rag.storage.full_text]
type = "ElasticSearch"
uri = "127.0.0.1"
port = "9200"
```

然后运行以下命令启动 webserver：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-bm25-rag.toml
```

或者
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-bm25-rag.toml
```
