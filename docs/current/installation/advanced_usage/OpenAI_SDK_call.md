# OpenAI SDK 调用本地多模型
多模型服务的调用兼容 OpenAI 接口，通过 DB-GPT 部署的模型可以直接通过 OpenAI SDK 进行调用。

:::info 注意

使用此功能前，您必须首先部署模型服务，可以通过[集群部署教程](../model_service/cluster.md)进行部署。
:::

## 启动 apiserver

部署模型服务后，您需要启动 API Server。默认情况下，模型 API Server 使用端口 `8100` 启动。
```bash
dbgpt start apiserver --controller_addr http://127.0.0.1:8000 --api_keys EMPTY

```

## 验证

### cURL 验证
apiserver 启动后，可以验证服务调用。首先，我们通过 curl 进行验证。

:::tip
列出模型
:::
```bash
curl http://127.0.0.1:8100/api/v1/models \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json"
```

:::tip
对话
:::
```bash
curl http://127.0.0.1:8100/api/v1/chat/completions \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{
  "model": "Qwen/Qwen2.5-Coder-32B-Instruct", 
  "messages": [{"role": "user", "content": "hello"}]
}'
```

:::tip
流式对话
:::
```bash
curl http://127.0.0.1:8100/api/v1/chat/completions \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{
  "model": "Qwen/Qwen2.5-Coder-32B-Instruct", 
  "stream": true,
  "messages": [{"role": "user", "content": "hello"}]
}'
```

:::tip
嵌入
:::
```bash
curl http://127.0.0.1:8100/api/v1/embeddings \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{
    "model": "BAAI/bge-large-zh-v1.5",
    "input": "Hello world!"
}'
```

## 通过 OpenAI SDK 验证

```python
import openai
model = "Qwen/Qwen2.5-Coder-32B-Instruct"

client = openai.OpenAI(
  api_key="EMPTY",
  base_url="http://127.0.0.1:8100/api/v1",
)
completion = client.chat.completions.create(
  model=model,
  messages=[{"role": "user", "content": "hello"}]
)
# 打印 completion
print(completion.choices[0].message.content)
```

## （实验性）Rerank Open API

rerank API 是一个实验性功能，可用于对候选列表进行重排序。

1. 使用 cURL 验证 rerank API。
```bash
curl http://127.0.0.1:8100/api/v1/beta/relevance \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{
    "model": "bge-reranker-base",
    "query": "what is awel talk about?",
    "documents": [
      "Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application development.",
      "Autonomous agents have long been a research focus in academic and industry communities",
      "AWEL is divided into three levels in deign, namely the operator layer, AgentFream layer and DSL layer.",
      "Elon musk is a famous entrepreneur and inventor, he is the founder of SpaceX and Tesla."
    ]
}'
```

2. 使用 python 验证 rerank API。
```python
from dbgpt.rag.embedding import OpenAPIRerankEmbeddings

rerank = OpenAPIRerankEmbeddings(api_key="EMPTY", model_name="bge-reranker-base")
rerank.predict(
    query="what is awel talk about?", 
    candidates=[
        "Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application development.",
        "Autonomous agents have long been a research focus in academic and industry communities",
        "AWEL is divided into three levels in deign, namely the operator layer, AgentFream layer and DSL layer.",
        "Elon musk is a famous entrepreneur and inventor, he is the founder of SpaceX and Tesla."
    ]
)
```

输出如下：
```bash
[
 0.9685816764831543,
 3.7338297261158004e-05,
 0.03692878410220146,
 3.73825132555794e-05
]
```
