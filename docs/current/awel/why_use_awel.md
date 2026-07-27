# 为什么使用 AWEL？

AWEL（Agentic Workflow Expression Language）是一套专门为 LLM 应用开发设计的智能体工作流表达式语言。在 DB-GPT 的设计中，Agent 被视为一等公民。RAG、数据源（DS）、SMMF（面向服务的多模型管理框架）和插件都是 Agent 所依赖的资源。

我们目前也看到，多 Agent 的自动编排能力在很大程度上受到模型能力的限制，同时对于需要确定性的场景，例如管道类任务，并不需要利用大模型的自动编排能力。因此，在 DB-GPT 中，AWEL 与 Agent 的结合可以满足生产级管道的实现以及解决开放式问题的 Agent 系统的自动编排。

通过 AWEL 的编排能力，可以用最少的代码开发大语言模型应用。

**AWEL 和 Agent 就是您所需要的一切**。
