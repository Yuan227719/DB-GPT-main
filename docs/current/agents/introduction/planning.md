# 智能体规划

当面对复杂任务时，人类倾向于将其分解为更简单的子任务并分别解决。规划模块旨在赋予智能体这种人类能力，这将使智能体的行为更加合理、强大和可靠。

## 介绍

以下是规划模块的简单架构图：

<p align="left">
  <img src={'/img/agents/introduction/agents_planning.png'} width="720px" />
</p>

在上图中，规划模块将接收用户的任务，然后将任务分解为子任务并分配给相应的智能体（Agent1、Agent2...）。

## 使用智能体分析数据库

在以下示例中，我们将向您展示如何使用规划模块来分析数据库。

要运行此示例，请根据[前面的说明](./database#installation)安装依赖。

### 准备数据库

为简单起见，我们将使用一个临时的 SQLite 数据库来存储数据。该数据库将在临时目录中创建，并在程序退出后自动删除。

首先，创建一个临时 SQLite 数据库，创建一些表并插入一些数据：

```python
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteTempConnector

connector = SQLiteTempConnector.create_temporary_db()
connector.create_temp_tables(
    {
        "students": {
            "columns": {
                "student_id": "INTEGER PRIMARY KEY",
                "student_name": "TEXT",
                "major": "TEXT",
                "year_of_enrollment": "INTEGER",
                "student_age": "INTEGER",
            },
            "data": [
                (1, "Zhang San", "Computer Science", 2020, 20),
                (2, "Li Si", "Computer Science", 2021, 19),
                (3, "Wang Wu", "Physics", 2020, 21),
                (4, "Zhao Liu", "Mathematics", 2021, 19),
                (5, "Zhou Qi", "Computer Science", 2022, 18),
                (6, "Wu Ba", "Physics", 2020, 21),
                (7, "Zheng Jiu", "Mathematics", 2021, 19),
                (8, "Sun Shi", "Computer Science", 2022, 18),
                (9, "Liu Shiyi", "Physics", 2020, 21),
                (10, "Chen Shier", "Mathematics", 2021, 19),
            ],
        },
        "courses": {
            "columns": {
                "course_id": "INTEGER PRIMARY KEY",
                "course_name": "TEXT",
                "credit": "REAL",
            },
            "data": [
                (1, "Introduction to Computer Science", 3),
                (2, "Data Structures", 4),
                (3, "Advanced Physics", 3),
                (4, "Linear Algebra", 4),
                (5, "Calculus", 5),
                (6, "Programming Languages", 4),
                (7, "Quantum Mechanics", 3),
                (8, "Probability Theory", 4),
                (9, "Database Systems", 4),
                (10, "Computer Networks", 4),
            ],
        },
        "scores": {
            "columns": {
                "student_id": "INTEGER",
                "course_id": "INTEGER",
                "score": "INTEGER",
                "semester": "TEXT",
            },
            "data": [
                (1, 1, 90, "Fall 2020"),
                (1, 2, 85, "Spring 2021"),
                (2, 1, 88, "Fall 2021"),
                (2, 2, 90, "Spring 2022"),
                (3, 3, 92, "Fall 2020"),
                (3, 4, 85, "Spring 2021"),
                (4, 3, 88, "Fall 2021"),
                (4, 4, 86, "Spring 2022"),
                (5, 1, 90, "Fall 2022"),
                (5, 2, 87, "Spring 2023"),
            ],
        },
    }
)
```

### 创建数据库资源

```python
from dbgpt.agent.resource import RDBMSConnectorResource

db_resource = RDBMSConnectorResource("student_manager", connector=connector)
```

### 自动规划分析数据库

为了创建分析数据库的计划，这里我们引入一个新的智能体 `AutoPlanChatManager`，
它可以自动规划任务并将子任务分配给相应的智能体。

`AutoPlanChatManager` 是一个特殊的智能体，其创建方式与其他智能体类似，
但它有一个特殊的方法 `hire` 来雇佣其他智能体。

```python

import asyncio
import os

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    AutoPlanChatManager,
    LLMConfig,
    UserProxyAgent,
)
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
    manager = (
        await AutoPlanChatManager()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([sql_boy])

    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="Analyze student scores from at least three dimensions",
    )

    # dbgpt-vis 消息信息
    print(await agent_memory.gpts_memory.app_link_chat_message("test123"))


if __name__ == "__main__":
    asyncio.run(main())
```

输出结果如下：

``````bash
--------------------------------------------------------------------------------
User (to AutoPlanChatManager)-[]:

"Analyze student scores from at least three dimensions"

--------------------------------------------------------------------------------
un_stream ai response: [
    {
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.",
        "rely": "1"
    },
    {
        "serialjson_number": "3",
        "agent": "DataScientist",
        "content": "Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.",
        "rely": "2"
    }
]

--------------------------------------------------------------------------------
Planner (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"[\n    {\n        \"serial_number\": \"1\",\n        \"agent\": \"DataScientist\",\n        \"content\": \"Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.\",\n        \"rely\": \"\"\n    },\n    {\n        \"serial_number\": \"2\",\n        \"agent\": \"DataScientist\",\n        \"content\": \"Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.\",\n        \"rely\": \"1\"\n    },\n    {\n        \"serialjson_number\": \"3\",\n        \"agent\": \"DataScientist\",\n        \"content\": \"Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.\",\n        \"rely\": \"2\"\n    }\n]"
>>>>>>>>Planner Review info: 
Pass(None)
>>>>>>>>Planner Action report: 
execution succeeded,
[
    {
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.",
        "rely": "1"
    },
    {
        "serialjson_number": "3",
        "agent": "DataScientist",
        "content": "Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.",
        "rely": "2"
    }
]

--------------------------------------------------------------------------------
GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:
DataScientist

--------------------------------------------------------------------------------
AutoPlanChatManager (to Edgar)-[]:

"Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records."

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id",
  "thought": "I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys."
}

--------------------------------------------------------------------------------
Edgar (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id\",\n  \"thought\": \"I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id","thought":"I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys."}

--------------------------------------------------------------------------------
GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:
DataScientist

--------------------------------------------------------------------------------
AutoPlanChatManager (to Edgar)-[]:

"Read the result data of the dependent steps in the above historical message to complete the current goal:Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation."

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course."
}

