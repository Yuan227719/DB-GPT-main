# 使用 AWEL 构建 RAG

在本示例中，我们将展示如何使用 AWEL 库创建一个 RAG 程序。

现在，让我们创建一个 Python 文件 `first_rag_with_awel.py`。

在本示例中，我们将从 URL 加载知识并将其存储到向量存储中。

### 安装依赖

首先，您需要安装 `dbgpt` 库。

```bash
pip install "dbgpt[agent,simple_framework, client]>=0.7.1" "dbgpt_ext>=0.7.1" -U
```

### 准备 Embedding 模型

为了将知识存储到向量存储中，我们需要一个 embedding 模型，DB-GPT 支持多种 embedding 模型，以下是一些示例：

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI(API)', value: 'openai'},
    {label: 'text2vec(local)', value: 'text2vec'},
    {label: 'Embedding API Server(cluster)', value: 'remote_embedding'},
  ]}>
  <TabItem value="openai">
```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.openai()
```
  </TabItem>

  <TabItem value="text2vec">

```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.default("/data/models/text2vec-large-chinese")
```
  </TabItem>

  <TabItem value="remote_embedding">

如果您已经部署了 [DB-GPT 集群](/docs/installation/model_service/cluster) 和 [API 服务器](/docs/installation/advanced_usage/OpenAI_SDK_call)，您可以连接到 API 服务器来获取 embeddings。

```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.remote(
  api_url="http://localhost:8100/api/v1/embeddings",
  api_key="{your_api_key}",
  model_name="text2vec"
)
```
  </TabItem>
</Tabs>

### 加载知识并存储到向量存储

然后我们可以创建一个 DAG，从 URL 加载知识并存储到向量存储中。

```python
import asyncio
import shutil
from dbgpt.core.awel import DAG
from dbgpt_ext.rag import ChunkParameters
from dbgpt.rag.knowledge import KnowledgeType
from dbgpt_ext.rag.operators import EmbeddingAssemblerOperator
from dbgpt_ext.rag.operators.knowledge import KnowledgeOperator
from dbgpt_ext.storage.vector_store.chroma_store import ChromaStore, ChromaVectorConfig

# 删除旧的向量存储目录(/tmp/awel_rag_test_vector_store)
shutil.rmtree("/tmp/awel_rag_test_vector_store", ignore_errors=True)

vector_store = ChromaStore(
    vector_store_config=ChromaVectorConfig(
        persist_path="/tmp/awel_rag_test_vector_store"
    ),
    name="test_vstore",
    embedding_fn=embeddings
)

with DAG("load_knowledge_dag") as knowledge_dag:
    # 从 URL 加载知识
    knowledge_task = KnowledgeOperator(knowledge_type=KnowledgeType.URL.name)
    assembler_task = EmbeddingAssemblerOperator(
        index_store=vector_store,
        chunk_parameters=ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    )
    knowledge_task >> assembler_task

chunks = asyncio.run(assembler_task.call("https://docs.dbgpt.site/docs/awel/"))
print(f"Chunk length: {len(chunks)}")
```

### 从向量存储检索知识

然后您可以从向量存储中检索知识。

```python

from dbgpt.core.awel import MapOperator
from dbgpt.rag.operators import EmbeddingRetrieverOperator

with DAG("retriever_dag") as retriever_dag:
    retriever_task = EmbeddingRetrieverOperator(
        top_k=3,
        index_store=vector_store,
    )
    content_task = MapOperator(lambda cks: "\n".join(c.content for c in cks))
    retriever_task >> content_task

chunks = asyncio.run(content_task.call("What is the AWEL?"))
print(chunks)
```

### 准备 LLM

为了构建一个 RAG 程序，我们需要一个 LLM，以下是 DB-GPT 支持的一些 LLM：

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI(API)', value: 'openai'},
    {label: 'YI(API)', value: 'yi_proxy'},
    {label: 'API Server(cluster)', value: 'model_service'},
  ]}>
  <TabItem value="openai">

首先，您需要安装 `openai` 库。

```bash
pip install openai
```
然后在环境变量中设置您的 API 密钥 `OPENAI_API_KEY`。

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient()
```
  </TabItem>

  <TabItem value="yi_proxy">

您需要拥有一个 YI 账户并从 YI 官方网站获取 API 密钥。

首先，您需要安装 `openai` 库。

```bash
pip install openai
```

然后在环境变量中设置您的 API 密钥 `YI_API_KEY`。

```python
from dbgpt.model.proxy import YiLLMClient

llm_client = YiLLMClient()
```
  </TabItem>

  <TabItem value="model_service">

如果您已经部署了 [DB-GPT 集群](/docs/installation/model_service/cluster) 和 [API 服务器](/docs/installation/advanced_usage/OpenAI_SDK_call)，您可以连接到 API 服务器来获取 LLM 模型。

该 API 与 OpenAI API 兼容，因此您可以使用 OpenAILLMClient 连接到 API 服务器。

首先，您需要安装 `openai` 库。
```bash
pip install openai
```

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient(api_base="http://localhost:8100/api/v1/", api_key="{your_api_key}")
```
  </TabItem>
</Tabs>

### 创建 RAG 程序

最后，我们可以使用检索到的知识创建一个 RAG。

