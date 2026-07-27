# 应用管理

应用管理面板提供了丰富的功能。这里我们主要介绍数据智能应用生命周期的管理，包括应用的创建、编辑、删除和使用。

<p align="center">
  <img src={'/img/app/app_manage_v0.6.jpg'} width="800px" />
</p>

如图所示，应用管理界面。首先，让我们来看一下应用的创建。在 DB-GPT 中，提供了四种应用创建模式。

- 多智能体自动规划模式（Multi-agent automatic planning mode）
- 任务流编排模式（Task flow orchestration mode）
- 单智能体模式（Single Agent Mode）
- 原生应用模式（Native application mode）

<p align="center">
  <img src={'/img/app/app_manage_mode_v0.6.jpg'} width="800px" />
</p>

接下来，我们将分别说明每种模式下的应用创建。在原生应用模式下，DB-GPT 早期版本提供了六种原生应用场景，如 `Chat DB`、`Chat Data`、`Chat Dashboard`、`Chat Knowledge Base`、`Chat Normal`、`Chat Excel` 等。

通过原生应用模式创建数据智能应用，您可以根据自己的数据库、知识库等参数快速构建类似的应用程序。点击右上角的**创建应用**按钮，选择**原生应用模式**，输入应用名称和描述，点击**确定**。

<p align="center">
  <img src={'/img/app/app_manage_chat_data_v0.6.jpg'} width="800px" />
</p>

确认后，进入参数选择面板。如下图所示，我们可以看到应用类型、模型、温度、推荐问题等选择框。

<p align="center">
  <img src={'/img/app/app_manage_chat_data_editor_v0.6.jpg'} width="800px" />
</p>

这里我们选择 **Chat Data** 应用，根据要求依次填写参数。注意，在数据对话应用中，参数列需要填写数据源。如果您没有数据源，需要按照[数据源教程](../datasources.md)进行添加。

完成参数填写后，点击**保存**即可在应用面板中查看相关应用。

<p align="center">
  <img src={'/img/app/app_manage_app_v0.6.jpg'} width="800px" />
</p>

请注意，创建应用后，有一个**发布应用**按钮。只有应用发布后，才能被其他用户发现和使用。

<p align="center">
  <img src={'/img/app/app_manage_app_publish_v0.6.jpg'} width="800px" />
</p>

最后，点击**开始对话**按钮，即可与您刚创建的应用开始对话。

<p align="center">
  <img src={'/img/app/app_manage_chat_v0.6.jpg'} width="800px" />
</p>

此外，您还可以编辑和删除应用。只需在相应界面上进行操作即可。
