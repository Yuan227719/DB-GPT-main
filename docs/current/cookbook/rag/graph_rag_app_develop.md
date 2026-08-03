# Graph RAG 用户手册

在本示例中，我们将展示如何在 DB-GPT 中使用 Graph RAG 框架。使用图数据库实现 RAG 可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

您可以参考源代码中的 Python 示例文件 `DB-GPT/examples/rag/graph_rag_example.py`。此示例演示了如何从文档中加载知识并存储到图存储中，随后通过在图中搜索三元组来回溯与您问题相关的知识。

### 安装依赖

首先，您需要安装 `dbgpt` 库。

```bash
uv sync --all-packages --frozen \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
--extra "graph_rag"
````

### 准备图数据库

为了将知识存储在图中，我们需要一个图数据库。[TuGraph](https://github.com/TuGraph-family/tugraph-db) 是 DB-GPT 支持的首个图数据库。

访问 TuGraph 的 GitHub 仓库查看[快速开始](https://tugraph-db.readthedocs.io/zh-cn/latest/3.quick-start/1.preparation.html#id5)文档，按照说明拉取 TuGraph 数据库 Docker 镜像（最新版或版本 >= 4.5.1）并启动。

```
docker pull tugraph/tugraph-runtime-centos7:4.5.1
docker run -d -p 7070:7070  -p 7687:7687 -p 9090:9090 --name tugraph_demo tugraph/tugraph-runtime-centos7:latest lgraph_server -d run --enable_plugin true
```

Bolt 协议的默认端口是 `7687`。

> **下载提示：**
> 
> OSS 上也有相应版本的 TuGraph Docker 镜像包。您也可以直接下载并导入。
> 
> ```
> wget 'https://tugraph-web.oss-cn-beijing.aliyuncs.com/tugraph/tugraph-4.5.1/tugraph-runtime-centos7-4.5.1.tar' -O tugraph-runtime-centos7-4.5.1.tar
> docker load -i tugraph-runtime-centos7-4.5.1.tar
> ```

### 准备 LLM

要构建 Graph RAG 程序，我们需要一个 LLM。以下是 DB-GPT 支持的一些 LLM：

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI(API)', value: 'openai'},
    {label: 'YI(API)', value: 'yi_proxy'},
    {label: 'API Server(cluster)', value: 'model_service'},
  ]}>
  <TabItem value="openai">

然后在环境变量 `OPENAI_API_KEY` 中设置您的 API 密钥。

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient()
```
  </TabItem>

  <TabItem value="yi_proxy">

您需要有一个 YI 账户并从 YI 官方网站获取 API 密钥。

然后在环境变量 `YI_API_KEY` 中设置您的 API 密钥。

  </TabItem>

  <TabItem value="model_service">

如果您已部署 [DB-GPT 集群](/docs/installation/model_service/cluster) 和
[API 服务器](/docs/installation/advanced_usage/OpenAI_SDK_call)
，您可以连接到 API 服务器获取 LLM 模型。

该 API 与 OpenAI API 兼容，因此您可以使用 OpenAILLMClient 连接到 API 服务器。

首先您需要安装 `openai` 库。
```bash
pip install openai
```

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient(api_base="http://localhost:8100/api/v1/", api_key="{your_api_key}")
```
  </TabItem>
</Tabs>

### TuGraph 配置

在 `.env` 文件中设置以下变量，让 DB-GPT 知道如何连接到 TuGraph。

```
GRAPH_STORE_TYPE=TuGraph
TUGRAPH_HOST=127.0.0.1
TUGRAPH_PORT=7687
TUGRAPH_USERNAME=admin
TUGRAPH_PASSWORD=73@TuGraph
GRAPH_COMMUNITY_SUMMARY_ENABLED=True  # 启用图谱社区摘要
TRIPLET_GRAPH_ENABLED=True  # 启用三元组图谱搜索
DOCUMENT_GRAPH_ENABLED=True  # 启用文档和块的图搜索
KNOWLEDGE_GRAPH_CHUNK_SEARCH_TOP_SIZE=5  # 每次检索搜索的三元组数量
KNOWLEDGE_GRAPH_EXTRACTION_BATCH_SIZE=20  # 从文本中提取三元组的批处理大小
COMMUNITY_SUMMARY_BATCH_SIZE=20  # 并行社区摘要处理的批处理大小
```

### 加载到知识图谱

当使用图数据库作为底层知识存储平台时，需要构建知识图谱以方便文档的归档和检索。DB-GPT 利用大语言模型的能力实现集成的知识图谱，同时保持灵活性，可以自由连接到其他知识图谱系统和图数据库系统。

我们基于 `CommunitySummaryKnowledgeGraph` 创建了带有图谱社区摘要的知识图谱。

```python
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.storage.knowledge_graph.community_summary import (
    CommunitySummaryKnowledgeGraph,
    CommunitySummaryKnowledgeGraphConfig,
)