--------------------------------------------------------------------------------
Edgar (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name\",\n  \"thought\": \"I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name","thought":"I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course."}

--------------------------------------------------------------------------------
GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:
DataScientist

--------------------------------------------------------------------------------
AutoPlanChatManager (to Edgar)-[]:

"Read the result data of the dependent steps in the above historical message to complete the current goal:Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively."

--------------------------------------------------------------------------------
un_stream ai response: {
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively."
}

--------------------------------------------------------------------------------
Edgar (to AutoPlanChatManager)-[gpt-3.5-turbo]:

"{\n  \"display_type\": \"response_table\",\n  \"sql\": \"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name\",\n  \"thought\": \"The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively.\"\n}"
>>>>>>>>Edgar Review info: 
Pass(None)
>>>>>>>>Edgar Action report: 
execution succeeded,
{"display_type":"response_table","sql":"SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name","thought":"The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively."}

--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
AutoPlanChatManager (to User)-[]:

"Analyze student scores from at least three dimensions"
>>>>>>>>AutoPlanChatManager Review info: 
Pass(None)
>>>>>>>>AutoPlanChatManager Action report: 
execution succeeded,
```vis-db-chart
{"sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name", "type": "response_table", "title": "", "describe": "The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively.", "data": [{"student_id": 1, "student_name": "Zhang San", "course_name": "Data Structures", "credit": 4.0, "average_score": 85.0, "total_scores": 1, "highest_score": 85, "lowest_score": 85, "total_score": 85, "average_semester": 0.0}, {"student_id": 1, "student_name": "Zhang San", "course_name": "Introduction to Computer Science", "credit": 3.0, "average_score": 90.0, "total_scores": 1, "highest_score": 90, "lowest_score": 90, "total_score": 90, "average_semester": 0.0}, {"student_id": 2, "student_name": "Li Si", "course_name": "Data Structures", "credit": 4.0, "average_score": 90.0, "total_scores": 1, "highest_score": 90, "lowest_score": 90, "total_score": 90, "average_semester": 0.0}, {"student_id": 2, "student_name": "Li Si", "course_name": "Introduction to Computer Science", "credit": 3.0, "average_score": 88.0, "total_scores": 1, "highest_score": 88, "lowest_score": 88, "total_score": 88, "average_semester": 0.0}, {"student_id": 3, "student_name": "Wang Wu", "course_name": "Advanced Physics", "credit": 3.0, "average_score": 92.0, "total_scores": 1, "highest_score": 92, "lowest_score": 92, "total_score": 92, "average_semester": 0.0}, {"student_id": 3, "student_name": "Wang Wu", "course_name": "Linear Algebra", "credit": 4.0, "average_score": 85.0, "total_scores": 1, "highest_score": 85, "lowest_score": 85, "total_score": 85, "average_semester": 0.0}, {"student_id": 4, "student_name": "Zhao Liu", "course_name": "Advanced Physics", "credit": 3.0, "average_score": 88.0, "total_scores": 1, "highest_score": 88, "lowest_score": 88, "total_score": 88, "average_semester": 0.0}, {"student_id": 4, "student_name": "Zhao Liu", "course_name": "Linear Algebra", "credit": 4.0, "average_score": 86.0, "total_scores": 1, "highest_score": 86, "lowest_score": 86, "total_score": 86, "average_semester": 0.0}, {"student_id": 5, "student_name": "Zhou Qi", "course_name": "Data Structures", "credit": 4.0, "average_score": 87.0, "total_scores": 1, "highest_score": 87, "lowest_score": 87, "total_score": 87, "average_semester": 0.0}, {"student_id": 5, "student_name": "Zhou Qi", "course_name": "Introduction to Computer Science", "credit": 3.0, "average_score": 90.0, "total_scores": 1, "highest_score": 90, "lowest_score": 90, "total_score": 90, "average_semester": 0.0}]}
```

