# 发布 V0.5.0 | 通过工作流和 Agent 开发原生数据应用

## V0.5.0 版本发布说明
经过一段时间的密集开发，0.5.0 版本历时两个多月终于面世。这是 DB-GPT 项目中第一个将在较长时期内维护的稳定版本。同时，DB-GPT 的长期愿景正式确立：旨在成为利用 Agentic Workflow Expression Language (AWEL) 和 Agent 的 AI 原生数据应用开发框架。
本质上，该框架通过基于智能 Agent 的表达式语言，促进以数据为中心的应用程序的创建。

<p align="left">
  <img src={'/img/app/app_list.png'} width="720px" />
</p>

## 版本更新介绍

在早期版本中，DB-GPT 项目提供了六个默认用例，分别是：
- [ChatData](https://docs.dbgpt.site/docs/application/started_tutorial/chat_data)
- [ChatExcel](https://docs.dbgpt.site/docs/application/started_tutorial/chat_excel)
- [ChatDB](https://docs.dbgpt.site/docs/application/started_tutorial/chat_db)
- [ChatKnowledge](https://docs.dbgpt.site/docs/application/started_tutorial/chat_knowledge)
- [ChatAgents](https://docs.dbgpt.site/docs/agents)
- [ChatDashboard](https://docs.dbgpt.site/docs/application/started_tutorial/chat_dashboard)

这些场景旨在满足基础简单的使用需求。然而，对于大规模生产部署，尤其是在处理复杂业务场景时，需要根据特定业务情况开发定制场景。这在灵活性和开发复杂性方面带来了重大挑战。

为了进一步提升业务框架的易用性和灵活性，我们在现有功能（包括多模型管理 (SMMF)、知识库、Agent、数据源、插件和 Prompt）的基础上，抽象了智能 Agent 编排 (AWEL) 和应用构建的能力。此外，为了方便应用管理和分发，我们引入了 [dbgpts](https://github.com/eosphoros-ai/dbgpts) 子项目，专门管理在 DB-GPT 之上构建的原生智能数据应用、AWEL 通用算子、AWEL 通用工作流模板和 Agent。

本次版本更新不会影响之前建立的六个场景的使用。但随着后续迭代，这些默认场景将逐步被重写为 Data App。我们还计划将它们作为默认应用纳入 `dbgpts` 项目，使其随时可供安装和使用。

现在，让我们系统性地介绍本次本地版本的主要更新。

### 术语表：

1. **Data App**：基于 DB-GPT 构建的智能数据应用。
2. **AWEL**：Agentic Workflow Expression Language，智能工作流表达式语言。
3. **AWEL Flow**：使用智能工作流表达式语言进行的工作流编排。
4. **SMMF**：面向服务的多模型管理框架 (Service-oriented Multi-model Management Framework)。
5. **Datasource**：数据源，例如 MySQL、PG、StarRocks 和 Clickhouse。

## AWEL 工作流和应用
如下图所示，在左侧导航栏中，有一个 AWEL 工作流菜单。打开后，您可以编排工作流。

<p align="left">
  <img src={'/img/app/awel_flow_list.png'} width="720px" />
</p>

默认安装后，AWEL 流中没有内容。您可以通过两种方式构建。
1. 从 DB-GPT 提供的应用仓库安装。
2. 自行创建。以下介绍这两种方法的简单使用。更详细的使用方法，请参见 DB-GPT 相关教程。

<p align="left">
  <img src={'/img/app/flow_detail.png'} width="720px" />
</p>

### 从官方仓库安装：

确保您已首先安装并部署了 DB-GPT。
安装部署完成后，您可以使用默认的 `dbgpt` 命令进行各种操作。

:::info 注意

此过程将允许您后续安装 AWEL 工作流。
:::

<p align="left">
  <img src={'/img/app/dbgpts_cli.png'} width="720px" />
</p>

如图所示，dbgpt 命令支持多种操作，包括模型相关操作、知识库操作和 Trace 日志。这里我们重点介绍 app 的操作。

<p align="left">
  <img src={'/img/app/dbgpts_apps.png'} width="720px" />
</p>

通过 `dbgpt app list-remote` 命令，我们可以看到当前仓库中有三个可用的 AWEL 工作流。这里我们安装 `awel-flow-web-info-search` 这个工作流。运行命令 `dbgpt app install awel-flow-web-info-search`。

<p align="left">
  <img src={'/img/app/dbgpts_app_install.png'} width="720px" />
</p>

安装成功后，重启 DB-GPT 服务（动态热加载即将推出），刷新页面，然后在 `AWEL 工作流页面` 中可以看到对应的工作流。

<p align="left">
  <img src={'/img/app/dbgpts_flow_black.png'} width="720px" />
</p>

### 构建您自己的工作流

除了使用官方命令安装默认的 AWEL 流之外，在实际场景中您通常还需要构建自己的工作流。如下图所示，点击 `新建 AWEL 流程`，您将进入如图所示的编辑页面。

<p align="left">
  <img src={'/img/app/awel_flow_node.png'} width="720px" />
</p>

在编辑过程中，每个任务的下游节点和算子都支持自动补全。通过点击每个算子右下角的加号 (➕)，可以弹出可连接到当前算子的下游算子列表。此功能通过提供建议增强了用户体验，使构建复杂工作流更加容易，无需记住可用算子的确切名称或类型。

<p align="left">
  <img src={'/img/app/awel_flow_node_plus.png'} width="720px" />
</p>

## 创建数据应用

我们介绍了 AWEL 工作流的构建和安装。接下来，我们将介绍如何创建基于大模型的数据应用。

### 搜索聊天应用
搜索对话应用的核心能力是通过搜索引擎（如百度和 Google）搜索相关知识，然后进行总结和回答。效果如下：

<p align="left">
  <img src={'/img/app/app_search.png'} width="720px" />
</p>

创建上述应用非常简单。在应用创建面板上，点击 `创建`，输入以下参数即可完成创建。需要注意几个参数：1. 工作模式 2. 流程。这里我们使用的工作模式是 `awel_layout`，选择的 AWEL 工作流是之前安装的 `awel-flow-web-info-search` 工作流。

<p align="left">
  <img src={'/img/app/app_awel.png'} width="720px" />
</p>

### 数据分析助手
使用多 Agent 编写一个数据分析助手应用。结果如下：

<p align="left">
  <img src={'/img/app/app_analysis.png'} width="720px" />
</p>

<p align="left">
  <img src={'/img/app/app_analysis_black.png'} width="720px" />
</p>

## 其他更新详情
- 发布 dbgpt core sdk (#1092)：现在包含 AWEL 算子编排能力。安装命令：`pip install dbgpt`

- 支持 Jina Embeddings (#1105)：此次更新与 Jina AI 集成，提供了一种为各种数据类型创建和管理 Embedding 的方式，增强了应用中的搜索和相似性任务。

- 使用 AWEL 进行 schema-linking 的新示例 (#1081)：提供了一个新的示例，演示如何使用 AWEL 进行 schema-linking，这对于需要映射不同数据模式的任务非常有价值。

- 统一卡片 UI 样式，包括知识库卡片、模型管理卡片等：此更新使以卡片格式显示信息的各种 UI 组件具有更一致的外观和感觉。

## Bug 修复
- MySQL 数据库不再支持自动建表和字段自动更新 (#1133)：此更改可能需要开发人员手动处理数据库模式更改，从而更好地控制数据库迁移。

- 修复了默认对话携带历史消息记录的问题 (#1117)：通过确保正确处理历史记录，解决了潜在的隐私或性能问题。

- 修复了 examples/awel 中 model_name 从 model_config 错误获取的问题 (#1112)：通过确保正确获取和使用模型配置，提高了 AWEL 示例的可靠性。

- 修复了 DAG 共享数据的问题 (#1102)：此修复涉及有向无环图 (DAG) 中的数据隔离，确保工作流不会无意中共享或覆盖数据。

- 修复了 examples/awel 默认加载模型 text2vec-large-chinese 的问题 (#1095)：此修复确保在给定示例中正确加载大型中文文本到向量模型。

这些更改反映了 dbgpt 项目的持续改进，增强了其能力，修复了已知问题，并优化了用户体验。用户应参考官方文档或发布说明以获取关于这些更新的详细说明和信息。

## 升级到 V0.5.0

如果您当前的版本是 V0.4.6 或 V0.4.7，则需要升级到 V0.5.0。
1. 暂停服务
2. 升级数据库表结构

```sql
-- dbgpt.dbgpt_serve_flow 定义
CREATE TABLE `dbgpt_serve_flow` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增 id',
  `uid` varchar(128) NOT NULL COMMENT '唯一 id',
  `dag_id` varchar(128) DEFAULT NULL COMMENT 'DAG id',
  `name` varchar(128) DEFAULT NULL COMMENT '流程名称',
  `flow_data` text COMMENT '流程数据，JSON 格式',
  `user_name` varchar(128) DEFAULT NULL COMMENT '用户名',
  `sys_code` varchar(128) DEFAULT NULL COMMENT '系统代码',
  `gmt_created` datetime DEFAULT NULL COMMENT '记录创建时间',
  `gmt_modified` datetime DEFAULT NULL COMMENT '记录更新时间',
  `flow_category` varchar(64) DEFAULT NULL COMMENT '流程类别',
  `description` varchar(512) DEFAULT NULL COMMENT '流程描述',
  `state` varchar(32) DEFAULT NULL COMMENT '流程状态',
  `source` varchar(64) DEFAULT NULL COMMENT '流程来源',
  `source_url` varchar(512) DEFAULT NULL COMMENT '流程来源 url',
  `version` varchar(32) DEFAULT NULL COMMENT '流程版本',
  `label` varchar(128) DEFAULT NULL COMMENT '流程标签',
  `editable` int DEFAULT NULL COMMENT '可编辑，0：可编辑，1：不可编辑',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_uid` (`uid`),
  KEY `ix_dbgpt_serve_flow_sys_code` (`sys_code`),
  KEY `ix_dbgpt_serve_flow_uid` (`uid`),
  KEY `ix_dbgpt_serve_flow_dag_id` (`dag_id`),
  KEY `ix_dbgpt_serve_flow_user_name` (`user_name`),
  KEY `ix_dbgpt_serve_flow_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- dbgpt.gpts_app 定义
CREATE TABLE `gpts_app` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增 id',
  `app_code` varchar(255) NOT NULL COMMENT '当前 AI 助手代码',
  `app_name` varchar(255) NOT NULL COMMENT '当前 AI 助手名称',
  `app_describe` varchar(2255) NOT NULL COMMENT '当前 AI 助手描述',
  `language` varchar(100) NOT NULL COMMENT 'gpts 语言',
  `team_mode` varchar(255) NOT NULL COMMENT '团队工作模式',
  `team_context` text COMMENT '不同工作模式的团队所依赖的执行逻辑和团队成员内容',
  `user_code` varchar(255) DEFAULT NULL COMMENT '用户代码',
  `sys_code` varchar(255) DEFAULT NULL COMMENT '系统应用代码',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  `updated_at` datetime DEFAULT NULL COMMENT '最后更新时间',
  `icon` varchar(1024) DEFAULT NULL COMMENT '应用图标，url',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts_app` (`app_name`)
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `gpts_app_collection` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '自增 id',
  `app_code` varchar(255) NOT NULL COMMENT '当前 AI 助手代码',
  `user_code` int(11) NOT NULL COMMENT '用户代码',
  `sys_code` varchar(255) NOT NULL COMMENT '系统应用代码',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  `updated_at` datetime DEFAULT NULL COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_app_code` (`app_code`),
  KEY `idx_user_code` (`user_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT="gpt 收藏";

-- dbgpt.gpts_app_detail 定义
CREATE TABLE `gpts_app_detail` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增 id',
  `app_code` varchar(255) NOT NULL COMMENT '当前 AI 助手代码',
  `app_name` varchar(255) NOT NULL COMMENT '当前 AI 助手名称',
  `agent_name` varchar(255) NOT NULL COMMENT 'Agent 名称',
  `node_id` varchar(255) NOT NULL COMMENT '当前 AI 助手 Agent 节点 id',
  `resources` text COMMENT 'Agent 绑定资源',
  `prompt_template` text COMMENT 'Agent 绑定模板',
  `llm_strategy` varchar(25) DEFAULT NULL COMMENT 'Agent 使用 llm 策略',
  `llm_strategy_value` text COMMENT 'Agent 使用 llm 策略值',
  `created_at` datetime DEFAULT NULL COMMENT '创建时间',
  `updated_at` datetime DEFAULT NULL COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gpts_app_agent_node` (`app_name`,`agent_name`,`node_id`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

```SQL
ALTER TABLE `gpts_conversations`
ADD COLUMN `team_mode` varchar(255) NULL COMMENT 'agent 团队工作模式';

ALTER TABLE `gpts_conversations`
ADD COLUMN  `current_goal` text COMMENT '当前消息对应的目标';
```

3. 重新安装依赖

```shell
pip install -e ".[default]"
```

4. 启动服务

## 致谢
我们向所有使此版本成为可能的贡献者表示最深切的感谢！

@Aralhi, @Aries-ckt, @JoanFM, @csunny, @fangyinc, @Hzh_97, @junewgl, @lcxadml, @likenamehaojie, @xiuzhu9527 和 @yhjun1026

## 附录
- DB-GPT 框架：https://github.com/eosphoros-ai
- Text2SQL 微调：https://github.com/eosphoros-ai/DB-GPT-Hub
- DB-GPT-Web：https://github.com/eosphoros-ai/DB-GPT-Web
- 官方英文文档：http://docs.dbgpt.site/docs/overview
- 官方中文文档：https://www.yuque.com/eosphoros/dbgpt-docs/bex30nsv60ru0fmx