```python

from dbgpt.core.awel import InputOperator, JoinOperator, InputSource
from dbgpt.core.operators import PromptBuilderOperator, RequestBuilderOperator
from dbgpt.model.operators import LLMOperator

prompt = """根据以下已知信息，为用户提供专业、简洁的问题回答。
如果无法从提供的内容中获得答案，请说：
"知识库中提供的信息不足以回答这个问题。"
禁止随意编造信息。回答时，最好按1.2.3点进行总结。
          已知信息：
          {context}
          问题：
          {question}
"""

with DAG("llm_rag_dag") as rag_dag:
    input_task = InputOperator(input_source=InputSource.from_callable())
    retriever_task = EmbeddingRetrieverOperator(
        top_k=3,
        index_store=vector_store,
    )
    content_task = MapOperator(lambda cks: "\n".join(c.content for c in cks))
    
    merge_task = JoinOperator(lambda context, question: {"context": context, "question": question})
    
    prompt_task = PromptBuilderOperator(prompt)
    # 模型为 gpt-3.5-turbo，您可以替换为其他模型。
    req_build_task = RequestBuilderOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(llm_client=llm_client)
    result_task = MapOperator(lambda r: r.text)

    input_task >> retriever_task >> content_task >> merge_task
    input_task >> merge_task

    merge_task >> prompt_task >> req_build_task >> llm_task >> result_task

print(asyncio.run(result_task.call("What is the AWEL?")))
```
输出将是：

```bash
AWEL stands for Agentic Workflow Expression Language, which is a set of intelligent agent workflow expression language designed for large model application development. It simplifies the process by providing functionality and flexibility through its layered API design architecture, including the operator layer, AgentFrame layer, and DSL layer. Its goal is to allow developers to focus on business logic for LLMs applications without having to deal with intricate model and environment details.
```

恭喜！您已经使用 AWEL 创建了一个 RAG 程序。

### 完整代码

让我们看看 `first_rag_with_awel.py` 的完整代码：

```python
import asyncio
import shutil
from dbgpt.core.awel import DAG, MapOperator, InputOperator, JoinOperator, InputSource
from dbgpt.core.operators import PromptBuilderOperator, RequestBuilderOperator
from dbgpt_ext.rag import ChunkParameters
from dbgpt.rag.knowledge import KnowledgeType
from dbgpt_ext.rag.operators.embedding import EmbeddingAssemblerOperator, EmbeddingRetrieverOperator
from dbgpt_ext.rag.operators import KnowledgeOperator
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt_ext.storage.vector_store.chroma_store import ChromaStore, ChromaVectorConfig
from dbgpt.model.operators import LLMOperator
from dbgpt.model.proxy import OpenAILLMClient

# 这里我们使用 openai embedding 模型，如果您想使用其他模型，可以按照前面的示例进行替换。
embeddings = DefaultEmbeddingFactory.openai()
# 这里我们使用 openai LLM 模型，如果您想使用其他模型，可以按照前面的示例进行替换。
llm_client = OpenAILLMClient()

# 删除旧的向量存储目录(/tmp/awel_rag_test_vector_store)
shutil.rmtree("/tmp/awel_rag_test_vector_store", ignore_errors=True)

vector_store = ChromaStore(
    vector_store_config=ChromaVectorConfig(
        persist_path="/tmp/awel_rag_test_vector_store",
    ),
    name="test_vstore",
    embedding_fn=embeddings
)

with DAG("load_knowledge_dag") as knowledge_dag:
    # 从 URL 加载知识
    knowledge_task = KnowledgeOperator(knowledge_type=KnowledgeType.URL.name)
    assembler_task = EmbeddingAssemblerOperator(
        index_store=vector_store,
        chunk_parameters=ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    )
    knowledge_task >> assembler_task

chunks = asyncio.run(assembler_task.call("https://docs.dbgpt.site/docs/awel/"))
print(f"Chunk length: {len(chunks)}\n")

prompt = """根据以下已知信息，为用户提供专业、简洁的问题回答。
如果无法从提供的内容中获得答案，请说：
"知识库中提供的信息不足以回答这个问题。"
禁止随意编造信息。回答时，最好按1.2.3点进行总结。
          已知信息：
          {context}
          问题：
          {question}
"""

with DAG("llm_rag_dag") as rag_dag:
    input_task = InputOperator(input_source=InputSource.from_callable())
    retriever_task = EmbeddingRetrieverOperator(
        top_k=3,
        index_store=vector_store,
    )
    content_task = MapOperator(lambda cks: "\n".join(c.content for c in cks))

    merge_task = JoinOperator(
        lambda context, question: {"context": context, "question": question})

    prompt_task = PromptBuilderOperator(prompt)
    # 模型为 gpt-3.5-turbo，您可以替换为其他模型。
    req_build_task = RequestBuilderOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(llm_client=llm_client)
    result_task = MapOperator(lambda r: r.text)

    input_task >> retriever_task >> content_task >> merge_task
    input_task >> merge_task

    merge_task >> prompt_task >> req_build_task >> llm_task >> result_task

print(asyncio.run(result_task.call("What is the AWEL?")))
```

### 可视化 DAG

我们可以使用以下代码可视化 DAG：

```python
knowledge_dag.visualize_dag()
rag_dag.visualize_dag()
```
如果在 Jupyter Notebook 中执行代码，您可以在笔记本中看到 DAG。

```python
display(knowledge_dag.show())
display(rag_dag.show())
```

`knowledge_dag` 的图示如下：

<p align="left">
  <img src={'/img/awel/cookbook/first_rag_knowledge_dag.png'} width="1000px"/>
</p>

`rag_dag` 的图示如下：
<p align="left">
  <img src={'/img/awel/cookbook/first_rag_rag_dag.png'} width="1000px"/>
</p>
