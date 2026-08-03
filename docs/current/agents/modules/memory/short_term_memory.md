# 短期记忆

短期记忆临时缓冲最近的感知信息，它接收部分感觉记忆，并可通过其他观察结果或检索到的记忆得到**增强**，从而进入长期记忆。

在大多数情况下，短期记忆类似于受 LLM 上下文窗口限制的输入信息。因此，你可以认为短期记忆在大多数情况下会被写入 LLM 的提示词中。

## 使用短期记忆

```python
from dbgpt.agent import AgentMemory, ShortTermMemory

# 创建一个 Agent 记忆，包含一个短期记忆
memory = ShortTermMemory(buffer_size=2)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```

与感觉记忆类似，短期记忆也有缓冲区大小，当缓冲区满时，它会保留最新的 buffer_size 条记忆，部分被丢弃的记忆将被转移到长期记忆。

默认的短期记忆是一种 `FIFO` 缓冲记忆，这里我们不再过多介绍。

## 增强型短期记忆

类似于人类的短期记忆，DB-GPT Agent 中的短期记忆可以通过外部观测结果得到增强。这里我们介绍一种增强型短期记忆，称为 `EnhancedShortTermMemory`，它通过比较新观测结果与现有记忆之间的相似度来增强记忆。

要使用 `EnhancedShortTermMemory`，你需要提供一个嵌入模型。

### 准备嵌入模型

DB-GPT 支持多种嵌入模型，以下是一些示例：

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
import os
from dbgpt.rag.embedding import DefaultEmbeddingFactory

api_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
api_key = os.getenv("OPENAI_API_KEY")
embeddings = DefaultEmbeddingFactory.openai(api_url=api_url, api_key=api_key)
```
  </TabItem>

  <TabItem value="text2vec">

```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.default("/data/models/text2vec-large-chinese")
```
</TabItem>

<TabItem value="remote_embedding">

如果你已经部署了 [DB-GPT 集群](../../../installation/model_service/cluster) 和 [API 服务](../../../installation/advanced_usage/OpenAI_SDK_call)，你可以连接到 API 服务来获取嵌入向量。

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

### 使用增强型短期记忆

```python
from concurrent.futures import ThreadPoolExecutor
from dbgpt.agent import AgentMemory, EnhancedShortTermMemory

# 创建一个 Agent 记忆，包含一个短期记忆
memory = EnhancedShortTermMemory(
    embeddings=embeddings,
    buffer_size=2,
    enhance_similarity_threshold=0.5,
    enhance_threshold=3,
    executor=ThreadPoolExecutor(),
)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```

在 DB-GPT 中，核心接口是异步和非阻塞的，因此我们使用 `ThreadPoolExecutor` 在单独的线程中运行相似度计算，以获得更好的性能。

在上述代码中，我们将 `enhance_similarity_threshold` 设置为 `0.5`，这意味着如果相似度大于 `0.7`，新的观测结果有概率被增强到短期记忆中（增强过程中存在随机因素）。我们将 `enhance_threshold` 设置为 `3`，这意味着如果记忆被增强的次数大于或等于 `3` 次，它将被转移到长期记忆。

然后，你可以在 Agent 中使用增强型短期记忆。