--------------------------------------------------------------------------------
``````

输出是 [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) 协议，我们可以解析出一些有用的结果。

**1. 计划**
```json
[
    {
        "serial_number": "1",
        "agent": "DataScientist",
        "content": "Retrieve student scores data from the database including scores for each subject, overall performance, and attendance records.",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "Analyze student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation.",
        "rely": "1"
    },
    {
        "serialjson_number": "3",
        "agent": "DataScientist",
        "content": "Visualize the analyzed data using appropriate graphs and charts to represent the student scores from different dimensions effectively.",
        "rely": "2"
    }
]
```

**2. 第一个任务的 LLM 输出**
```json
{
  "display_type": "response_table",
  "sql": "SELECT s.student_id, s.student_name, s.major, s.year_of_enrollment, s.student_age, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id",
  "thought": "I have crafted a SQL query that retrieves student scores data including scores for each subject, overall performance, and attendance records by joining the 'students', 'scores', and 'courses' tables on their respective keys."
}
```

**3. 第二个任务的 LLM 输出**
```json
{
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "I have created a SQL query that analyzes student scores data to identify trends and patterns in academic performance, subject-wise scores, and attendance correlation. The query calculates average score, total scores, highest score, lowest score, total score, and average semester for each student in each course."
}
```

**4. 第三个任务的 LLM 输出**
```json
{
  "display_type": "response_table",
  "sql": "SELECT student_id, student_name, course_name, credit, AVG(score) AS average_score, COUNT(score) AS total_scores, MAX(score) AS highest_score, MIN(score) AS lowest_score, SUM(score) AS total_score, AVG(semester) AS average_semester FROM (SELECT s.student_id, s.student_name, c.course_name, c.credit, sc.score, sc.semester FROM students s JOIN scores sc ON s.student_id = sc.student_id JOIN courses c ON sc.course_id = c.course_id) GROUP BY student_id, course_name",
  "thought": "The SQL query provided will generate a table with the analyzed data including average score, total scores, highest score, lowest score, total score, and average semester for each student in each course. This table can be further used for visualization purposes to represent student scores from different dimensions effectively."
}
```

当然，如果运行上述代码，输出还会包含 SQL 查询执行后的数据，这里我们不再展示数据，因为内容太长。
