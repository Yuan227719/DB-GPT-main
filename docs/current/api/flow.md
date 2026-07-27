# 流程

开始使用流程 API

# 聊天流程

```python
POST /api/v2/chat/completions
```
### 示例

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### 流式聊天流程


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
FLOW_ID={YOUR_FLOW_ID}

curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"gpt-4o\", \"chat_mode\": \"chat_flow\", \"chat_param\": \"$FLOW_ID\"}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt_client import Client

DBGPT_API_KEY = "dbgpt"
FLOW_ID="{YOUR_FLOW_ID}"

client = Client(api_key=DBGPT_API_KEY)
async for data in client.chat_stream(
    messages="Introduce AWEL", 
    model="gpt-4o", 
    chat_mode="chat_flow", 
    chat_param=FLOW_ID
):
    print(data)
```
 </TabItem>


<TabItem value="openai-sdk">

```python
from openai import OpenAI

DBGPT_API_KEY = "dbgpt"
FLOW_ID="{YOUR_FLOW_ID}"

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
        "chat_mode": "chat_flow",
        "chat_param": FLOW_ID,
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

#### 聊天补全流式响应
```commandline
data: {"id": "579f8862-fc4b-481e-af02-a127e6d036c8", "created": 1710918094, "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "\n\n"}}]}
```
### 创建流程

```python
POST /api/v2/serve/awel/flows
```
#### 请求体
请求 <a href="#the-flow-object">流程对象</a>

#### 响应体
返回 <a href="#the-flow-object">流程对象</a>


### 更新流程
```python
PUT /api/v2/serve/awel/flows
```

#### 请求体
请求 <a href="#the-flow-object">流程对象</a>

#### 响应体
返回 <a href="#the-flow-object">流程对象</a>

### 删除流程

```python
DELETE /api/v2/serve/awel/flows
```

<Tabs
  defaultValue="curl_update_flow"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_update_flow'},
    {label: 'Python', value: 'python_update_flow'},
  ]
}>

<TabItem value="curl_update_flow">

```shell
DBGPT_API_KEY=dbgpt
FLOW_ID={YOUR_FLOW_ID}
 
 curl -X DELETE "http://localhost:5670/api/v2/serve/awel/flows/$FLOW_ID" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \

```
 </TabItem>

<TabItem value="python_update_flow">


```python
from dbgpt_client import Client
from dbgpt_client.flow import delete_flow

DBGPT_API_KEY = "dbgpt"
flow_id = "{your_flow_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await delete_flow(client=client, flow_id=flow_id)

```

 </TabItem>
</Tabs>

#### 删除参数
________
<b>uid</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

流程 ID
________

#### 响应体
返回 <a href="#the-flow-object">流程对象</a>

### 获取流程

```python
GET /api/v2/serve/awel/flows/{flow_id}
```
<Tabs
  defaultValue="curl_get_flow"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_flow'},
    {label: 'Python', value: 'python_get_flow'},
  ]
}>

<TabItem value="curl_get_flow">

```shell
DBGPT_API_KEY=dbgpt
FLOW_ID={YOUR_FLOW_ID}

curl -X GET "http://localhost:5670/api/v2/serve/awel/flows/$FLOW_ID" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_get_flow">


```python
from dbgpt_client import Client
from dbgpt_client.flow import get_flow

DBGPT_API_KEY = "dbgpt"
flow_id = "{your_flow_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_flow(client=client, flow_id=flow_id)

```

 </TabItem>
</Tabs>

#### 查询参数
________
<b>uid</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

流程 ID
________

#### 响应体
返回 <a href="#the-flow-object">流程对象</a>

### 列出流程

```python
GET /api/v2/serve/awel/flows
```


<Tabs
  defaultValue="curl_list_flow"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_flow'},
    {label: 'Python', value: 'python_list_flow'},
  ]
}>

<TabItem value="curl_list_flow">

```shell
DBGPT_API_KEY=dbgpt

curl -X GET "http://localhost:5670/api/v2/serve/awel/flows" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_list_flow">


```python
from dbgpt_client import Client
from dbgpt_client.flow import list_flow

DBGPT_API_KEY = "dbgpt"

client = Client(api_key=DBGPT_API_KEY)
res = await list_flow(client=client)

```

 </TabItem>
</Tabs>

#### 响应体
返回 <a href="#the-flow-object">流程对象</a>

### 流程对象

________
<b>uid</b> <font color="gray">string</font>

流程的唯一 ID。
________
<b>name</b> <font color="gray">string</font>

流程的名称。
________
<b>description</b> <font color="gray">string</font>

流程的描述。
________
<b>label</b> <font color="gray">string</font>

流程的标签。
________
<b>flow_category</b> <font color="gray">string</font>

流程的分类。默认为 FlowCategory.COMMON。
________
<b>flow_data</b> <font color="gray">object</font>

流程数据。
________
<b>state</b> <font color="gray">string</font>

流程的状态。默认为 INITIALIZING。
________
<b>error_message</b> <font color="gray">string</font>

流程的错误信息。
________
<b>source</b> <font color="gray">string</font>

流程的来源。默认为 DBGPT-WEB。
________
<b>source_url</b> <font color="gray">string</font>

流程的源 URL。
________
<b>version</b> <font color="gray">string</font>

流程的版本。默认为 0.1.0。
________
<b>editable</b> <font color="gray">boolean</font>

流程是否可编辑。默认为 True。
________
<b>user_name</b> <font color="gray">string</font>

流程的用户名。
________
<b>sys_code</b> <font color="gray">string</font>

流程的系统代码。
________
<b>dag_id</b> <font color="gray">string</font>

流程的 DAG ID。
________
<b>gmt_created</b> <font color="gray">string</font>

流程的创建时间。
________
<b>gmt_modified</b> <font color="gray">string</font>

流程的修改时间。
________
