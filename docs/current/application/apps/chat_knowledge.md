# Chat Knowledge Base

`Chat Knowledge Base` 提供了基于私域知识进行问答的能力，可以基于`知识库`构建智能问答系统、阅读助手等产品。DB-GPT 中也使用了 `RAG` 技术来增强知识检索。


## 名词解释

:::info 提示

`知识空间`：是一个管理某一类知识的文档空间。同一类型的文档知识可以上传到一个知识空间中。
:::


## 步骤
知识库操作流程相对简单，主要分为以下几个步骤。
- 1.创建知识空间
- 2.上传文档
- 3.等待文档向量化
- 4.选择知识库应用
- 5.与应用对话


### 创建知识空间

首先打开`构建应用`，选择顶部的`知识`。

<p align="center">
  <img src={'/img/app/knowledge_build_v0.6.jpg'} width="800px" />
</p>

选择知识库，点击`创建`按钮，填写必要信息即可完成知识空间的创建。


<p align="center">
  <img src={'/img/app/knowledge_space_v0.6.jpg'} width="800px" />
</p>

### 上传文档

文档添加目前支持多种类型，如纯文本、URL 抓取，以及 PDF、Word、Markdown 等多种文档类型。选择特定文档进行`上传`。

<p align="left">
  <img src={'/img/chat_knowledge/upload_doc.png'} width="720px" />
</p>


选择一个或多个相应文档，点击`下一步`。


<p align="left">
  <img src={'/img/chat_knowledge/upload_doc_finish.png'} width="720px" />
</p>

### 文档分段

选择文档分段方式，您可以根据块大小、分隔符、段落或 Markdown 标题对文档进行分段。默认为按块大小进行分段。

然后点击处理，将需要几分钟时间完成文档分段。

<p align="left">
  <img src={'/img/chat_knowledge/doc_segmentation.png'} width="720px" />
</p>

:::tip
**自动：根据文档类型自动分段。**

**块大小：文档每段包含的单词数。默认为 512 个词。**
    - chunk size：文档每段包含的单词数。默认为 512 个词。
    - chunk overlap：文档每段之间重叠的单词数。默认为 50 个词。
**分隔符：按分隔符分段**
    - separator：文档的分隔符。默认为 `\n`。
    - enable_merge：是否在分割后根据 chunk_size 合并分隔符块。默认为 `False`。
**页面：按页面分段，仅支持 .pdf 和 .pptx 文档。**

**段落：按段落分段，仅支持 .docx 文档。**
    - separator：文档的段落分隔符。默认为 `\n`。

**Markdown 标题：按 Markdown 标题分段，仅支持 .md 文档。**
:::


### 等待文档向量化

点击`知识空间`，在左下角观察文档`切片`+`向量化`状态。当状态达到 `FINISHED` 时，即可开始知识库对话。


<p align="left">
  <img src={'/img/chat_knowledge/waiting_doc_vector.png'} width="720px" />
</p>


### 知识库对话

点击`对话`按钮，开始与知识库进行对话。


<p align="left">
  <img src={'/img/chat_knowledge/chat.png'} width="720px" />
</p>


### 阅读助手
除了以上功能外，您还可以在知识库对话窗口中直接上传文档，文档将默认被汇总。此功能可作为`阅读助手`辅助文档阅读。

<p align="left">
  <img src={'/img/chat_knowledge/read_helper.gif'} width="720px" />
</p>
