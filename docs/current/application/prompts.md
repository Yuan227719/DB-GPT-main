# 提示词管理

在实际应用开发过程中，在不同场景、Agent、RAG 等模块中需要自定义 Prompt。为了使 Prompt 的编辑和调整更加灵活，我们创建了独立的 Prompt 模块。

## 浏览

如下图所示，点击**应用管理** -> **提示词** 即可进入相应的管理界面。界面默认显示自定义提示词列表，您可以管理所有提示词。

<p align="center">
  <img src={'/img/app/prompt_v0.6.jpg'} width="800px" />
</p>

## 新增
接下来，让我们看看如何创建新的提示词。点击 **添加提示词** 按钮，弹出提示词编辑框。

<p align="center">
  <img src={'/img/app/prompt_add_v0.6.jpg'} width="800px" />
</p>

我们定义了四种提示词类型：
- AGENT：Agent 提示词
- SCENE：场景提示词
- NORMAL：普通提示词
- EVALUATE：评估模式提示词

当选择 AGENT 类型时，下拉列表菜单中可以看到所有已注册的 Agent，您可以选择一个 Agent 来设置提示词。

<p align="center">
  <img src={'/img/app/agent_prompt_v0.6.jpg'} width="400px" />
</p>

设置完成后，会生成唯一的 UID。您可以在使用时根据 ID 绑定相应的提示词。

<p align="center">
  <img src={'/img/app/agent_prompt_code_v0.6.jpg'} width="800px" />
</p>


## 使用

进入 AWEL 编辑界面，如下图所示，点击**应用管理** -> **创建工作流**


<p align="center">
  <img src={'/img/app/awel_create.6.jpg'} width="800px" />
</p>

找到 Agent 资源并选择 AWEL 布局 Agent 算子。我们可以看到每个 Agent 包含以下信息：

- 概况
- 角色
- 目标
- 资源（AWELResource）：Agent 依赖的资源
- Agent 配置（AWELAgentConfig）
- Agent 提示词：Prompt

<p align="center">
  <img src={'/img/app/agent_prompt_awel_v0.6.jpg'} width="800px" />
</p>

点击 **AgentPrompt** 旁边的 [+]，选择弹出的 Prompt 算子，在参数面板中选择相应的 Prompt 名称或 UID，将我们新创建的 Prompt 绑定到 Agent，并依次调试 Agent 的行为。
