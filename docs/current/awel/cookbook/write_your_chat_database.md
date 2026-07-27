# 使用 AWEL 编写您自己的 Chat Data

在本指南中，我们将向您展示如何使用 `AWEL` 编写您自己的 `Chat Data`，就像 DB-GPT 中的 `Chat Data` 场景一样。

本指南稍微进阶一些，可能需要一些时间来理解。如果您有任何问题，请随时在 [DB-GPT issues](https://github.com/eosphoros-ai/DB-GPT/issues) 中提出。

## 简介

`Chat Data` 是**与您的数据库对话**。其目标是通过自然语言与数据库进行交互，包括以下步骤：

1. **构建知识库**：解析数据库模式和其他信息来构建知识库。
2. **与数据库对话**：通过自然语言与数据库进行对话。

**与数据库对话**的一些步骤：
1. **检索相关信息**：根据用户的查询从数据库中检索相关信息。
2. **生成响应**：将相关信息和用户查询传递给 LLM，然后生成包含 SQL 和其他信息的响应。
3. **执行 SQL**：执行 SQL 获取最终结果。
4. **可视化结果**：可视化结果并返回给用户。

在本指南中，我们主要关注步骤 1、2 和 3。

## 安装依赖

首先，您需要安装 `dbgpt` 库。

```bash
pip install "dbgpt[rag, agent, client, simple_framework]>=0.7.0" "dbgpt_ext>=0.7.0" -U
pip install openai
```

## 构建知识库

### 准备 Embedding 模型

首先，您需要准备 embedding 模型，您可以按照[准备 Embedding 模型](./first_rag_with_awel.md#prepare-embedding-model)来提供 embedding 模型。

这里我们使用 OpenAI 的 embedding 模型。

```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.openai()
```

### 准备数据库

这里我们创建一个简单的 SQLite 数据库。

```python
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteTempConnector

db_conn = SQLiteTempConnector.create_temporary_db()
db_conn.create_temp_tables(
    {
        "user": {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "name": "TEXT",
                "age": "INTEGER",
            },
            "data": [
                (1, "Tom", 10),
                (2, "Jerry", 16),
                (3, "Jack", 18),
                (4, "Alice", 20),
                (5, "Bob", 22),
            ],
        }
    }
)
```

### 将数据库模式存储到向量存储

```python

import asyncio
import shutil
from dbgpt.core.awel import DAG, InputOperator
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.operators.db_schema import DBSchemaAssemblerOperator
from dbgpt_ext.storage.vector_store.chroma_store import ChromaVectorConfig, ChromaStore

# 删除旧的向量存储目录(/tmp/awel_with_data_vector_store)
shutil.rmtree("/tmp/awel_with_data_vector_store", ignore_errors=True)

vector_store = ChromaStore(
    ChromaVectorConfig(
        persist_path="/tmp/tmp_ltm_vector_store",
    ),
    name="ltm_vector_store",
    embedding_fn=embeddings,
)

with DAG("load_schema_dag") as load_schema_dag:
    input_task = InputOperator.dummy_input()
    # 将数据库模式加载到向量存储
    assembler_task = DBSchemaAssemblerOperator(
        connector=db_conn,
        table_vector_store_connector=vector_store,
        chunk_parameters=ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    )
    input_task >> assembler_task

chunks = asyncio.run(assembler_task.call())
print(chunks)
```

### 从向量存储检索数据库模式

```python
from dbgpt.core.awel import InputSource
from dbgpt_ext.rag.operators.db_schema import DBSchemaRetrieverOperator

with DAG("retrieve_schema_dag") as retrieve_schema_dag:
    input_task = InputOperator(input_source=InputSource.from_callable())
    # 从向量存储检索数据库模式
    retriever_task = DBSchemaRetrieverOperator(
        top_k=1,
        table_vector_store_connector=vector_store,
        field_vector_store_connector=vector_store
    )
    input_task >> retriever_task

chunks = asyncio.run(retriever_task.call("Query the name and age of users younger than 18 years old"))
print("Retrieved schema:\n", chunks)
```

## 与数据库对话

### 准备 LLM
我们使用 LLM 来生成 SQL 查询。这里我们使用 OpenAI 的 LLM 模型，您可以根据[准备 LLM](./first_rag_with_awel.md#prepare-llm)替换为其他模型。

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient()
```

### 准备一些决策

有时，我们希望 LLM 能够做出一些决策，这里我们提供了一些决策，即图表类型。

```python
antv_charts = [
    {"response_line_chart": "用于展示对比趋势分析数据"},
    {
        "response_pie_chart": "适用于比例和分布统计等场景"
    },
    {
        "response_table": "适用于显示列较多或非数值型列的场景"
    },
    # {"response_data_text":"默认显示方式，适用于单行或简单内容显示"},
    {
        "response_scatter_plot": "适用于探索变量之间的关系、检测异常值等"
    },
    {
        "response_bubble_chart": "适用于多变量之间的关系、突出异常值或特殊情况等"
    },
    {
        "response_donut_chart": "适用于层次结构表示、类别比例展示和突出关键类别等"
    },
    {
        "response_area_chart": "适用于时间序列数据可视化、多组数据比较、数据变化趋势分析等"
    },
    {
        "response_heatmap": "适用于时间序列数据可视化分析、大规模数据集、分类数据分布等"
    },
]
display_type = "\n".join(
    f"{key}:{value}" for dict_item in antv_charts for key, value in dict_item.items()
)
```

### 生成 SQL

现在，让我们将用户查询和数据库模式传递给 LLM 来生成 SQL。

```python
import asyncio
import json

from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    SystemPromptTemplate,
    SQLOutputParser
)
from dbgpt.core.awel import DAG, InputOperator, InputSource, MapOperator, JoinOperator
from dbgpt.core.operators import PromptBuilderOperator, RequestBuilderOperator
from dbgpt_ext.rag.operators.db_schema import DBSchemaRetrieverOperator
from dbgpt.model.operators import LLMOperator

system_prompt = """您是一名数据库专家。请根据用户选择的数据库以及数据库的一些可用表结构定义来回答用户的问题。
数据库名称：
    {db_name}
表结构定义：
    {table_info}
    
约束：
1.请根据用户的问题理解用户意图，并使用给定的表结构定义创建语法正确的 {dialect} sql。如果不需要 sql，请直接回答用户的问题。
2.除非用户在问题中指定了希望获取的具体数据行数，否则始终将查询结果限制在最多 {top_k} 条。
3.您只能使用表结构信息中提供的表来生成 sql。如果无法基于提供的表结构生成 sql，请说："提供的表结构信息不足以生成 sql 查询。" 禁止随意编造信息。
4.在生成 SQL 时，请注意不要弄错表和列之间的关系。
5.请检查 SQL 的正确性，并确保在正确条件下优化查询性能。
6.请从下面给出的显示方法中选择最适合数据渲染的一种，并将类型名称放入返回所需格式的 name 参数值中。如果找不到最合适的，请使用 'Table' 作为显示方法。
可用的数据显示方法如下：{display_type}
 
用户问题：
    {user_input}
请逐步思考，并按照以下 JSON 格式回答：
    {response}
确保响应是正确的 json，并且可以被 Python json.loads 解析。
"""

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "向用户说的想法总结",
    "sql": "要执行的 SQL 查询",
    "display_type": "数据显示方法",
}

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            system_prompt,
            response_format=json.dumps(
                RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4
            ),
        ),
        HumanPromptTemplate.from_template("{user_input}"),
    ]
)


