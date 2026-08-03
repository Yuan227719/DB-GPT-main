# DB-GPT V0.6.0，定义 AI 原生数据应用的新标准。

## 介绍

DB-GPT 是一个开源的 AI 原生数据应用开发框架，集成了 AWEL 和 Agent。在 V0.6.0 版本中，我们进一步提供了围绕大模型的灵活可扩展的 AI 原生数据应用管理和开发能力，可以帮助企业快速构建和部署智能 AI 数据应用，并通过智能数据分析、洞察和决策实现企业数字化转型和业务增长。

### V0.6.0 版本主要增加和增强了以下核心功能

- AWEL 协议升级 2.0，支持更复杂的编排

- 支持数据应用的创建和生命周期管理，并支持多种应用构建模式，例如：多 Agent 自动规划模式、任务流编排模式、单 Agent 模式、原生应用模式

- GraphRAG 支持图谱社区摘要和混合检索，图谱索引成本相比 Microsoft GraphRAG 降低 50%

- 支持多种 Agent 记忆，如感知记忆、短期记忆、长期记忆、混合记忆等

- 支持意图识别和 Prompt 管理，新增支持 Text2NLU 和 Text2GQL 微调

- GPT-Vis 前端可视化升级，支持更丰富的可视化图表

<p align="center">
  <img src={'/img/app/app_chat_v0.6.jpg'} width="800px" />
</p>

## 功能特性

**AWEL 协议升级 2.0 支持更复杂的编排，并优化了前端可视化和交互能力。**

AWEL (Agentic Workflow Expression Language) 是一种基于 Agent 的工作流表达式语言，专门为大模型应用开发设计，提供了强大的功能和灵活性。通过 AWEL API，开发者可以专注于大模型应用逻辑开发，无需关注繁琐的模型、环境等细节。在 AWEL2.0 中，我们支持更复杂的编排和可视化。

<p align="center">
  <img src={'/img/app/agent_prompt_awel_v0.6.jpg'} width="800px" />
</p>

**支持数据应用的创建和生命周期管理，并支持多种模式构建应用，例如：多 Agent 自动规划模式、任务流编排模式、单 Agent 模式、原生应用模式**

<p align="center">
  <img src={'/img/app/app_manage_mode_v0.6.jpg'} width="800px" />
</p>

<p align="center">
  <img src={'/img/app/app_manage_app_v0.6.jpg'} width="800px" />
</p>

**GraphRAG 支持图谱社区摘要和混合检索。**

图谱构建和检索性能相比社区方案具有明显优势，并支持酷炫的可视化。GraphRAG 是基于知识图谱的增强检索生成系统。通过知识图谱的构建和检索，进一步增强检索的准确性和召回的稳定性，同时减少大模型的幻觉，增强领域应用效果。DB-GPT 与 TuGraph 结合，构建高效的检索增强生成能力。

<p align="center">
  <img src={'/img/app/graph_rag_pipeline_v0.6.png'} width="800px" />
</p>

基于 DB-GPT 0.5.6 版本推出的集成向量索引、图索引和全文索引的通用 RAG 框架，DB-GPT 0.6.0 版本增强了图索引 (GraphRAG) 的能力，支持图谱社区摘要和混合检索能力。在新版本中，我们引入了 TuGraph 内置的 Leiden 社区发现算法，结合大模型提取社区子图摘要，最终利用社区摘要的相似性召回应对泛化提问场景，即 QFS (Query Focused Summarization) 问题。此外，在知识提取阶段，我们将原有的三元组提取升级为带点边信息摘要的图提取，并通过文本块历史优化跨文本块关联信息提取，进一步增强知识图谱的信息密度。

基于以上设计，我们使用了 TuGraph 社区提供的开源知识图谱语料库 (OSGraph) 以及 DB-GPT 和 TuGraph 的产品介绍材料（总计约 43k tokens），与 Microsoft 的 GraphRAG 系统进行了对比测试。最终，DB-GPT 仅消耗 50% 的 Token 开销，生成了同等规模的知识图谱。在问答测试质量相当的前提下，全局搜索性能得到了显著提升。

<p align="center">
  <img src={'/img/app/graph_rag_v0.6.png'} width="800px" />
</p>

对于最终生成的知识图谱，我们使用了 AntV 的 G6 引擎升级了前端渲染逻辑，可以直观地预览知识图谱数据和社区分割结果。

<p align="center">
  <img src={'/img/app/graph_rag_display_v0.6.png'} width="800px" />
</p>

**GPT-Vis：GPT-Vis 是一个面向 LLM 和数据的交互式可视化解决方案，支持丰富的可视化图表展示和智能推荐**

<p align="center">
  <img src={'/img/app/app_chat_v0.6.jpg'} width="800px" />
</p>

**Text2GQL 和 Text2NLU 微调：新增支持从自然语言到图语言的微调，以及用于语义分类的微调。**

<p align="center">
  <img src={'/img/ft/ft_pipeline.jpg'} width="800px" />
</p>

## 如何升级？

[升级到 v0.6.0](../upgrade/v0.6.0.md)

## 用户手册
- [应用](../application/apps/app_manage.md)
- [AWEL](../awel/awel.md)
- [GraphRAG](../application/graph_rag.md)

## 致谢
本次迭代离不开社区开发者和用户的参与，同时进一步与 [TuGraph](https://github.com/TuGraph-family) 和 [AntV](https://github.com/antvis) 社区合作。感谢所有使此版本成为可能的贡献者！

@Aries-ckt, @Dreammy23, @Hec-gitHub, @JxQg, @KingSkyLi, @M1n9X, @bigcash, @chaplinthink, @csunny, @dusens, @fangyinc, @huangjh131, @hustcc, @lhwan, @whyuds 和 @yhjun1026

## 参考
- [中文手册](https://www.yuque.com/eosphoros/dbgpt-docs/ym574wh2hddunfbd)
