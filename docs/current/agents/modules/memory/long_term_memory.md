# 长期记忆

> 短期记忆包含 Agent 当前情境的上下文信息，而长期记忆存储 Agent 过去的行为和思考，可以根据当前事件进行检索。

> 长期记忆类似于外部向量存储，Agent 可以根据需要快速查询和检索。

在 DB-GPT 中，长期记忆默认存储在向量存储中。

## 使用长期记忆

要使用长期记忆，你需要提供一个向量存储。

### 准备嵌入模型

首先，你需要准备一个嵌入模型，用于将文本转换为向量。你可以根据 [准备嵌入模型](./short_term_memory#prepare-embedding-model) 准备嵌入模型。

这里我们以 OpenAI Embedding API 为例：

```python
import os
from dbgpt.rag.embedding import DefaultEmbeddingFactory

api_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
api_key = os.getenv("OPENAI_API_KEY")
embeddings = DefaultEmbeddingFactory.openai(api_url=api_url, api_key=api_key)
```

### 准备向量存储

然后你需要准备一个向量存储，这里我们以 `ChromaStore` 为例：

安装 `chroma` 包，使用以下命令：

```bash
pip install chromadb
```

```python

import shutil
from dbgpt_ext.storage.vector_store.chroma_store import ChromaVectorConfig, ChromaStore

# 删除旧的向量存储目录(/tmp/tmp_ltm_vector_store)
shutil.rmtree("/tmp/tmp_ltm_vector_store", ignore_errors=True)
vector_store = ChromaStore(
    vector_store_config=ChromaVectorConfig(
        persist_path="/tmp/tmp_ltm_vector_store",
    ),
    name="ltm_vector_store",
    embedding_fn=embeddings,
)
```

### 使用长期记忆

```python
from concurrent.futures import ThreadPoolExecutor
from dbgpt.agent import AgentMemory, LongTermMemory

# 创建一个 Agent 记忆，包含一个长期记忆
memory = LongTermMemory(
    executor=ThreadPoolExecutor(), vector_store=vector_store, _default_importance=0.5
)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```

在上述代码中，`_default_importance` 表示一个记忆片段的默认重要性，因为我们直接使用 `LongTermMemory`，所以需要设置默认重要性。