llm_client = OpenAILLMClient()
model_name = "gpt-4o-mini"

def __create_community_kg_connector():
    """创建社区知识图谱连接器。"""
    return CommunitySummaryKnowledgeGraph(
        config=CommunitySummaryKnowledgeGraphConfig(
            name="community_graph_rag_test",
            embedding_fn=DefaultEmbeddingFactory.openai(),
            llm_client=llm_client,
            model_name=model_name,
            graph_store_type="TuGraphGraph",
        ),
    )
```

### 从知识图谱检索

然后您可以从知识图谱中检索知识，这与向量存储的检索方式相同。

```python
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.core import Chunk, HumanPromptTemplate, ModelMessage, ModelRequest
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.assembler import EmbeddingAssembler
from dbgpt_ext.rag.knowledge import KnowledgeFactory
from dbgpt.rag.retriever import RetrieverStrategy

async def test_community_graph_rag():
    await __run_graph_rag(
        knowledge_file="examples/test_files/graphrag-mini.md",
        chunk_strategy="CHUNK_BY_MARKDOWN_HEADER",
        knowledge_graph=__create_community_kg_connector(),
        question="What's the relationship between TuGraph and DB-GPT ?",
    )

async def __run_graph_rag(knowledge_file, chunk_strategy, knowledge_graph, question):
    file_path = os.path.join(ROOT_PATH, knowledge_file).format()
    knowledge = KnowledgeFactory.from_file_path(file_path)
    try:
        chunk_parameters = ChunkParameters(chunk_strategy=chunk_strategy)

        # 获取 embedding 组装器
        assembler = await EmbeddingAssembler.aload_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            index_store=knowledge_graph,
            retrieve_strategy=RetrieverStrategy.GRAPH,
        )
        await assembler.apersist()

        # 获取 embedding 检索器
        retriever = assembler.as_retriever(1)
        chunks = await retriever.aretrieve_with_scores(question, score_threshold=0.3)

        # 聊天
        print(f"{await ask_chunk(chunks[0], question)}")

    finally:
        knowledge_graph.delete_vector_name(knowledge_graph.get_config().name)

async def ask_chunk(chunk: Chunk, question) -> str:
    rag_template = (
        "Based on the following [Context] {context}, "
        "answer [Question] {question}."
    )
    template = HumanPromptTemplate.from_template(rag_template)
    messages = template.format_messages(context=chunk.content, question=question)
    model_messages = ModelMessage.from_base_messages(messages)
    request = ModelRequest(model=model_name, messages=model_messages)
    response = await llm_client.generate(request=request)

    if not response.success:
        code = str(response.error_code)
        reason = response.text
        raise Exception(f"request llm failed ({code}) {reason}")

    return response.text