with DAG("chat_data_dag") as chat_data_dag:
    input_task = InputOperator(input_source=InputSource.from_callable())
    retriever_task = DBSchemaRetrieverOperator(
        top_k=1,
        index_store=vector_store,
    )
    content_task = MapOperator(lambda cks: [c.content for c in cks]) 
    merge_task = JoinOperator(lambda table_info, ext_dict: {"table_info": table_info, **ext_dict}) 
    prompt_task = PromptBuilderOperator(prompt)
    req_build_task = RequestBuilderOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(llm_client=llm_client) 
    # 解析纯 json 响应，然后转换为 python dict
    sql_parse_task = SQLOutputParser()
 
    input_task >> MapOperator(lambda x: x["user_input"]) >> retriever_task >> content_task >> merge_task
    input_task >> merge_task
    merge_task >> prompt_task >> req_build_task >> llm_task >> sql_parse_task
 

result = asyncio.run(sql_parse_task.call({
    "user_input": "Query the name and age of users younger than 18 years old",
    "db_name": "user_management",
    "dialect": "SQLite",
    "top_k": 1,
    "display_type": display_type,
    "response": json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4)
}))

print("Result:\n", result)
```

输出将如下所示：

```bash
un_stream ai response: {
    "thoughts": "The user wants to retrieve the name and age of users who are younger than 18 years old from the 'user_management' database.",
    "sql": "SELECT name, age FROM user WHERE age < 18",
    "display_type": "response_table"
}
Result:
 {'thoughts': "The user wants to retrieve the name and age of users who are younger than 18 years old from the 'user_management' database.", 'sql': 'SELECT name, age FROM user WHERE age < 18', 'display_type': 'response_table'}
