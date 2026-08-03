# Data App 开发指南

在本文档中，我们将指导您使用 DB-GPT 开发数据分析应用的完整流程。

# 目标

在本案例中，我们的目标是构建一个包含以下能力的数据助手应用：
1. 基于文档的智能问答。
2. 基于数据库进行数据对话。
3. 基于工具使用的互联网搜索。

这三种能力可以在同一对话中基于 DB-GPT 提供的意图识别能力进行调用。数据助手会根据用户的提问，匹配相应的子 Agent 应用来回答对应领域的问题。

:::tip
注意：本案例主要用于应用构建的演示目的，生产环境中的实际应用仍需进一步优化。
:::

# 准备工作

在开始构建应用之前，您首先需要完成项目的安装和部署。相关教程请参考[部署文档](../../installation/sourcecode.md)。

# 子数据应用构建

首先，我们需要分别创建三个子智能应用，然后利用 AppLink 提供的意图识别能力，将这些智能应用集成为一个统一的智能实体，统一对话交互入口。

## 1. 构建基于 RAG 的问答助手

我们使用 DB-GPT 提供的 Agent 模块来构建基于 RAG 的问答助手。DB-GPT 内置了一些 Agent，例如：

- 意图识别专家 Agent
- CodeEnginner Agent
- 报告生成器 Agent
- 数据科学家 Agent
- 文档摘要 Agent
- 工具专家 Agent
- ...

在本案例中，智能问答主要依赖于领域知识库和文档摘要 Agent (Summarizer)，因此我们首先需要构建领域知识库。流程如下：

1. 领域知识清洗与整理
2. 上传到 DB-GPT 知识库
3. 创建基于知识的数据应用
4. 与 KBQA 对话

### 领域知识清洗与整理
领域知识的整理和处理是一项非常重要的任务，对最终效果有着非常重要的影响。您需要根据实际应用来整理和清理文件。在本示例中，我们使用默认的 PDF 进行上传。我们准备官方 DB-GPT 文档作为演示材料。

### 创建知识库

在产品界面上，选择知识库，点击[创建知识]，填写相应参数。我们提供多种存储类型：1. Embedding 向量 2. 知识图谱 3. 全文检索。在本示例中，我们使用 Embedding 方案进行构建。

<p align="center">
  <img src={'/img/cookbook/knowledge_base.png'} width="800" />
</p>

填写相应参数后，点击[下一步]选择文档类型并上传文档。

<p align="center">
  <img src={'/img/cookbook/knowledge_base_upload.png'} width="800" />
</p>

选择合适的分片方式，等待文档上传完成。至此，我们的知识库已构建完成，可以进行后续的智能问答应用了。

<p align="center">
  <img src={'/img/cookbook/knowledge_base_success.png'} width="800" />
</p>

### 创建 KBQA 应用

选择[应用管理] -> [创建应用]，在弹出对话框中选择单 Agent 模式。

<p align="center">
  <img src={'/img/cookbook/app_create_with_agent.png'} width="800" />
</p>

点击[确定]，在弹出的对话框中：
1. 选择 Summarizer Agent
2. Prompt 默认为空，如需修改可先自定义 Prompt。关于 Prompt 定义的教程，请参见文档。
3. 模型策略：支持多种模型策略，如果有多个模型，可按优先级配置。
4. 添加资源：本案例中我们依赖之前创建的知识库，因此选择资源类型[知识]，参数为刚创建的知识库名称。
5. 添加推荐问题，[是否生效]控制推荐问题的有效性。

<p align="center">
  <img src={'/img/cookbook/qa_app_build_parameters.png'} width="800" />
</p>

点击[保存]完成智能应用的创建。

### 开始对话

<p align="center">
  <img src={'/img/cookbook/qa_app_chat.png'} width="800" />
</p>

:::tip
注意：本教程中展示的 Agent 应用是基于 Summarizer Agent 构建的。Summarizer Agent 是 DB-GPT 的内置 Agent，相关代码实现请参见[源代码](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/expand/summary_assistant_agent.py)。在实际使用中，可以根据具体场景对相关代码进行进一步修改和优化，或基于本案例自定义 Agent。
:::

## 数据对话机器人助手

同样，可以基于类似思路构建数据对话助手。数据对话助手可以基于数据库进行简单的数据对话并绘制相应图表。主要包括以下步骤：

1. 数据准备
2. 创建数据源
3. 创建数据聊天应用
4. 对话

### 数据准备

