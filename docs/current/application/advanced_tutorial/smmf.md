# SMMF

DB-GPT 项目提供了面向服务的多模型管理能力。对相关能力感兴趣的开发者可以阅读 [SMMF](../../modules/smmf.md) 模块部分。这里我们重点介绍如何使用多 LLM。

这里我们主要通过 Web 界面介绍用法。对命令行感兴趣的开发者可以参考[集群部署](../../installation/model_service/cluster.md)模式。打开 DB-GPT-Web 前端服务，点击 `Model Management` 进入多模型管理界面。


## 列出模型
打开模型管理界面，我们可以查看当前已部署的模型列表。以下是模型列表。

<p align="left">
  <img src={'/img/module/model_list.png'} width="720px"/>
</p>

## 使用模型
模型部署完成后，您可以在多模型界面上切换和使用相应的模型。

<p align="left">
  <img src={'/img/module/model_use.png'} width="720px"/>
</p>

## 停止模型
如下图所示，点击模型管理进入模型列表界面。选择特定模型，点击红色的 `Stop Model` 按钮即可停止模型。

<p align="left">
  <img src={'/img/module/model_stop.png'} width="720px"/>
</p>

模型停止后，右上角的显示会发生变化。

<p align="left">
  <img src={'/img/module/model_stopped.png'} width="720px"/>
</p>

## 模型部署

 1. 打开网页，点击左侧的 `model management` 按钮进入模型列表页面，点击左上角的 `Create Model`，然后在弹出的对话框中选择要部署的模型名称。这里我们选择 `vicuna-7b-v1.5`，如图所示。

    <p align="left">
    <img src={'/img/module/model_vicuna-7b-1.5.png'} width="720px"/>
    </p>


2. 根据实际部署的模型选择合适的参数（如果不确定，使用默认值即可），然后点击对话框左下角的 `Submit` 按钮，等待模型部署成功。

3. 新模型部署完成后，您可以在模型页面上看到新部署的模型，如图所示

    <p align="left">
    <img src={'/img/module/model_vicuna_deployed.png'} width="720px"/>
    </p>

# 运维与可观测性

运维和可观测性是生产系统的重要组成部分。在运维能力方面，除了 Web 界面上提供的常见管理功能外，DB-GPT 还提供了一个名为 dbgpt 的命令行工具用于运维和管理。dbgpt 命令行工具提供以下功能：

- 启动和停止各种服务
- 知识库管理（批量导入、自定义导入、查看和删除知识库文档）
- 模型管理（查看、启动、停止模型，以及进行调试对话）
- 可观测性工具（查看和分析可观测性日志）

这里我们不详细介绍命令行工具的使用。您可以使用 `dbgpt --help` 命令获取具体的使用文档。此外，您还可以查看各个子命令的文档。例如，您可以使用 `dbgpt start --help` 查看启动服务的文档。更多信息请参考以下文档。

- [调试](../advanced_tutorial/debugging.md)