```

### 执行 SQL

让我们添加一个算子来执行之前生成的 SQL。

```python
from dbgpt.datasource.operators import DatasourceOperator

    # 之前的代码 ...
    db_query_task = DatasourceOperator(connector=db_conn)
    sql_parse_task >> MapOperator(lambda x: x["sql"]) >> db_query_task
    
    db_result = asyncio.run(db_query_task.call({
        "user_input": "Query the name and age of users younger than 18 years old",
        "db_name": "user_management",
        "dialect": "SQLite",
        "top_k": 1,
        "display_type": display_type,
        "response": json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4)
    }))
    print("The result of the query is:")
    print(db_result)
```

输出将如下所示：

```bash
un_stream ai response: {
    "thoughts": "The user wants to retrieve the names and ages of users who are younger than 18 years old from the 'user' table.",
    "sql": "SELECT name, age FROM user WHERE age < 18",
    "display_type": "response_table"
}
The result of the query is:
    name  age
0    Tom   10
1  Jerry   16
```

### 在 SQL 执行后编写自定义处理逻辑

有时，您可能希望在 SQL 执行后添加一些自定义逻辑，这里我们提供一个包含自定义算子的示例。

```python
import pandas as pd

from dbgpt.core.awel import MapOperator, BranchOperator, JoinOperator, is_empty_data


