# 数据源

开始使用数据源 API

# 聊天数据源

```python
POST /api/v2/chat/completions
```
### 示例

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### 聊天数据源


<Tabs
  defaultValue="python"
  groupId="chat"
  values={[
    {label: 'Curl', value: 'curl'},
    {label: 'Python', value: 'python'},
    {label: 'Python(OpenAI SDK)', value: 'openai-sdk'},
  ]
}>

<TabItem value="curl">

```shell
DBGPT_API_KEY=dbgpt
DB_NAME="{your_db_name}"

curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"show space datas limit 5\",\"model\":\"gpt-4o\", \"chat_mode\": \"chat_data\", \"chat_param\": \"$DB_NAME\"}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt_client import Client

DBGPT_API_KEY = "dbgpt"
DB_NAME="{your_db_name}"

client = Client(api_key=DBGPT_API_KEY)
res = client.chat(
    messages="show space datas limit 5", 
    model="gpt-4o", 
    chat_mode="chat_data", 
    chat_param=DB_NAME
)
```
 </TabItem>

<TabItem value="openai-sdk">

```python
from openai import OpenAI

DBGPT_API_KEY = "dbgpt"
DB_NAME="{your_db_name}"

client = OpenAI(
    api_key=DBGPT_API_KEY,
    base_url="http://localhost:5670/api/v2"
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": "Hello",
        },
    ],
    extra_body={
        "chat_mode": "chat_data",
        "chat_param": DB_NAME,
    },
    stream=True,
    max_tokens=2048,
)

for chunk in response:
    delta_content = chunk.choices[0].delta.content
    print(delta_content, end="", flush=True)
```
 </TabItem>
</Tabs>

#### 聊天补全响应
```json
{
    "id": "2bb80fdd-e47e-4083-8bc9-7ca66ee0931b",
    "object": "chat.completion",
    "created": 1711509733,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "The user wants to display information about knowledge spaces with a limit of 5 results.\\n<chart-view content=\"{\"type\": \"response_table\", \"sql\": \"SELECT * FROM knowledge_space LIMIT 5\", \"data\": [{\"id\": 5, \"name\": \"frfrw\", \"vector_type\": \"Chroma\", \"desc\": \"eee\", \"owner\": \"eee\", \"context\": null, \"gmt_created\": \"2024-01-02T13:29:52\", \"gmt_modified\": \"2024-01-02T13:29:52\", \"description\": null}, {\"id\": 7, \"name\": \"acc\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T13:47:01\", \"gmt_modified\": \"2024-01-02T13:47:01\", \"description\": null}, {\"id\": 8, \"name\": \"bcc\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T14:22:02\", \"gmt_modified\": \"2024-01-02T14:22:02\", \"description\": null}, {\"id\": 9, \"name\": \"dede\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T14:36:18\", \"gmt_modified\": \"2024-01-02T14:36:18\", \"description\": null}, {\"id\": 10, \"name\": \"qqq\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T14:40:56\", \"gmt_modified\": \"2024-01-02T14:40:56\", \"description\": null}]}\" />"
            },
            "finish_reason": null
        }
    ],
    "usage": {
        "prompt_tokens": 0,
        "total_tokens": 0,
        "completion_tokens": 0
    }
}
```
### 创建数据源

```python
POST /api/v2/serve/datasources
```
#### 请求体
请求 <a href="#the-flow-object">数据源对象</a>

#### 响应体
返回 <a href="#the-flow-object">数据源对象</a>


### 更新数据源
```python
PUT /api/v2/serve/datasources
```

#### 请求体
请求 <a href="#the-flow-object">数据源对象</a>

#### 响应体
返回 <a href="#the-flow-object">数据源对象</a>

### 删除数据源

```python
DELETE /api/v2/serve/datasources
```

<Tabs
  defaultValue="curl_update_datasource"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_update_datasource'},
    {label: 'Python', value: 'python_update_datasource'},
  ]
}>

<TabItem value="curl_update_datasource">

```shell
DBGPT_API_KEY=dbgpt
DATASOURCE_ID={YOUR_DATASOURCE_ID}
 
 curl -X DELETE "http://localhost:5670/api/v2/serve/datasources/$DATASOURCE_ID" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \

```
 </TabItem>

<TabItem value="python_update_datasource">


```python
from dbgpt_client import Client
from dbgpt_client.datasource import delete_datasource

DBGPT_API_KEY = "dbgpt"
datasource_id = "{your_datasource_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await delete_datasource(client=client, datasource_id=datasource_id)

```

 </TabItem>
</Tabs>

#### 删除参数
________
<b>datasource_id</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

数据源 ID
________

#### 响应体
返回 <a href="#the-flow-object">数据源对象</a>

### 获取数据源

```python
GET /api/v2/serve/datasources/{datasource_id}
```
<Tabs
  defaultValue="curl_get_datasource"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_datasource'},
    {label: 'Python', value: 'python_get_datasource'},
  ]
}>

<TabItem value="curl_get_datasource">

```shell
DBGPT_API_KEY=dbgpt
DATASOURCE_ID={YOUR_DATASOURCE_ID}

curl -X GET "http://localhost:5670/api/v2/serve/datasources/$DATASOURCE_ID" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_get_datasource">


```python
from dbgpt_client import Client
from dbgpt_client.datasource import get_datasource

DBGPT_API_KEY = "dbgpt"
datasource_id = "{your_datasource_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_datasource(client=client, datasource_id=datasource_id)

```

 </TabItem>
</Tabs>

#### 查询参数
________
<b>datasource_id</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

数据源 ID
________

#### 响应体
返回 <a href="#the-flow-object">数据源对象</a>

### 列出数据源

```python
GET /api/v2/serve/datasources
```


<Tabs
  defaultValue="curl_list_datasource"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_datasource'},
    {label: 'Python', value: 'python_list_datasource'},
  ]
}>

<TabItem value="curl_list_datasource">

```shell
DBGPT_API_KEY=dbgpt

curl -X GET "http://localhost:5670/api/v2/serve/datasources" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_list_datasource">


```python
from dbgpt_client import Client
from dbgpt_client.datasource import list_datasource

DBGPT_API_KEY = "dbgpt"

client = Client(api_key=DBGPT_API_KEY)
res = await list_datasource(client=client)

```

 </TabItem>
</Tabs>

#### 响应体
返回 <a href="#the-flow-object">数据源对象</a>

### 数据源对象

________
<b>id</b> <font color="gray">string</font>

数据源的唯一 ID。
________
<b>db_name</b> <font color="gray">string</font>

数据库名称
________
<b>db_type</b> <font color="gray">string</font>

数据库类型，例如 sqlite、mysql 等。
________
<b>db_path</b> <font color="gray">string</font>

基于文件的数据库的文件路径。
________
<b>db_host</b> <font color="gray">string</font>

数据库主机。
________
<b>db_port</b> <font color="gray">object</font>

数据库端口。
________
<b>db_user</b> <font color="gray">string</font>

数据库用户。
________
<b>db_pwd</b> <font color="gray">string</font>

数据库密码。
________
<b>comment</b> <font color="gray">string</font>

数据库的备注。
________
