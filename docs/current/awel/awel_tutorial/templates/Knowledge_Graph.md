# 知识图谱处理工作流

# 简介
与需要将向量作为数据载体的传统 Native RAG 不同，GraphRAG 需要三元组提取（实体 -> 关系 -> 实体）来构建知识图谱，因此整个知识处理过程也可以看作是知识图谱的构建过程。

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734357331126-a3a96fd7-c8fb-4208-8e3b-be798d1b73b4.png)

# 适用场景
+ 需要使用 GraphRAG 能力挖掘知识之间的关系以进行多步推理。
+ 弥补 Naive RAG 在召回上下文方面的完整性不足。

# 使用方法
+ 进入 AWEL 界面，添加工作流

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734354927468-feed0ac7-e0fe-45e8-b85c-aba170084f82.png)

+ 导入知识处理模板

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734356276305-a6e03aff-ba89-40c4-be2d-f88dff29d0f5.png)

+ 调整参数并保存

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734356745373-4e449611-d0bc-4735-b142-0aebafaa34d6.png)

    - `document knowledge loading operator`：知识加载工厂，通过加载指定的文档类型，找到对应的文档处理器进行文档内容解析。
    - `Document Chunk slicing operator`：根据指定的切片参数对加载的文档内容进行切片。
    - `Knowledge Graph processing operator`：可以连接不同的知识图谱处理算子，包括原生知识图谱处理算子和社区摘要知识图谱处理算子。您还可以指定不同的图数据库进行存储。目前支持 TuGraph 数据库。

+ 注册为 HTTP POST 请求

```bash
curl --location --request POST 'http://localhost:5670/api/v1/awel/trigger/rag/knowledge/kg/process' \
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