class TwoSumOperator(MapOperator[pd.DataFrame, int]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    async def map(self, df: pd.DataFrame) -> int:
        return await self.blocking_func_to_async(self._two_sum, df)
    
    def _two_sum(self, df: pd.DataFrame) -> int:
        return df['age'].sum()

def branch_even(x: int) -> bool:
    return x % 2 == 0

def branch_odd(x: int) -> bool:
    return not branch_even(x)

class DataDecisionOperator(BranchOperator[int, int]):
    def __init__(self, odd_task_name: str, even_task_name: str, **kwargs):
        super().__init__(**kwargs)
        self.odd_task_name = odd_task_name
        self.even_task_name = even_task_name
        
    async def branches(self):
        return {
            branch_even: self.even_task_name,
            branch_odd: self.odd_task_name
        }

class OddOperator(MapOperator[int, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    async def map(self, x: int) -> str:
        print(f"{x} is odd")
        return f"{x} is odd"

class EvenOperator(MapOperator[int, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    async def map(self, x: int) -> str:
        print(f"{x} is even")
        return f"{x} is even"

class MergeOperator(JoinOperator[str]):
    def __init__(self, **kwargs):
        super().__init__(combine_function=self.merge_func, **kwargs)
        
    async def merge_func(self, odd: str, even: str) -> str:
        return odd if not is_empty_data(odd) else even
```

让我们将这些算子添加到 DAG 中。

```python
    # 之前的代码 ...
    two_sum_task = TwoSumOperator()
    decision_task = DataDecisionOperator(odd_task_name="odd_task", even_task_name="even_task")
    odd_task = OddOperator(task_name="odd_task")
    even_task = EvenOperator(task_name="even_task")
    merge_task = MergeOperator()
    
    db_query_task >> two_sum_task >> decision_task
    decision_task >> odd_task >> merge_task
    decision_task >> even_task >> merge_task


final_result = asyncio.run(merge_task.call({
    "user_input": "Query the name and age of users younger than 18 years old",
    "db_name": "user_management",
    "dialect": "SQLite",
    "top_k": 1,
    "display_type": display_type,
    "response": json.dumps(RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4) 
}))
print("The final result is:")
print(final_result)
```

输出将如下所示：

```bash
un_stream ai response: {
    "thoughts": "The user wants to retrieve the names and ages of users who are younger than 18 years old from the 'user' table.",
    "sql": "SELECT name, age FROM user WHERE age < 18",
    "display_type": "response_table"
}
26 is even
The final result is:
26 is even
```

恭喜！您已经成功使用 `AWEL` 编写了您自己的 `Chat Data`。

### 完整代码

最后，让我们看看完整代码：

```python
import asyncio
import json
import shutil

import pandas as pd

from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    SQLOutputParser,
    SystemPromptTemplate,
)
from dbgpt.core.awel import (
    DAG,
    BranchOperator,
    InputOperator,
    InputSource,
    JoinOperator,
    MapOperator,
    is_empty_data,
)
from dbgpt.core.operators import PromptBuilderOperator, RequestBuilderOperator
from dbgpt.datasource.operators import DatasourceOperator
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteTempConnector
from dbgpt.model.operators import LLMOperator
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt_ext.rag import ChunkParameters
from dbgpt.rag.embedding import DefaultEmbeddingFactory
from dbgpt_ext.rag.operators.db_schema import DBSchemaAssemblerOperator, DBSchemaRetrieverOperator
from dbgpt_ext.storage.vector_store.chroma_store import ChromaVectorConfig, ChromaStore

# 删除旧的向量存储目录(/tmp/awel_with_data_vector_store)
shutil.rmtree("/tmp/awel_with_data_vector_store", ignore_errors=True)

embeddings = DefaultEmbeddingFactory.openai()

# 这里我们使用 openai LLM 模型，如果您想使用其他模型，可以按照前面的示例进行替换。
llm_client = OpenAILLMClient()

db_conn = SQLiteTempConnector.create_temporary_db()
db_conn.create_temp_tables(
    {
        "user": {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "name": "TEXT",
                "age": "INTEGER",
            },
            "data": [
                (1, "Tom", 10),
                (2, "Jerry", 16),
                (3, "Jack", 18),
                (4, "Alice", 20),
                (5, "Bob", 22),
            ],
        }
    }
)

vector_store = ChromaStore(
    ChromaVectorConfig(
        persist_path="/tmp/awel_with_data_vector_store",
    ),
    embedding_fn=embeddings,
    name="db_schema_vector_store",
)

antv_charts = [
    {"response_line_chart": "用于展示对比趋势分析数据"},
    {
        "response_pie_chart": "适用于比例和分布统计等场景"
    },
    {
        "response_table": "适用于显示列较多或非数值型列的场景"
    },
    # {"response_data_text":"默认显示方式，适用于单行或简单内容显示"},
    {
        "response_scatter_plot": "适用于探索变量之间的关系、检测异常值等"
    },
    {
        "response_bubble_chart": "适用于多变量之间的关系、突出异常值或特殊情况等"
    },
    {
        "response_donut_chart": "适用于层次结构表示、类别比例展示和突出关键类别等"
    },
    {
        "response_area_chart": "适用于时间序列数据可视化、多组数据比较、数据变化趋势分析等"
    },
    {
        "response_heatmap": "适用于时间序列数据可视化分析、大规模数据集、分类数据分布等"
    },
]
display_type = "\n".join(
    f"{key}:{value}" for dict_item in antv_charts for key, value in dict_item.items()
)

system_prompt = """您是一名数据库专家。请根据用户选择的数据库以及数据库的一些可用表结构定义来回答用户的问题。
数据库名称：
    {db_name}
表结构定义：
    {table_info}

约束：
1.请根据用户的问题理解用户意图，并使用给定的表结构定义创建语法正确的 {dialect} sql。如果不需要 sql，请直接回答用户的问题。
2.除非用户在问题中指定了希望获取的具体数据行数，否则始终将查询结果限制在最多 {top_k} 条。
3.您只能使用表结构信息中提供的表来生成 sql。如果无法基于提供的表结构生成 sql，请说："提供的表结构信息不足以生成 sql 查询。" 禁止随意编造信息。
4.在生成 SQL 时，请注意不要弄错表和列之间的关系。
5.请检查 SQL 的正确性，并确保在正确条件下优化查询性能。
6.请从下面给出的显示方法中选择最适合数据渲染的一种，并将类型名称放入返回所需格式的 name 参数值中。如果找不到最合适的，请使用 'Table' 作为显示方法。
可用的数据显示方法如下：{display_type}

用户问题：
    {user_input}
请逐步思考，并按照以下 JSON 格式回答：
    {response}
确保响应是正确的 json，并且可以被 Python json.loads 解析。
"""

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "向用户说的想法总结",
    "sql": "要执行的 SQL 查询",
    "display_type": "数据显示方法",
}

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            system_prompt,
            response_format=json.dumps(
                RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4
            ),
        ),
        HumanPromptTemplate.from_template("{user_input}"),
    ]
)


