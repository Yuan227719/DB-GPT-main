# 快速开始

AWEL（Agentic Workflow Expression Language）使构建复杂的 LLM 应用变得简单，它提供了强大的功能和灵活性。

## 使用 AWEL 的基础示例：HTTP 请求 + 输出重写

AWEL 的基本用法是构建一个 HTTP 请求并重写某些输出值。让我们通过一个示例来了解其工作原理。

### DAG 规划
首先，让我们看一个 AWEL 基础编排的入门示例。该示例的核心功能是处理 HTTP 请求的输入和输出。因此，整个编排只包含两个步骤：
- HTTP 请求
- 处理 HTTP 响应结果

在 DB-GPT 中，已经封装了一些基础的依赖算子，可以直接引用。

```python
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
```

### 自定义算子

定义一个接受两个参数（name 和 age）的 HTTP 请求体。

```python
class TriggerReqBody(BaseModel):
    name: str = Field(..., description="用户名")
    age: int = Field(18, description="用户年龄")
```

定义一个名为 `RequestHandleOperator` 的请求处理器算子，它是一个扩展自基础 `MapOperator` 的算子。`RequestHandleOperator` 的操作非常简单：解析请求体，提取 name 和 age 字段，然后将它们拼接成一个句子。例如：

> "Hello, zhangsan, your age is 18."

```python
class RequestHandleOperator(MapOperator[TriggerReqBody, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> str:
        print(f"Receive input value: {input_value}")
        return f"Hello, {input_value.name}, your age is {input_value.age}"
```

### DAG 管道

编写完上述算子后，可以将它们组装成一个 DAG 编排。这个 DAG 共有两个节点：第一个节点是 `HttpTrigger`，主要负责处理 HTTP 请求（该算子是 DB-GPT 内置的），第二个节点是新定义的 `RequestHandleOperator`，用于处理请求体。下面的 DAG 代码可以将这两个节点连接起来。

```python
with DAG("simple_dag_example") as dag:
    trigger = HttpTrigger("/examples/hello", request_body=TriggerReqBody)
    map_node = RequestHandleOperator()
    trigger >> map_node
```

### 访问验证

在执行访问验证之前，需要先启动项目：`python dbgpt/app/dbgpt_server.py`

```bash
% curl -X GET http://127.0.0.1:5670/api/v1/awel/trigger/examples/hello\?name\=zhangsan
"Hello, zhangsan, your age is 18"
```

当然，为了方便用户测试，我们还提供了一个测试环境。该测试环境无需启动 dbgpt_server 即可进行测试。在 simple_dag_example 下方添加以下代码，然后直接运行 simple_dag_example.py 脚本即可执行测试脚本，无需启动项目。

```python
if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # 开发模式，可以在本地运行 DAG 进行调试。
        from dbgpt.core.awel import setup_dev_environment
        setup_dev_environment([dag], port=5555)
    else:
        # 生产模式，DB-GPT 启动后将自动加载并执行当前文件。
        pass
```

```bash
curl -X GET http://127.0.0.1:5555/api/v1/awel/trigger/examples/hello\?name\=zhangsan
"Hello, zhangsan, your age is 18"
```

[simple_dag_example](/examples/awel/simple_dag_example.py)