```

### 通过 GraphRAG 进行知识对话

> 注意：当前测试数据为中文。

这里我们演示如何通过 Web 页面使用 Graph RAG 实现知识对话。

首先，使用 `知识图谱` 类型创建知识库。

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/create_knowledge_graph.png'} width="1000px"/>
</p>

然后，上传文档（[graphrag-test.md](https://github.com/eosphoros-ai/DB-GPT/blob/main/examples/test_files/graphrag-test.md)）并自动处理（默认按 markdown 标题分片）。

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/upload_file.png'} width="1000px"/>
</p>

索引完成后，图谱数据可能如下所示。
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/graph_data.png'} width="1000px"/>
</p>

开始进行知识图谱对话。
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/graph_rag_chat.png'} width="1000px"/>
</p>

### 性能测试

性能测试基于 `gpt-4o-mini` 模型。

#### 索引性能

|                     | DB-GPT                | GraphRAG(microsoft)  |
| ------------------- | --------------------- | -------------------- |
| 文档 Tokens          | 42631                 | 42631                |
| 三元组图谱           | 734 个节点, 1064 条边 | 779 个节点, 967 条边 |
| 文档结构图           | 76 个节点, 1090 条边  | N/A                  |
| Prompt Tokens       | 375768                | 744990               |
| Completion Tokens   | 41797                 | 227230               |
| 总 Tokens           | **417565**            | 972220               |
| 索引时间            | **170s**              | 210s                 |

#### 查询性能

**全局搜索**

|        | DB-GPT | GraphRAG(microsoft) |
| ------ | ------ | ------------------- |
| 时间   | 8s     | 40s                 |
| Tokens | 7432   | 63317               |

**问题**
```
请总结知识库的内容，并进行摘要说明。
```

- **DB-GPT 回答**

```
· 知识图谱概述: 知识图谱集中展示了与图数据库及相关处理系统的多种实体和其相互关联，涵盖了分布式内存图数据库、图计算模型及多种图处理框架和技术，强调了这些技术在图处理· 领域中的应用和相互影响。
· TuGraph DB: TuGraph DB是一种高效的图数据库，支持大数据容量和低延迟查找，具备ACID特性。其社区版适用于学习和小型项目，支持实时数据管理和多图结构。
· DB-GPT: DB-GPT是一个私有化的LLM技术数据库交互方式，支持多种高级功能，旨在推动数据3.0时代的到来。它提供了多模型管理、信息检索优化和智能体协作等功能。
· 应用领域: 知识库中提到的图技术应用于金融风控、社交网络和数据分析等多个领域，展示了图数据库的快速发展及其在各行各业中的重要性。
· 开发者生态: 知识库还强调了开发者在开源项目中的活跃表现，尤其是在Apache Flink和Spark等项目中的贡献，表明了良好的合作与开发生态。
整体而言，知识库展示了图数据库及其相关技术的广泛应用和快速进步，强调了DB-GPT和TuGraph等工具在数据智能和处理中的重要角色。
```

- **GraphRAG(microsoft) 回答**

```
知识库内容总结
概述
  知识库涵盖了与图处理相关的多个社区和框架，强调了这些实体在推动技术解决方案和协作努力中的重要性。主要关注的领域包括图处理、人工智能开发和开源贡献。
关键实体
  1. 图处理框架：知识库中提到的多个重要框架，如 GraphChi、X-Stream、GraphQ、PowerLyra、Gemini 和 TuGraph，均在处理大规模图数据方面发挥了重要作用。这些框架的相互关联性表明了一个促进创新的协作环境。
  2. 企业贡献：一些主要企业如 Ant Group、Google、Tencent 和 Alibaba 在图处理和数据管理技术的发展中扮演了关键角色。它们的合作关系强调了在推动技术创新方面的伙伴关系的重要性。
  3. 开源项目：Apache 软件基金会的多个开源项目（如 Apache Hudi、Iceberg、Pulsar 和 Kafka）展示了全球开发者的贡献，增强了数据管理和分析能力。
发展趋势
  知识库还指出了动态图处理、人工智能驱动的数据库管理和自动化工具集成等新兴趋势，这些趋势对于提高现代软件开发的效率和有效性至关重要。
结论
  整体而言，知识库展示了一个充满活力的技术生态系统，其中各个实体通过合作和创新共同推动图处理和相关技术的发展。这种相互联系的网络不仅促进了技术的进步，也为解决复杂的技术挑战提供了支持。
```

**局部搜索**

|        | DB-GPT | GraphRAG(microsoft) |
| ------ | ------ | ------------------- |
| 时间   | 15s    | 15s                 |
| Tokens | 9230   | 11619               |

**问题**

```
DB-GPT社区和TuGraph社区在社区贡献，社区生态，开发者的这几个方面的联系和区别分别是什么？
```

- **DB-GPT 回答**

```
· 社区贡献:
  · DB-GPT社区: 由多个开发者和公司支持，开发者积极参与代码提交、审查和问题反馈，展现出强大的社区协作能力。主要合作项目包括Langchain-Chatchat、LLaMA-Factory、FastChat等。
  · TuGraph社区: 吸引了众多开发者参与，专注于提升TuGraph DB的功能和性能，与多个开源工具共同开发，形成了活跃的贡献模式。
· 社区生态:
  · DB-GPT社区: 主要围绕私有化LLM技术数据库交互方式，支持多种高级功能，促进数据智能应用开发，构建了一个以AI和数据处理为核心的生态。
  · TuGraph社区: 依托于图数据库领域，尤其是TuGraph DB和TuGraph Analytics，形成了以大数据处理和实时计算为核心的生态，涉及多个行业应用，如金融风控和社交网络。
· 开发者:
  · DB-GPT社区: 包含多个GitHub用户，开发者主要集中在AI和数据处理领域，积极参与开源项目的开发和维护。
  · TuGraph社区: 涉及来自不同国家的开发者，特别是在图数据库和大数据分析领域的专业人员，强调多领域协作与贡献。
