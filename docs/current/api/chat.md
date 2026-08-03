# 聊天

给定一组构成对话的消息列表，模型将返回响应。

# 创建聊天补全

```python
POST /api/v2/chat/completions
```

### 示例

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### 流式聊天补全


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
 DBGPT_API_KEY="dbgpt"

 curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"gpt-4o\", \"stream\": true}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt_client import Client

DBGPT_API_KEY = "dbgpt"
client = Client(api_key=DBGPT_API_KEY)

async for data in client.chat_stream(
    model="gpt-4o",
    messages="hello",
):
    print(data)
```
 </TabItem>

<TabItem value="openai-sdk">

```python
from openai import OpenAI
DBGPT_API_KEY = "dbgpt"

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
        "chat_mode": "chat_normal",
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


### 聊天补全流式响应
```commandline
data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Hello"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "!"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " How"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " can"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " I"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " assist"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " you"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " today"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "gpt-4o", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "?"}}]}

data: [DONE]
```

### 聊天补全
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
 DBGPT_API_KEY="dbgpt"

 curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"gpt-4o\", \"stream\": false}"
```
 </TabItem>

<TabItem value="python">

```python
from dbgpt_client import Client

DBGPT_API_KEY = "dbgpt"
client = Client(api_key=DBGPT_API_KEY)
response = await client.chat(model="gpt-4o" ,messages="hello")
print(response)
await client.aclose()
```
 </TabItem>
</Tabs>

### 聊天补全响应
```json
{
    "id": "a8321543-52e9-47a5-a0b6-3d997463f6a3",
    "object": "chat.completion",
    "created": 1710826792,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I assist you today?"
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



### 请求体
________
<b>messages</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

截至目前对话的消息列表。示例 Python 代码。
________
<b>model</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

要使用的模型 ID。请参阅模型端点兼容性表，了解哪些模型适用于聊天 API 的详细信息。
________
<b>chat_mode</b> <font color="gray"> string </font> <font color="red"> 可选 </font>

DB-GPT 聊天模式，可以是以下之一：`chat_normal`、`chat_app`、`chat_knowledge`、`chat_flow`，默认为 `chat_normal`。
________
<b>chat_param</b> <font color="gray"> string </font> <font color="red"> 可选 </font>

DB-GPT 聊天模式的聊天参数值：`{app_id}`、`{space_id}`、`{flow_id}`，默认为 `None`。
________
<b>max_new_tokens</b> <font color="gray"> integer </font> <font color="red"> 可选 </font>

聊天补全中可以生成的最大 token 数量。

输入 token 和生成 token 的总长度受模型上下文长度的限制。
________
<b>stream</b> <font color="gray"> integer </font> <font color="red"> 可选 </font>

如果设置，将发送部分消息增量。
Token 将以纯数据服务器发送事件的形式在可用时发送，流以 `data: [DONE]` 终止。
________
<b>temperature</b> <font color="gray"> integer </font> <font color="red"> 可选 </font>

使用的采样温度，介于 0 和 2 之间。较高的值（如 0.8）会使输出更随机，而较低的值（如 0.2）会使其更聚焦和确定。
________
<b>conv_uid</b> <font color="gray"> string </font> <font color="red"> 可选 </font>

模型推理的对话 ID，默认为 `None`
________
<b>span_id</b> <font color="gray"> string </font> <font color="red"> 可选 </font>

模型推理的跨度 ID，默认为 `None`
________
<b>sys_code</b> <font color="gray"> string </font> <font color="red"> 可选 </font>

系统代码，默认为 `None`
________
<b>user_name</b> <font color="gray"> string </font> <font color="red"> 可选 </font>

Web 服务器用户名，默认为 `None`
________


### 聊天流式响应体
________
<b>id</b> <font color="gray"> string </font>

对话的 conv_uid。
________
<b>model</b> <font color="gray"> string </font>

用于聊天补全的模型。

________
<b>created</b> <font color="gray"> string </font>

创建聊天补全时的 Unix 时间戳（秒）。

________
<b>choices</b> <font color="gray"> array </font>

聊天补全选项列表。如果 n 大于 1，则可以有多个。

  - <b>index</b> <font color="gray"> integer </font>

    选项在选项列表中的索引。
  - <b>delta</b> <font color="gray"> object </font>

    聊天补全的增量。
    - <b>role</b> <font color="gray"> string </font>

      发言者的角色。可以是 `user` 或 `assistant`。
    - <b>content</b> <font color="gray"> string </font>

      消息的内容。
    - <b>finish_reason</b> <font color="gray"> string </font>
    
        聊天补全结束的原因。可以是 `max_tokens` 或 `stop`。
________


### 聊天响应体
________
<b>id</b> <font color="gray"> string </font>

对话的 conv_uid。
________
<b>model</b> <font color="gray"> string </font>

用于聊天补全的模型。

________
<b>created</b> <font color="gray"> string </font>

创建聊天补全时的 Unix 时间戳（秒）。
________
<b>object</b> <font color="gray"> string </font>

聊天补全的对象类型。
________
<b>choices</b> <font color="gray"> array </font>

聊天补全选项列表。如果 n 大于 1，则可以有多个。

  - <b>index</b> <font color="gray"> integer </font>

    选项在选项列表中的索引。

  - <b>delta</b> <font color="gray"> object </font>

    聊天补全的增量。
    - <b>role</b> <font color="gray"> string </font>

      发言者的角色。可以是 `user` 或 `assistant`。
    - <b>content</b> <font color="gray"> string </font>

      消息的内容。
    - <b>finish_reason</b> <font color="gray"> string </font>
    
        聊天补全结束的原因。可以是 `max_tokens` 或 `stop`。
________
<b>usage</b> <font color="gray"> object </font>

    聊天补全的使用统计。
    - <b>prompt_tokens</b> <font color="gray"> integer </font>

      提示中的 token 数量。
    - <b>total_tokens</b> <font color="gray"> integer </font>

      聊天补全中的总 token 数量。
    - <b>completion_tokens</b> <font color="gray"> integer </font>

      聊天补全中的 token 数量。
