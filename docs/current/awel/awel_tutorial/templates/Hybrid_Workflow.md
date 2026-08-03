# 混合知识处理工作流

# 简介
目前，DB-GPT 知识库提供了如 `文档上传` -> `解析` -> `切片` -> `Embedding` -> `知识图谱三元组提取` -> `向量数据库存储` -> `图数据库存储` 等知识处理能力，但它不具备从文档中提取复杂信息的能力，包括同时从文档块中进行向量提取和知识图谱提取。混合知识处理模板定义了复杂的知识处理工作流，它同时支持文档向量提取、关键词提取和知识图谱提取。

# 适用场景
+ 不局限于传统的单一知识处理流程（仅 Embedding 处理或知识图谱提取处理），知识处理工作流同时实现 Embedding 和知识图谱提取，作为混合知识召回检索的数据存储。
+ 用户可以根据自己的业务场景裁剪和添加已有的知识处理流程。

# 使用方法
+ 进入 AWEL 界面，添加工作流

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734354927468-feed0ac7-e0fe-45e8-b85c-aba170084f82.png)

+ 导入知识处理模板

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734357236704-5a15be65-3d11-4406-98d7-efb82e5142dc.png)

+ 调整参数并保存

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734355123947-3e252e59-2b2a-4bca-adef-13a93ee6cdf3.png)

    - `Document knowledge loading operator`：知识加载工厂，通过加载指定的文档类型，找到对应的文档处理器进行文档内容解析。
    - `Document Chunk slicing operator`：根据指定的切片参数对加载的文档内容进行切片。
    - `Knowledge Processing branch operator`：可以连接不同的知识处理流程，包括知识图谱处理流程、向量处理流程和关键词处理流程。
    - `Vector storage machining operator`：可以连接不同的向量数据库进行向量存储，也可以连接不同的 Embedding 模型和服务进行向量提取。
    - `Knowledge Graph processing operator`：可以连接不同的知识图谱处理算子，包括原生知识图谱处理算子和社区摘要知识图谱处理算子。您还可以指定不同的图数据库进行存储。目前支持 TuGraph 数据库。
    - `Result aggregation operator`：汇总向量提取和知识图谱提取的结果。

+ 注册为 HTTP POST 请求

```bash
curl --location --request POST 'http://localhost:5670/api/v1/awel/trigger/rag/knowledge/hybrid/process' \
--header 'Content-Type: application/json' \
--data-raw '{}'
```

```bash
[
    "async persist vector store success 1 chunks.",
    "async persist graph store success 1 chunks."
]
```
