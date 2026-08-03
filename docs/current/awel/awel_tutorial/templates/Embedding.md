# 嵌入处理工作流

# 简介
传统的 Native RAG 知识提取准备流程旨在将文档转化为数据库的过程，包括读取非结构化文档 -> 知识切片 -> 文档切片转换 -> 导入向量数据库。

# 适用场景
+ 支持简单的智能问答场景，通过语义相似度召回上下文信息。
+ 用户可以根据自己的业务场景裁剪和添加已有的嵌入处理流程。

# 使用方法
+ 进入 AWEL 界面，添加工作流

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734354927468-feed0ac7-e0fe-45e8-b85c-aba170084f82.png)

+ 导入知识处理模板

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734358060884-672d3157-a2ee-498b-887e-ea51f1caddae.png)

+ 调整参数并保存

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734358170081-32d38282-7765-4bbf-9bf7-c068550907d1.png)

    - `document knowledge loading operator`：知识加载工厂，通过加载指定的文档类型，找到对应的文档处理器进行文档内容解析。
    - `Document Chunk Manager operator`：根据指定的切片参数对加载的文档内容进行切片。
    - `Vector storage machining operator`：可以连接不同的向量数据库进行向量存储，也可以连接不同的 Embedding 模型和服务进行向量提取。

+ 注册为 HTTP POST 请求

```bash
curl --location --request POST 'http://localhost:5670/api/v1/awel/trigger/rag/knowledge/embedding/process' \
--header 'Content-Type: application/json' \
--data-raw '{}'
```

```bash
[
    {
        "content": "\"What is AWEL?\": Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application\ndevelopment. It provides great functionality and flexibility. Through the AWEL API, you can focus on the development of business logic for LLMs applications\nwithout paying attention to cumbersome model and environment details.  \nAWEL adopts a layered API design. AWEL's layered API design architecture is shown in the figure below.  \n<p align=\"left\">\n<img src={'/img/awel.png'} width=\"480px\"/>\n</p>",
        "metadata": {
            "Header1": "What is AWEL?",
            "source": "../../docs/docs/awel/awel.md"
        },
        "chunk_id": "c1ffa671-76d0-4c7a-b2dd-0b08dfd37712",
        "chunk_name": "",
        "score": 0.0,
        "summary": "",
        "separator": "\n",
        "retriever": null
    },...
  ]
```