关于数据准备，请参考文档中的[数据准备](https://github.com/eosphoros-ai/DB-GPT/blob/main/docker/examples/dashboard/test_case_mysql_data.py)部分。

### 创建数据源

准备数据后，需要将数据库添加到数据源中供后续使用。选择[应用管理] -> [数据库] -> [添加数据源]。

<p align="center">
  <img src={'/img/cookbook/datasource.png'} width="800" />
</p>

### 创建数据聊天应用

如下图所示，选择[应用管理] -> [应用] -> [创建应用]，选择单 Agent 应用，填写相应参数，点击确定。

<p align="center">
  <img src={'/img/cookbook/data_app_create.png'} width="800" />
</p>

依次选择相应参数：
- Agent：选择 `DataScientist` Agent
- Prompt：默认为空，自定义请参考 Prompt 管理教程。
- 模型策略：此处选择优先级策略，可按优先级使用 `proxyllm` 和 `tongyi_proxyllm` 模型。
- 可用资源：选择数据库类型作为资源类型，参数选择之前添加的数据库。
- 推荐问题：可根据数据情况设置默认问题。

<p align="center">
  <img src={'/img/cookbook/data_app_build_parameters.png'} width="800" />
</p>

### 开始对话

点击开始对话，输入相应问题进行数据问答。

<p align="center">
  <img src={'/img/cookbook/data_app_chat.png'} width="800" />
</p>

## 搜索助手

天气助手需要调用搜索引擎查询相关信息，因此需要设计工具调用，构建过程相对复杂。为简化应用创建，我们将相关能力构建到 AWEL 工作流中，可以直接安装使用。

### 安装 AWEL 工作流

首先执行命令 `dbgpt app list-remote` 查看远程仓库中的所有 AWEL 示例流程。`awel-flow-web-info-search` 提供了互联网搜索能力。

```
dbgpt app list-remote

┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃           存储库  ┃ 类型       ┃                               名称 ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ eosphoros/dbgpts │ operators │               awel-simple-operator │
│ eosphoros/dbgpts │ resources │                    jina-web-reader │
│ eosphoros/dbgpts │ resources │          simple-calculator-example │
│ eosphoros/dbgpts │ workflow  │                all-in-one-entrance │
│ eosphoros/dbgpts │ workflow  │        andrewyng-translation-agent │
│ eosphoros/dbgpts │ workflow  │             awel-flow-example-chat │
│ eosphoros/dbgpts │ workflow  │         awel-flow-rag-chat-example │
│ eosphoros/dbgpts │ workflow  │      awel-flow-rag-summary-example │
│ eosphoros/dbgpts │ workflow  │    awel-flow-simple-streaming-chat │
│ eosphoros/dbgpts │ workflow  │          awel-flow-web-info-search │
│ eosphoros/dbgpts │ workflow  │                 db-expert-assisant │
│ eosphoros/dbgpts │ workflow  │ financial-report-knowledge-factory │
│ eosphoros/dbgpts │ workflow  │                financial-robot-app │
│ eosphoros/dbgpts │ workflow  │             rag-save-url-to-vstore │
│ eosphoros/dbgpts │ workflow  │          rag-url-knowledge-example │
└──────────────────┴───────────┴────────────────────────────────────┘

```

执行 `dbgpt app install awel-flow-web-info-search` 命令在本地安装。

```
dbgpt app install awel-flow-web-info-search

> 
  Installing collected packages: awel-flow-web-info-search
  Successfully installed awel-flow-web-info-search-0.1.0
  Installed dbgpts at ~/.dbgpts/packages/ae442685cde998fe51eb565a23180544/awel-flow-web-info-search.
  dbgpts 'awel-flow-web-info-search' installed successfully.
```

刷新界面，在 AWEL 工作流界面中可以看到对应的工作流已安装。

<p align="center">
  <img src={'/img/cookbook/awel_web_search.png'} width="800" />
</p>

点击该 AWEL 工作流，我们可以查看里面的内容。简要说明如下：

1. Agent Resource：Agent 依赖的资源，此处为 baidu_search
2. ToolExpert：工具专家，用于实现工具调用。
3. Summarizer Agent：用于总结查询结果。

总结：此 AWEL 工作流使用了 ToolExpert 和 Summarizer 两个 Agent。ToolExpert 依赖内置工具 baidu_search，Summarizer 进一步总结工具专家的执行结果并生成最终答案。

<p align="center">
  <img src={'/img/cookbook/awel_web_search_tool.png'} width="800" />
</p>

### 创建搜索助手

同时，[创建应用] -> [任务流编排模式]

<p align="center">
  <img src={'/img/cookbook/search_app.png'} width="800" />
</p>

选择对应的工作流，添加推荐问题，点击保存。

<p align="center">
  <img src={'/img/cookbook/search_app_build.png'} width="800" />
</p>

### 对话
<p align="center">
  <img src={'/img/cookbook/search_app_chat.png'} width="800" />
</p>

# 统一智能应用构建

根据上述流程，我们已经为每个子场景创建了智能应用，但在实际应用中，我们需要在统一入口完成所有问答，因此需要集成这些子领域的 Agent，通过 AppLink 和意图识别能力统一交互入口。

为了实现问题路由，核心能力是意图识别和分类。为使应用构建在设计上更加灵活，我们提供了基于知识库和 Agent 的意图识别和分类能力，并支持基于 AWEL 的自定义。

### 构建意图知识库

要实现意图分类并将用户问题路由到相应的智能应用，我们首先需要定义和描述每个应用的能力。这里通过知识库进行构建。以下是一个简单的意图定义文档，用于描述每个智能应用的能力。需要填写四种主要信息：

1. Intent：意图类型

2. App Code：可在应用界面中复制。

<p align="center">
  <img src={'/img/cookbook/app_code.png'} width="800" />
</p>

3. Describe：描述 Agent 的能力。

4. Slots：槽位信息，用于表示 Agent 在实际问答中依赖的参数，如天气查询中需要的[时间]和[位置]信息。

```
#######################
Intent:DB答疑 App Code:a41d0274-8ac4-11ef-8735-3ea07eeef889 Describe: 所有DB领域相关知识的咨询答疑，包含了日常DBA的FAQ问题数据、OceanBase(OB)的官方文档手册，操作手册、问题排查手册、日常疑难问题的知识总结、可以进行专业的DBA领域知识答疑。 只要和DB相关的不属于其他应用负责范畴的都可以使用我来回答 问题范例: 1.怎么查看OB抖动？ 2.DMS权限如何申请 3.如何确认xxxxx 类型:知识库咨询
#######################
Intent:数据对话 App Code:516963c4-8ac9-11ef-8735-3ea07eeef889 Describe: 通过SQL查询分析当前数据库(dbgpt-test:包含用户和用户销售订单数据的数据库） 类型:数据查询
#######################
Intent:天气检索助手 App Code:f93610cc-8acc-11ef-8735-3ea07eeef889 Describe: 可以进行天气查询 Slots:
位置: 要获取天气信息的具体位置
时间: 要获取的天气信息的时间，如果没有明确提到，使用当前时间

```

### 创建意图分类知识库

如下图所示，创建意图分类知识库。

<p align="center">
  <img src={'/img/cookbook/app_intent_knowledge.png'} width="800" />
</p>

需要注意的是，分隔符需要使用我们自定义的分隔符，即文档中的 #。

<p align="center">
  <img src={'/img/cookbook/chunk_sep.png'} width="800" />
</p>

### AWEL 工作流安装编辑器
同样，为简化使用，我们编写了对应的意图识别 AWEL 工作流，可以直接安装使用。

```
dbgpt app install db-expert-assisant

> Installing collected packages: db-expert-assisant
Successfully installed db-expert-assisant-0.1.0
Installed dbgpts at ~/.dbgpts/packages/ae442685cde998fe51eb565a23180544/db-expert-assisant.
dbgpts 'db-expert-assisant' installed successfully.
```

打开前端界面，在 AWEL 工作流界面中，我们可以看到 db_expert_assisant。为了方便后续编辑，我们复制一个流程进行编辑。点击右上角的[复制]，自定义名称和描述，完成复制。

<p align="center">
  <img src={'/img/cookbook/awel_db_expert.png'} width="800" />
</p>

我们打开复制的 AWEL 流程，此处命名为 `db_expert_assistant_v1`，打开工作流。我们可以看到以下编排流程。同样，此工作流使用以下 Agent：

1. `Intent Recognition Expert`：意图识别专家，专门用于意图识别。它依赖知识库资源，即我们之前定义的意图识别知识库资源。

2. `AppLauncher`：用于调用各领域的专家。

3. `Summarizer`：总结整个问答。如果所有场景都没有匹配到路由，将基于数据库知识库给出默认答案。

<p align="center">
  <img src={'/img/cookbook/awel_expert_v1.png'} width="800" />
</p>

### 应用创建

创建应用并选择任务流编排模式。

<p align="center">
  <img src={'/img/cookbook/data_app_build.png'} width="800" />
</p>

点击确定，选择工作流，输入推荐问题，保存。

<p align="center">
  <img src={'/img/cookbook/data_app_awel.png'} width="800" />
</p>

### 对话
<p align="center">
  <img src={'/img/cookbook/data_expert_chat.png'} width="800" />
</p>
