# API 接口使用

DB-GPT 项目目前也提供了多种 API 供使用。目前 API 主要分为两类：1. 模型 API 2. 应用服务层 API

模型 API 主要是指 DB-GPT 适配各种模型，并统一封装成兼容 OpenAI SDK 输出的模型。服务层 API 是指 DB-GPT 服务层对外暴露的 API。以下是对两者使用的简要介绍。

## 模型 API

在 DB-GPT 项目中，我们定义了一个面向服务的多模型管理框架（SMMF）。通过 SMMF 的能力，我们可以部署多个模型，这些模型通过服务对外提供能力。为了使客户端实现无缝切换，我们统一支持 OpenAI SDK 标准。
- 详细使用教程：[OpenAI SDK 调用本地多模型](../../installation/advanced_usage/OpenAI_SDK_call.md)

**示例：** 以下是通过 OpenAI SDK 调用的示例

```python
import openai
model = "Qwen/QwQ-32B"

client = openai.OpenAI(
  api_key="EMPTY",
  base_url="http://127.0.0.1:8100/api/v1",
)
completion = client.chat.completions.create(
  model=model,
  messages=[{"role": "user", "content": "hello"}]
)
# 打印完成结果
print(completion.choices[0].message.content)
```


## 应用服务层 API
服务层 API 是指启动 Web 服务器后在 5670 端口暴露的 API，主要聚焦于应用层。按类别可分为以下几部分

- 聊天 API
- 编辑器 API
- LLM 管理 API
- Agent API
- AWEL API
- 模型 API

:::info
注意：启动 Web 服务器后，打开 http://127.0.0.1:5670/docs 查看详情

关于服务层 API，在早期策略方面，我们遵循最小可用和开放原则。稳定对外暴露的 API 会携带版本信息，例如
- /api/v1/
- /api/v2/

由于整个领域发展迅速，不同版本的 API 在兼容性方面不会完全兼容。在后续的新版本 API 中，我们将在文档中说明不兼容的 API。
:::

## API 说明

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="chatapi"
  values={[
    {label: '聊天 API', value: 'chatapi'},
    {label: '编辑器 API', value: 'editorapi'},
    {label: '模型 API', value: 'modelapi'},
    {label: 'LLM 管理 API', value: 'llmanageapi'},
    {label: 'Agent API', value: 'agentapi'},
    {label: 'AWEL API', value: 'awelapi'},
  ]}>
  <TabItem value="chatapi">    

  聊天 API 列表

  ```python
    api/v1/chat/db/list
    api/v1/chat/db/add
    api/v1/chat/db/edit
    api/v1/chat/db/delete
    api/v1/chat/db/test/connect
    api/v1/chat/db/summary
    api/v1/chat/db/support/type
    api/v1/chat/dialogue/list
    api/v1/chat/dialogue/scenes
    api/v1/chat/dialogue/new
    api/v1/chat/mode/params/list
    api/v1/chat/mode/params/file/load
    api/v1/chat/dialogue/delete
    api/v1/chat/dialogue/messages
    api/v1/chat/prepare
    api/v1/chat/completions
  ```
  </TabItem>
  <TabItem value="editorapi">   

  编辑器 API 列表
  
  ```python
    api/v1/editor/db/tables
    api/v1/editor/sql/rounds
    api/v1/editor/sql
    api/v1/editor/sql/run
    api/v1/sql/editor/submit
    api/v1/editor/chart/list
    api/v1/editor/chart/info
    api/v1/editor/chart/run
    api/v1/chart/editor/submit
  ```
  </TabItem>
  <TabItem value="modelapi">   
    
  模型 API 列表

  ```python
    api/v1/model/types
    api/v1/model/supports
  ```
  </TabItem>
  <TabItem value="llmanageapi">   
    
  LLM 管理 API 列表

  ```python
    api/v1/worker/model/params
    api/v1/worker/model/list
    api/v1/worker/model/stop
    api/v1/worker/model/start
    api/worker/generate_stream
    api/worker/generate
    api/worker/embeddings
    api/worker/apply
    api/worker/parameter/descriptions
    api/worker/models/supports
    api/worker/models/startup
    api/worker/models/shutdown
    api/controller/models
    api/controller/heartbeat
  ```
  </TabItem>
  <TabItem value="agentapi">   
    
  Agent API 列表

  ```python
    api/v1/agent/hub/update
    api/v1/agent/query
    api/v1/agent/my
    api/v1/agent/install
    api/v1/agent/uninstall
    api/v1/personal/agent/upload
  ```
  </TabItem>
  <TabItem value="awelapi">   
    
  AWEL API 列表

  ```python
    api/v1/awel/trigger/examples/simple_rag
    api/v1/awel/trigger/examples/simple_chat
    api/v1/awel/trigger/examples/hello
  ```

  </TabItem>
</Tabs>

:::info 注意

⚠️ 知识和提示 API

目前，由于知识和提示频繁变更，相关 API 仍处于测试阶段，将在后续逐步开放

:::

更多详细的接口参数请查看 `http://127.0.0.1:5670/docs`