class TwoSumOperator(MapOperator[pd.DataFrame, int]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, df: pd.DataFrame) -> int:
        return await self.blocking_func_to_async(self._two_sum, df)

    def _two_sum(self, df: pd.DataFrame) -> int:
        return df["age"].sum()


def branch_even(x: int) -> bool:
    return x % 2 == 0


def branch_odd(x: int) -> bool:
    return not branch_even(x)


class DataDecisionOperator(BranchOperator[int, int]):
    def __init__(self, odd_task_name: str, even_task_name: str, **kwargs):
        super().__init__(**kwargs)
        self.odd_task_name = odd_task_name
        self.even_task_name = even_task_name

    async def branches(self):
        return {branch_even: self.even_task_name, branch_odd: self.odd_task_name}


class OddOperator(MapOperator[int, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, x: int) -> str:
        print(f"{x} is odd")
        return f"{x} is odd"


class EvenOperator(MapOperator[int, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, x: int) -> str:
        print(f"{x} is even")
        return f"{x} is even"


class MergeOperator(JoinOperator[str]):
    def __init__(self, **kwargs):
        super().__init__(combine_function=self.merge_func, **kwargs)

    async def merge_func(self, odd: str, even: str) -> str:
        return odd if not is_empty_data(odd) else even


with DAG("load_schema_dag") as load_schema_dag:
    input_task = InputOperator.dummy_input()
    # 将数据库模式加载到向量存储
    assembler_task = DBSchemaAssemblerOperator(
        connector=db_conn,
        table_vector_store_connector=vector_store,
        chunk_parameters=ChunkParameters(chunk_strategy="CHUNK_BY_SIZE"),
    )
    input_task >> assembler_task

chunks = asyncio.run(assembler_task.call())
print(chunks)

with DAG("chat_data_dag") as chat_data_dag:
    input_task = InputOperator(input_source=InputSource.from_callable())
    retriever_task = DBSchemaRetrieverOperator(
        top_k=1,
        index_store=vector_store,
    )
    content_task = MapOperator(lambda cks: [c.content for c in cks])
    merge_task = JoinOperator(
        lambda table_info, ext_dict: {"table_info": table_info, **ext_dict}
    )
    prompt_task = PromptBuilderOperator(prompt)
    req_build_task = RequestBuilderOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(llm_client=llm_client)
    sql_parse_task = SQLOutputParser()
    db_query_task = DatasourceOperator(connector=db_conn)

    (
            input_task
            >> MapOperator(lambda x: x["user_input"])
            >> retriever_task
            >> content_task
            >> merge_task
    )
    input_task >> merge_task
    merge_task >> prompt_task >> req_build_task >> llm_task >> sql_parse_task
    sql_parse_task >> MapOperator(lambda x: x["sql"]) >> db_query_task

    two_sum_task = TwoSumOperator()
    decision_task = DataDecisionOperator(
        odd_task_name="odd_task", even_task_name="even_task"
    )
    odd_task = OddOperator(task_name="odd_task")
    even_task = EvenOperator(task_name="even_task")
    merge_task = MergeOperator()

    db_query_task >> two_sum_task >> decision_task
    decision_task >> odd_task >> merge_task
    decision_task >> even_task >> merge_task

final_result = asyncio.run(
    merge_task.call(
        {
            "user_input": "Query the name and age of users younger than 18 years old",
            "db_name": "user_management",
            "dialect": "SQLite",
            "top_k": 1,
            "display_type": display_type,
            "response": json.dumps(
                RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4
            ),
        }
    )
)
print("The final result is:")
print(final_result)

```

## 可视化 DAG

我们可以使用以下代码可视化 DAG：
```python
load_schema_dag.visualize_dag()
chat_data_dag.visualize_dag()
```

如果在 Jupyter Notebook 中执行代码，您可以在笔记本中看到 DAG。
```python
display(load_schema_dag)
display(chat_data_dag)
```

`load_schema_dag` 的图示如下：

<p align="left">
  <img src={'/img/awel/cookbook/chat_data_load_schema_dag.png'} width="1000px"/>
</p>

`chat_data_dag` 的图示如下：
<p align="left">
  <img src={'/img/awel/cookbook/chat_data_chat_data_dag.png'} width="1000px"/>
</p>