总体来看，DB-GPT社区和TuGraph社区在贡献方式和生态领域有所不同，前者更侧重于AI和数据交互技术，后者则专注于图数据库技术及其应用。
```

- **GraphRAG(microsoft) 回答**
```
DB-GPT社区与TuGraph社区的比较
  DB-GPT社区和TuGraph社区在多个方面展现了各自的特点和贡献，尤其是在社区贡献、生态系统和开发者参与等方面。以下是对这两个社区的联系与区别的详细分析。
社区贡献
  DB-GPT社区
    DB-GPT社区围绕DB-GPT框架展开，整合了多个组织和资源，致力于AI和数据驱动应用的开发。该社区的主要贡献者包括Hiyouga、LM-Sys和Langchain-AI等组织，这些组织通过合作推动AI模型和应用的发展。DB-GPT的开发者们积极参与知识共享和技术创新，推动了AI应用的多样化和实用性。
  TuGraph社区
    TuGraph社区则专注于图数据库的开发，尤其是TuGraph及其相关项目。该社区的贡献者包括Ant Group和Tsinghua University等，致力于提供高效的图数据管理和分析解决方案。TuGraph社区的开发者们通过开源项目和技术文档，促进了图数据库技术的普及和应用。
社区生态
  DB-GPT社区
    DB-GPT社区的生态系统是一个多元化的合作网络，涵盖了多个组织和技术平台。该社区通过整合不同的技术和数据源，支持从聊天系统到企业报告等多种应用，展现出其在AI领域的广泛适用性。DB-GPT的生态系统强调了组织间的协作与知识共享，促进了技术的快速发展。
  TuGraph社区
    相较之下，TuGraph社区的生态系统更为专注于图数据的管理和分析。TuGraph及其相关项目（如TuGraph DB和TuGraph Analytics）共同构成了一个完整的图技术体系，支持大规模数据的实时处理和复杂分析。该社区的生态系统强调了图数据库在金融、工业和政务服务等领域的应用，展现了其在特定行业中的深度影响。
开发者参与
  DB-GPT社区
    在DB-GPT社区中，开发者的参与主要体现在对AI应用的开发和优化上。社区内的开发者通过贡献代码、参与讨论和解决问题，推动了DB-GPT框架的不断完善。该社区的开发者们来自不同国家和地区，展现了全球范围内对AI技术的关注和参与。
  TuGraph社区
    TuGraph社区的开发者则主要集中在图数据库的构建和优化上。该社区的开发者们通过GitHub等平台积极参与项目的开发、代码审查和问题解决，推动了TuGraph技术的进步。TuGraph社区的开发者们同样来自中国及其他国家，展现了对图数据管理技术的广泛兴趣。
总结
  总体而言，DB-GPT社区和TuGraph社区在社区贡献、生态系统和开发者参与等方面各具特色。DB-GPT社区更侧重于AI应用的多样性和组织间的合作，而TuGraph社区则专注于图数据的高效管理和分析。两者的共同点在于都强调了开源和社区合作的重要性，推动了各自领域的技术进步和应用发展。
```

### 文档结构检索

在 DB-GPT 0.6.1 版本中，我们新增了一个功能：
- 结合**文档结构检索**的三元组检索

我们扩展了 GraphRAG 中 'Graph' 的定义范围：
```
知识图谱 = 三元组图谱 + 文档结构图谱
```

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/image_graphrag_0_6_1.png'} width="1000px"/>
</p>

得益于文档结构图谱，GraphRAG 现在可以在回答时提供原文引用：

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/doc_structure_graph_demo.png'} width="1000px"/>
</p>

如何实现？

我们将标准格式文件（目前对 Markdown 文件支持最好）基于其层次结构和布局信息分解为有向图，并存储在数据库中。在此图中：
- 每个节点代表文件的一个块
- 每条边代表原始文档中不同块之间的结构关系
- 将文档结构图合并到三元组图谱中

下一步是什么？

我们的目标是构建更复杂的图，覆盖更全面的信息，以支持 GraphRAG 中更复杂的检索算法。

### GraphRAG 中的相似性搜索：

在 DB-GPT 的最新版本中，我们实现了一个新功能：

- GraphRAG 检索的**相似性搜索**

#### 如何使用？

使用 TuGraph 4.5.1 及以上版本。

在 `.env` 文件中设置以下变量以启用 DB-GPT 中的相似性搜索。

```
SIMILARITY_SEARCH_ENABLED=True # 启用实体和块的相似性搜索
KNOWLEDGE_GRAPH_EMBEDDING_BATCH_SIZE=20 # 文本嵌入的批处理大小
KNOWLEDGE_GRAPH_SIMILARITY_SEARCH_TOP_SIZE=5 # 设置向量相似性搜索的 topk
KNOWLEDGE_GRAPH_SIMILARITY_SEARCH_RECALL_SCORE=0.3 # 设置向量相似性搜索的召回分数
```

此外，您需要在 `.env` 文件中选择一个 embedding 模型。

```
## Openai embedding model, 参见 dbgpt/model/parameter.py
# EMBEDDING_MODEL=proxy_openai
# proxy_openai_proxy_server_url=https://api.openai.com/v1
# proxy_openai_proxy_api_key={your-openai-sk}
# proxy_openai_proxy_backend=text-embedding-ada-002

