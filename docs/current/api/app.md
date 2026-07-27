# App

开始使用 App API

# 聊天 App

```python
POST /api/v2/chat/completions
```
### 示例

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### 流式聊天 App


<Tabs
  defaultValue="python"
  groupId="chat"
  values={[
    {label: 'Curl', value: 'curl'},
    {label: 'Python', value: 'python'},
  ]
}>

<TabItem value="curl">

```shell
 DBGPT_API_KEY=dbgpt
 APP_ID={YOUR_APP_ID}

 curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"gpt-4o\", \"chat_mode\": \"chat_app\", \"chat_param\": \"$APP_ID\"}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt_client import Client

DBGPT_API_KEY = "dbgpt"
APP_ID="{YOUR_APP_ID}"

client = Client(api_key=DBGPT_API_KEY)

async for data in client.chat_stream(
    messages="Introduce AWEL", 
    model="gpt-4o", 
    chat_mode="chat_app", 
    chat_param=APP_ID
):
    print(data)

```
 </TabItem>
</Tabs>

### 聊天补全流式响应
```commandline
data: {"id": "109bfc28-fe87-452c-8e1f-d4fe43283b7d", "created": 1710919480, "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "```agent-plans\n[{\"name\": \"Introduce Awel\", \"num\": 2, \"status\": \"complete\", \"agent\": \"Human\", \"markdown\": \"```agent-messages\\n[{\\\"sender\\\": \\\"Summarizer\\\", \\\"receiver\\\": \\\"Human\\\", \\\"model\\\": \\\"gpt-4o\\\", \\\"markdown\\\": \\\"Agentic Workflow Expression Language (AWEL) is a specialized language designed for developing large model applications with intelligent agent workflows. It offers flexibility and functionality, allowing developers to focus on business logic for LLMs applications without getting bogged down in model and environment details. AWEL uses a layered API design architecture, making it easier to work with. You can find examples and source code to get started with AWEL, and it supports various operators and environments. AWEL is a powerful tool for building native data applications through workflows and agents.\"}]\n```"}}]}

data: [DONE]
```
### 获取 App

```python
GET /api/v2/serve/apps/{app_id}
```

<Tabs
  defaultValue="curl_get_app"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_app'},
    {label: 'Python', value: 'python_get_app'},
  ]
}>

<TabItem value="curl_get_app">

```shell
DBGPT_API_KEY=dbgpt
APP_ID={YOUR_APP_ID}
curl -X GET "http://localhost:5670/api/v2/serve/apps/$APP_ID" -H "Authorization: Bearer $DBGPT_API_KEY"
```
 </TabItem>

<TabItem value="python_get_app">


```python
from dbgpt_client import Client
from dbgpt_client.app import get_app

DBGPT_API_KEY = "dbgpt"
app_id = "{your_app_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_app(client=client, app_id=app_id)

```

 </TabItem>
</Tabs>


#### 查询参数
________
<b>app_id</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

应用 ID
________

#### 响应体
返回 <a href="#the-app-object">App 对象</a>

### 列出 App

```python
GET /api/v2/serve/apps
```
<Tabs
  defaultValue="curl_list_app"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_app'},
    {label: 'Python', value: 'python_list_app'},
  ]
}>

<TabItem value="curl_list_app">

```shell
DBGPT_API_KEY=dbgpt

curl -X GET 'http://localhost:5670/api/v2/serve/apps' -H "Authorization: Bearer $DBGPT_API_KEY"
```
 </TabItem>

<TabItem value="python_list_app">


```python
from dbgpt_client import Client
from dbgpt_client.app import list_app

DBGPT_API_KEY = "dbgpt"
app_id = "{your_app_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await list_app(client=client)

```

 </TabItem>
</Tabs>

#### 响应体
返回 <a href="#the-app-object">App 对象</a> 列表

### App 模型
________
<b>app_code</b> <font color="gray"> string </font>

唯一的应用 ID
________
<b>app_name</b> <font color="gray"> string </font>

应用名称
________

<b>app_describe</b> <font color="gray"> string </font>

应用描述
________
<b>team_mode</b> <font color="gray"> string </font>

团队模式
________
<b>language</b> <font color="gray"> string </font>

语言
________
<b>team_context</b> <font color="gray"> string </font>

团队上下文
________
<b>user_code</b> <font color="gray"> string </font>

用户代码
________
<b>sys_code</b> <font color="gray"> string </font>

系统代码
________
<b>is_collected</b> <font color="gray"> string </font>

是否已收藏
________
<b>icon</b> <font color="gray"> string </font>

图标
________
<b>created_at</b> <font color="gray"> string </font>

创建时间
________
<b>updated_at</b> <font color="gray"> string </font>

更新时间
________
<b>details</b> <font color="gray"> string </font>

应用详情 List[AppDetailModel]
________

### App 详情模型
________
<b>app_code</b> <font color="gray"> string </font>

应用代码
________
<b>app_name</b> <font color="gray"> string </font>

应用名称
________
<b>agent_name</b> <font color="gray"> string </font>

Agent 名称
________
<b>node_id</b> <font color="gray"> string </font>

节点 ID
________
<b>resources</b> <font color="gray"> string </font>

资源
________
<b>prompt_template</b> <font color="gray"> string </font>

提示词模板
________
<b>llm_strategy</b> <font color="gray"> string </font>

LLM 策略
________
<b>llm_strategy_value</b> <font color="gray"> string </font>

LLM 策略值
________
<b>created_at</b> <font color="gray"> string </font>

创建时间
________
<b>updated_at</b> <font color="gray"> string </font>

更新时间
________
