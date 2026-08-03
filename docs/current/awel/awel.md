# 什么是 AWEL？

Agentic Workflow Expression Language（AWEL）是一套专门为大模型应用开发设计的智能体工作流表达式语言。它提供了强大的功能和灵活性。通过 AWEL API，您可以专注于 LLM 应用的业务逻辑开发，而无需关注繁琐的模型和环境细节。

AWEL 采用分层 API 设计。AWEL 的分层 API 设计架构如下图所示。

<p align="left">
  <img src={'/img/awel.png'} width="480px"/>
</p>

## AWEL 设计

AWEL 在设计上分为三个层级，分别是算子层（operator layer）、AgentFream 层和 DSL 层。以下是对这三个层级的简要介绍。

- **算子层（Operator layer）**
算子层是指在 LLM 应用开发过程中最基础的操作原子，例如在开发 RAG 应用时，检索、向量化、模型交互、提示词处理等都属于基础算子。在后续的开发中，框架将进一步抽象和标准化算子的设计。基于标准 API 可以快速实现一组算子。

- **AgentFream 层**
AgentFream 层对算子进行了进一步封装，可以基于算子进行链式计算。该层的链式计算还支持分布式，支持 filter、join、map、reduce 等一系列链式计算操作。未来将支持更多的计算逻辑。

- **DSL 层**
DSL 层提供了一套标准的结构化表示语言，通过编写 DSL 语句即可完成 AgentFream 和算子的操作，使得围绕数据编写大模型应用更加确定性，避免了使用自然语言编写的不确定性，使得围绕数据的应用编程成为确定性应用编程。

## 示例
AWEL 的初步版本已经发布，我们提供了一些内置的使用示例。

## 算子

### API-RAG 示例
您可以在 `examples/awel/simple_rag_example.py` 找到[源代码](https://github.com/eosphoros-ai/DB-GPT/blob/main/examples/awel/simple_rag_example.py)
```python
with DAG("simple_rag_example") as dag:
    trigger_task = HttpTrigger(
        "/examples/simple_rag", methods="POST", request_body=ConversationVo
    )
    req_parse_task = RequestParseOperator()
    # TODO should register prompt template first
    prompt_task = PromptManagerOperator()
    history_storage_task = ChatHistoryStorageOperator()
    history_task = ChatHistoryOperator()
    embedding_task = EmbeddingEngingOperator()
    chat_task = BaseChatOperator()
    model_task = ModelOperator()
    output_parser_task = MapOperator(lambda out: out.to_dict()["text"])

    (
        trigger_task
        >> req_parse_task
        >> prompt_task
        >> history_storage_task
        >> history_task
        >> embedding_task
        >> chat_task
        >> model_task
        >> output_parser_task
    )

```
位运算将以 DAG 的形式编排整个流程。

<p align="left">
  <img src={'/img/awel_dag_flow.png'} width="360px" />
</p>

#### LLM + 缓存示例

<p align="left">
  <img src={'/img/awel_cache_flow.png'} width="360px" />
</p>

### AgentFream 示例
```python
af = AgentFream(HttpSource("/examples/run_code", method = "post"))
result = (
    af
    .text2vec(model="text2vec")
    .filter(vstore, store = "chromadb", db="default")
    .llm(model="vicuna-13b", temperature=0.7)
    .map(code_parse_func)
    .map(run_sql_func)
    .reduce(lambda a, b: a + b)
)
result.write_to_sink(type='source_slink')
```

### DSL 示例

``` python
CREATE WORKFLOW RAG AS
BEGIN
    DATA requestData = RECEIVE REQUEST FROM 
    		http_source("/examples/rags", method = "post");
        
    DATA processedData = TRANSFORM requestData USING embedding(model = "text2vec");
    DATA retrievedData = RETRIEVE DATA 
    		FROM vstore(database = "chromadb", key = processedData)
    		ON ERROR FAIL;
        
    DATA modelResult = APPLY LLM "vicuna-13b" 
    		WITH DATA retrievedData AND PARAMETERS (temperature = 0.7)
    		ON ERROR RETRY 2 TIMES;
        
    RESPOND TO http_source WITH modelResult
    		ON ERROR LOG "Failed to respond to request";
END;
```

## 当前支持的算子
- **基础算子**
    - BaseOperator
    - JoinOperator
    - ReduceOperator
    - MapOperator
    - BranchOperator
    - InputOperator
    - TriggerOperator
- **流式算子**
    - StreamifyAbsOperator
    - UnstreamifyAbsOperator
    - TransformStreamAbsOperator

## 可执行环境
- 单机环境
- Ray 环境
