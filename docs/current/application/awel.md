# 使用数据应用与 AWEL

## 什么是 AWEL？

> 智能体工作流表达式语言（AWEL）是一套专为大模型应用开发设计的智能体工作流表达式语言。

如果您想了解更多关于 AWEL 的信息，可以查看 [AWEL](../awel/awel.md) 和 [AWEL 教程](../awel/tutorial/)。

简而言之，您可以使用 AWEL Python API 来开发 LLM 应用。

## 什么是 AWEL Flow？

AWEL Flow 允许您无需编写代码即可开发 LLM 应用。它构建在 AWEL Python API 之上。


## 在 `AWEL Flow` 页面查看您的 AWEL Flow

在 `AWEL Flow` 页面，您可以查看所有已创建的 AWEL Flow。您也可以通过点击 `Create Flow` 按钮创建新的 AWEL Flow。


<p align="left">
  <img src={'/img/application/awel/awel_flow_page.png'} width="720px"/>
</p>


## 示例

### 构建您的 RAG 应用

要构建您的 RAG 应用，您需要首先按照[聊天知识库](./apps/chat_knowledge.md)创建一个知识空间。
然后，点击 `Create Flow` 按钮创建一个新的 Flow。

在 Flow 编辑器中，您可以通过拖放节点来构建您的 RAG 应用。

1. 您将看到如下所示的空 Flow 编辑器：

<p align="left">
  <img src={'/img/application/awel/flow_dev_empty_page_img.png'} width="720px"/>
</p>

2. 将一个 `Streaming LLM Operator` 节点拖入 Flow 编辑器。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_llm_1.png'} width="720px"/>
</p>

3. 将一个 `Knowledge Operator` 节点拖入 Flow 编辑器。

您可以点击 `Streaming LLM Operator` 节点第二个输入（`"HOContext"`）中的 "+" 按钮，
它会显示可以连接到当前节点输入的节点列表，然后您可以选择 `Knowledge Operator` 节点。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_llm_2_.png'} width="720px"/>
</p>

可以连接的节点选项如下：

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_llm_3.png'} width="720px"/>
</p>

然后，拖入 `Knowledge Operator` 节点并将其连接到 `Streaming LLM Operator` 节点。

<p align="left">
  <img src={'/img/application/awel/flow_def_rag_ko_1.png'} width="720px"/>
</p>

请在 `Knowledge Operator` 节点的 `Knowledge Space Name` 选项中选择您的知识空间。

4. 将一个 `Common LLM Http Trigger` 节点拖入 Flow 编辑器。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_ko_2.png'} width="720px"/>
</p>

4. 将一个 `Common Chat Prompt Template` **资源**节点拖入 Flow 编辑器。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_prompt_1.png'} width="720px"/>
</p>

您可以在 `Common Chat Prompt Template` 参数中键入您的提示模板。

5. 将一个 `OpenAI Streaming Output Operator` 节点拖入 Flow 编辑器。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_output_1.png'} width="720px"/>
</p>

6. 点击右上角的 `Save` 按钮保存您的 Flow。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_save_1.png'} width="720px"/>
</p>

最后，您将在 `AWEL Flow` 页面看到您的 RAG 应用。

<p align="left">
  <img src={'/img/application/awel/flow_dev_rag_show_1.png'} width="720px"/>
</p>

之后，您可以根据[应用管理](./apps/app_manage.md)使用它来构建您的应用。

## 参考

- [AWEL](../awel/awel.md)
- [AWEL CookBook](../awel/cookbook/)
- [AWEL 教程](../awel/tutorial/)

---

📖 想了解更多关于 AWEL 的内容？查看 [AWEL 教程](../awel/tutorial/)，从基础到高级模式的分步指南。
