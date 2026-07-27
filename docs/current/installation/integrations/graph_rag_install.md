# Graph RAG

在本示例中，我们将展示如何在 DB-GPT 中使用 Graph RAG 框架。使用图数据库实现 RAG 可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

你可以参考源代码中的 Python 示例文件 `DB-GPT/examples/rag/graph_rag_example.py`。该示例演示了如何从文档中加载知识并将其存储到图存储中。随后，通过在图存储中搜索三元组来回溯与你的问题相关的知识。

### 安装依赖

首先，你需要安装 `dbgpt graph_rag` 库。

```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts" \
--extra "graph_rag"
````

### 准备图数据库

为了将知识存储在图数据库中，我们需要一个图数据库。[TuGraph](https://github.com/TuGraph-family/tugraph-db) 是 DB-GPT 支持的第一个图数据库。

访问 TuGraph 的 GitHub 仓库查看[快速入门](https://tugraph-db.readthedocs.io/zh-cn/latest/3.quick-start/1.preparation.html#id5)文档，按照说明拉取 TuGraph 数据库 Docker 镜像（latest / 版本 >= 4.5.1）并启动它。

```
docker pull tugraph/tugraph-runtime-centos7:4.5.1
docker run -d -p 7070:7070  -p 7687:7687 -p 9090:9090 --name tugraph_demo tugraph/tugraph-runtime-centos7:latest lgraph_server -d run --enable_plugin true
```

bolt 协议的默认端口是 `7687`。

> **下载提示：**
> 
> OSS 上也有对应版本的 TuGraph Docker 镜像包。你也可以直接下载并导入。
> 
> ```
> wget 'https://tugraph-web.oss-cn-beijing.aliyuncs.com/tugraph/tugraph-4.5.1/tugraph-runtime-centos7-4.5.1.tar' -O tugraph-runtime-centos7-4.5.1.tar
> docker load -i tugraph-runtime-centos7-4.5.1.tar
> ```

### TuGraph 配置

在 `configs/dbgpt-graphrag.toml` 文件中设置以下变量，让 DB-GPT 知道如何连接到 TuGraph。

```
[rag.storage.graph]
type = "TuGraph"
host="127.0.0.1"
port=7687
username="admin"
password="73@TuGraph"
enable_summary="True"
enable_similarity_search="True"
```

然后运行以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-graphrag.toml
```

你也可以使用以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```