## qwen embedding model, 参见 dbgpt/model/parameter.py
# EMBEDDING_MODEL=proxy_tongyi
# proxy_tongyi_proxy_backend=text-embedding-v1
# proxy_tongyi_proxy_api_key={your-api-key}

## qianfan embedding model, 参见 dbgpt/model/parameter.py
#EMBEDDING_MODEL=proxy_qianfan
#proxy_qianfan_proxy_backend=bge-large-zh
#proxy_qianfan_proxy_api_key={your-api-key}
#proxy_qianfan_proxy_api_secret={your-secret-key}
```

#### 为什么使用？

TuGraph 现在提供全面的向量能力，包括向量存储、索引和相似性搜索功能。这些功能使 GraphRAG 能够实现比传统基于关键词的方法更优越的检索性能。

为了利用这些能力，我们在实体和块对象中引入了 `_embedding` 字段来存储 embedding 数据，使相似性搜索能够为给定查询识别最相关的结果。

#### 相似性搜索结果对比

在相同环境下，给定相同的文档和问题，关键词模式的结果如下：

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/comparison_result_for_keywords.png'} width="1000px"/>
</p>

相似性搜索模式的结果如下：

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/comparison_result_for_similarity_search.png'} width="1000px"/>
</p>

与关键词搜索方法相比，相似性搜索方法可以覆盖更全面的信息。例如，在处理"清北大学"这个术语时，关键词搜索模式难以提取有用关键词，而相似性搜索模式可以识别相似词汇，从而检索到与清华大学相关的信息并将其包含在搜索结果中。

这意味着在查询不精确的场景下，与基于关键词的搜索模式相比，相似性搜索方法可以检索到更多相关信息。

此外，如下图所示，与 RAG 相比，带有相似性搜索的 GraphRAG 可以获取更多相关信息，确保更丰富的回答。

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/comparison_with_rag.png'} width="1000px"/>
</p>

总之，在 GraphRAG 中启用相似性搜索可以显著扩展其响应的范围和相关性。

### GraphRAG 中的 Text2GQL 搜索：

在 DB-GPT 的最新版本中，我们实现了一个新功能：

- 用于 GraphRAG 检索的 **Text2GQL 搜索**

#### 如何使用？

在 `.env` 文件中设置以下变量以启用 DB-GPT 中的 text2gql 搜索。

```
TEXT2GQL_SEARCH_ENABLED=True # 启用以搜索实体和关系的 text2gql
```

#### 为什么使用？

基于关键词或向量的检索会生成大型多跳子图供 LLM 总结信息，但当用户提出的问题可以通过单个图查询简单表达时，这种方法成本较高。Text2GQL 搜索可以有效降低图搜索成本，并在上述情况下提高检索子图的准确性。

未来，我们希望通过基于 prompt 和微调的方法，进一步提高 Text2GQL 翻译的能力，以在复杂问题上与基于关键词或向量的检索相竞争。

#### Text2GQL 搜索结果对比

在相同环境下，给定相同的文档和问题，关键词模式的结果如下：

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/comparison_result_for_keywords_search.png'} width="1000px"/>
</p>

text2gql 搜索模式的结果如下：

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/comparison_result_for_text2gql_search.png'} width="1000px"/>
</p>

与关键词搜索方法相比，text2gql 搜索方法可以生成精确的图查询语言来查询知识图谱中 DB-GPT 的实体，即：

```cypher
MATCH (n) WHERE n.id = 'DB-GPT' RETURN n LIMIT 10
```

这意味着在问题可以通过单个图查询表达的场景下，text2gql 搜索方法可以以更低的成本检索到更准确的信息。

总之，在 GraphRAG 中启用 text2gql 搜索可以在问题简洁明了时显著提高准确性并降低成本。
