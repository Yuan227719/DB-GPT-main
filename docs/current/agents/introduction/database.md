# 智能体与数据库

大多数情况下，我们希望智能体能够基于数据库中的数据来回答问题，或根据数据库中的数据做出决策。在这种情况下，我们需要将智能体连接到数据库。

## 安装

要在智能体中使用数据库，您需要使用以下命令安装依赖：

```bash
pip install "dbgpt[agent,simple_framework]>=0.7.0" "dbgpt_ext>=0.7.0"
```

## 创建数据库连接器

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="sqlite_temp"
  values={[
    {label: 'SQLite（临时）', value: 'sqlite_temp'},
    {label: 'SQLite', value: 'sqlite'},
    {label: 'MySQL', value: 'mysql'},
  ]}>

<TabItem value="sqlite_temp" label="sqlite_temp">

:::tip 注意
我们提供一个临时的 SQLite 数据库用于测试。临时数据库将在临时目录中创建，并在程序退出后自动删除。
:::

```python
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteTempConnector

connector = SQLiteTempConnector.create_temporary_db()
connector.create_temp_tables(
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
</TabItem>

<TabItem value="sqlite" label="sqlite">

:::tip 注意
我们通过提供数据库文件路径来连接 SQLite 数据库，请确保文件路径正确。
:::

```python
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

connector = SQLiteConnector.from_file_path("path/to/your/database.db")
```

</TabItem>

<TabItem value="mysql" label="MySQL">

:::tip 注意

我们通过提供数据库连接信息来连接 MySQL 数据库，请确保连接信息正确。
:::

```python
from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector

connector = MySQLConnector.from_uri_db(
    host="localhost",
    port=3307,
    user="root",
    pwd="********",
    db_name="user_manager",
    engine_args={"connect_args": {"charset": "utf8mb4"}},
)
```
 
</TabItem>

</Tabs>


## 创建数据库资源

```python
from dbgpt.agent.resource import RDBMSConnectorResource

db_resource = RDBMSConnectorResource("user_manager", connector=connector)
```

如前所述，**数据库**是一种资源，我们可以使用 DB-GPT 支持的大多数数据库（如 SQLite、MySQL、ClickHouse、ApacheDoris、DuckDB、Hive、MSSQL、OceanBase、PostgreSQL、StarRocks、Vertica 等）作为资源。

## 在智能体中使用数据库

```python
import asyncio
import os
from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
from dbgpt.model.proxy import OpenAILLMClient

async def main():

    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # 或其他模型，例如 "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(
        conv_id="test123", language="en", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="test123")

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    sql_boy = (
        await DataScientistAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(db_resource)
        .bind(agent_memory)
        .build()
    )

    await user_proxy.initiate_chat(
        recipient=sql_boy,
        reviewer=user_proxy,
        message="What is the name and age of the user with age less than 18",
    )

    ## dbgpt-vis 消息信息
    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())

```

输出结果如下：

``````bash
--------------------------------------------------------------------------------
User (to Edgar)-[]:

"What is the name and age of the user with age less than 18"

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT name, age FROM user WHERE age < 18",
  "thought": "I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18."
}

--------------------------------------------------------------------------------
Edgar (to User)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT name, age FROM user WHERE age < 18\",\n  \"thought\": \"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT name, age FROM user WHERE age < 18","thought":"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18."}

--------------------------------------------------------------------------------
```agent-plans
[{"name": "What is the name and age of the user with age less than 18", "num": 1, "status": "complete", "agent": "Human", "markdown": "```agent-messages\n[{\"sender\": \"DataScientist\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-db-chart\\n{\\\"sql\\\": \\\"SELECT name, age FROM user WHERE age < 18\\\", \\\"type\\\": \\\"response_table\\\", \\\"title\\\": \\\"\\\", \\\"describe\\\": \\\"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18.\\\", \\\"data\\\": [{\\\"name\\\": \\\"Tom\\\", \\\"age\\\": 10}, {\\\"name\\\": \\\"Jerry\\\", \\\"age\\\": 16}]}\\n```\"}]\n```"}]
```
``````

让我们解析上述输出结果，我们只关注最后一部分
（使用 [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) 协议输出）：
```json
[
    {
        "name": "What is the name and age of the user with age less than 18",
        "num": 1,
        "status": "complete",
        "agent": "Human",
        "markdown": "```agent-messages\n[{\"sender\": \"DataScientist\", \"receiver\": \"Human\", \"model\": \"gpt-3.5-turbo\", \"markdown\": \"```vis-db-chart\\n{\\\"sql\\\": \\\"SELECT name, age FROM user WHERE age < 18\\\", \\\"type\\\": \\\"response_table\\\", \\\"title\\\": \\\"\\\", \\\"describe\\\": \\\"I have selected a response_table to display the names and ages of users with an age less than 18. The SQL query retrieves the name and age columns from the user table where the age is less than 18.\\\", \\\"data\\\": [{\\\"name\\\": \\\"Tom\\\", \\\"age\\\": 10}, {\\\"name\\\": \\\"Jerry\\\", \\\"age\\\": 16}]}\\n```\"}]\n```"
    }
]
```
什么是 GPT-Vis？GPT-Vis 是面向 GPTs、生成式 AI 和 LLM 项目的组件集合。
它提供了一种协议（一种在 markdown 中的自定义代码语法）来描述 AI 模型的输出，
并能够在丰富的 UI 组件中渲染输出。

在这里，输出是一个表格，包含年龄小于 18 岁的用户的姓名和年龄。
