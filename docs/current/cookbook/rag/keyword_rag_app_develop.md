# 关键词搜索 RAG 用户手册

在本示例中，我们将展示如何在 DB-GPT 中使用全文搜索 RAG 框架。使用传统的全文搜索实现 RAG 可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

您可以参考源代码中的 Python 示例文件 `DB-GPT/examples/rag/keyword_rag_example.py`。此示例演示了如何从文档中加载知识并持久化到全文存储中，随后通过在全文存储中搜索关键词来回溯与您问题相关的知识。

### 向量检索的局限性
向量检索具有明显的优势，但该技术也有一些局限性：
- **计算密集** — 为整个文档语料库生成向量并基于向量相似性进行查询，比关键词索引和匹配需要更多的处理能力。如果系统未进行适当优化，延迟可能会成为问题。
- **需要大量训练数据** — 像 BERT 这样的模型所做的语义连接依赖于在大量多样化数据集上的长时间训练。对于专业语料库，这些数据可能不易获得，从而限制了向量的质量。
- **对精确关键词查询效果较差** — 当查询包含清晰、精确的关键词和意图时，向量搜索增加的价值有限。搜索"apple fruit"可能会比仅搜索"apple"返回更差的结果，因为向量更关注整体含义而非关键词。

### 如何在向量检索和关键词检索之间选择？
何时向量搜索优于关键词搜索，反之亦然？以下是一些最佳实践：

**何时使用向量搜索：**
- 研究初期，查询意图模糊或宽泛
- 需要理解概念和主题而非关键词
- 探索信息需求宽松的主题
- 用户搜索查询更接近对话风格
- 向量搜索的语义能力使其在这些用例中表现出色。即使用户对某个主题的关键词或理解有限，也能引导用户朝正确的方向前进。

**何时使用关键词搜索：**
- 寻找非常具体的内容且已了解该主题
- 研究范围狭窄，目标明确
- 查询包含品牌名称等独特的专有名词
- 需要快速结果而非全面的相关性
- 对于精确或时效性强的查询，关键词搜索将高效定位确切术语。向量搜索可能会进行不必要的语义扩展。

搜索方法应与用户的意图和特定需求保持一致。向量搜索用于探索，关键词搜索用于精确。两者都可用时，用户可以获得两全其美的体验。

### 安装依赖

首先，您需要安装 `dbgpt` 库。

```bash
pip install "dbgpt[rag]>=0.5.8"
````

### 准备全文检索引擎

`Elasticsearch` 是 Elastic Stack 核心的分布式搜索和分析引擎。Logstash 和 Beats 便于收集、聚合和丰富您的数据并将其存储在 Elasticsearch 中。Kibana 使您能够交互式地探索、可视化和分享对数据的洞察，并管理和监控整个栈。Elasticsearch 是索引、搜索和分析魔法发生的地方。
参考 https://www.elastic.co/guide/en/elasticsearch/reference/current/elasticsearch-intro.html

安装 Elasticsearch 参考 https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html

### 关键词搜索配置

在 `.env` 文件中设置以下变量，让 DB-GPT 知道如何连接到全文检索引擎存储。

```
ELASTICSEARCH_URL=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=dbgpt
```

### 加载到全文检索引擎

当使用 `Elasticsearch` 全文引擎作为底层知识存储平台时，需要构建文档倒排索引以方便文档的归档和检索。

以下代码演示了如何创建到 Elasticsearch 搜索引擎的连接。
```python
from dbgpt_ext.storage.full_text.elasticsearch import ElasticDocumentConfig, \
    ElasticDocumentStore
def _create_es_connector():
    """Create es connector."""
    config = ElasticDocumentConfig(
        name="keyword_rag_test",
        uri="localhost",
        port="9200",
        user="elastic",
        password="dbgpt",
    )

    return ElasticDocumentStore(config)
```

### 从全文检索引擎进行关键词检索

关键词检索是一种从大量文档中检索相关信息的简单高效方式。它基于全文检索引擎 Elasticsearch。用户可以输入查询并基于查询检索最相关的文档。
```python
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.assembler import EmbeddingAssembler
from dbgpt_ext.rag.knowledge import KnowledgeFactory

async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    keyword_store = _create_es_connector()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        index_store=keyword_store,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    chunks = await retriever.aretrieve_with_scores("what is awel talk about", 0.3)
    print(f"keyword rag example results:{chunks}")
```

### 通过关键词 RAG 进行知识对话

这里我们演示如何通过 Web 页面使用关键词 RAG 实现知识对话。

首先，使用 `全文检索` 类型创建知识库。上传知识文档并等待分片完成。

<p align="left">
  <img src={'/img/chat_knowledge/keyword_rag/create_keyword_rag.jpg'} width="1000px"/>
</p>

基于关键词 RAG 开始知识对话。
<p align="left">
  <img src={'/img/chat_knowledge/keyword_rag/keyword_search_chat.jpg'} width="1000px"/>
</p>
