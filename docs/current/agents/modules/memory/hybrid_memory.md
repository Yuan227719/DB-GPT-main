# 混合记忆

> 这种结构显式地建模了人类的短期记忆和长期记忆。短期记忆临时缓冲最近的感知信息，而长期记忆随时间推移巩固重要信息。

例如，短期记忆包含 Agent 当前情境的上下文信息，而长期记忆存储 Agent 过去的行为和思考，可以根据当前事件进行检索。

## 创建混合记忆

### 方法 1：使用默认值创建混合记忆

将使用 OpenAI Embedding API 和 ChromaStore 作为默认值。

```python
import shutil
from dbgpt.agent import HybridMemory, AgentMemory

# 删除旧的向量存储目录(/tmp/tmp_ltm_vector_store)
shutil.rmtree("/tmp/tmp_ltm_vector_store", ignore_errors=True)
hybrid_memory = HybridMemory.from_chroma(
    vstore_name="agent_memory", vstore_path="/tmp/tmp_ltm_vector_store"
)

agent_memory: AgentMemory = AgentMemory(memory=hybrid_memory)
```

### 方法 2：使用自定义值创建混合记忆

混合记忆需要创建感觉记忆、短期记忆和长期记忆。

**准备嵌入模型**

你可以根据 [准备嵌入模型](./short_term_memory#prepare-embedding-model) 准备嵌入模型。

这里我们以 OpenAI Embedding API 为例：

```python
import os
from dbgpt.rag.embedding import DefaultEmbeddingFactory

api_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
api_key = os.getenv("OPENAI_API_KEY")
embeddings = DefaultEmbeddingFactory.openai(api_url=api_url, api_key=api_key)
```

**准备向量存储**

你需要准备一个向量存储，这里我们以 `ChromaStore` 为例：
```python

import shutil
from dbgpt_ext.storage.vector_store.chroma_store import ChromaVectorConfig, ChromaStore

# 删除旧的向量存储目录(/tmp/tmp_ltm_vector_store)
shutil.rmtree("/tmp/tmp_ltm_vector_store", ignore_errors=True)
vector_store = ChromaStore(
    ChromaVectorConfig(
        persist_path="/tmp/tmp_ltm_vector_store",
    ),
    name="ltm_vector_store",
    embedding_fn=embeddings
)
```

**创建混合记忆**

```python
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from dbgpt.agent import (
    SensoryMemory,
    EnhancedShortTermMemory,
    LongTermMemory,
    HybridMemory,
    AgentMemory,
)

executor = ThreadPoolExecutor()

sensor_memory = SensoryMemory(buffer_size=2)

short_term_memory = EnhancedShortTermMemory(
    embeddings=embeddings,
    buffer_size=2,
    enhance_similarity_threshold=0.7,
    enhance_threshold=3,
    executor=executor,
)

long_term_memory = LongTermMemory(
    executor=ThreadPoolExecutor(), vector_store=vector_store, _default_importance=0.5
)

hybrid_memory = HybridMemory(
    now=datetime.now(),
    sensory_memory=sensor_memory,
    short_term_memory=short_term_memory,
    long_term_memory=long_term_memory,
)

agent_memory: AgentMemory = AgentMemory(memory=hybrid_memory)
```

### 方法 3：从向量存储创建混合记忆

你可以从向量存储创建混合记忆，它将使用默认值用于感觉记忆和短期记忆。

```python
from dbgpt.agent import HybridMemory, AgentMemory

hybrid_memory = HybridMemory.from_vstore(
    vector_store=vector_store, embeddings=embeddings
)

agent_memory: AgentMemory = AgentMemory(memory=hybrid_memory)
```

## 工作原理

写入记忆片段时：
1. 混合记忆首先将记忆片段存储在感觉记忆中，如果感觉记忆已满，它将丢弃所有感觉记忆片段，部分被丢弃的记忆片段将被转移到短期记忆。
2. 短期记忆将接收部分感觉记忆作为外部观测结果，短期记忆中的记忆片段可以被其他观测结果增强。部分被增强的记忆片段将转移到长期记忆，同时，这些被增强的记忆将被反思为更高级别的思考和洞察，并存入长期记忆。
3. 长期记忆将存储 Agent 的经验和知识。当它接收来自短期记忆的记忆片段时，会计算记忆片段的重要性，然后写入向量存储。

读取记忆片段时：
1. 首先，混合记忆将根据观测结果从长期记忆中读取记忆片段。长期记忆使用 `TimeWeightedEmbeddingRetriever` 来检索记忆片段（最近的记忆片段具有更高的权重）。
2. 检索到的记忆片段将被保存到短期记忆中（仅用于增强记忆片段，不会向短期记忆追加新的记忆片段）。检索到的记忆片段与所有短期记忆片段合并后，作为当前记忆提供给 LLM。增强过程完成后，部分新的短期记忆片段将被转移到长期记忆。
