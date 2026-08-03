# 蚂蚁集团数据检索基准数据集指南

对于 Text2SQL 任务，我们提供了数据集基准测试能力。它评估不同的大语言模型（LLM）和 Agent 在 Text2SQL 上的表现，涵盖语法正确性、语义准确性和执行有效性。输出可执行率和准确率等指标，并提供评估报告。

1. 蚂蚁集团开源 Text2SQL 数据集仓库：[Falcon](https://github.com/eosphoros-ai/Falcon)
2. DB-GPT 支持基于 Falcon 基准数据集进行 LLM 评估

# 简介

为了客观、公平地评估模型在 Text2SQL 任务上的表现，我们提供了一个基准测试模块和数据集。该模块支持对 DB-GPT 框架中的所有模型进行全面评估，并提供评估报告。

该模块使用的基准数据集 [Falcon](https://github.com/eosphoros-ai/Falcon) 是蚂蚁集团开源的高质量、持续演进的 Text2SQL 数据集。
该数据集旨在复杂的跨领域分析场景中对模型进行压力测试，重点关注：
 - SQL 计算挑战——多表连接、嵌套 CTE、窗口函数、排序、类型转换、正则表达式过滤...
 - 语言挑战——中文模糊时间表达、口语化业务术语、省略表达、多意图问题...

> 该基准测试包含 28 个数据集和 90 张表。截至目前，已正式发布 500 个不同难度的中文问题。
> 
> 其中：简单：151 个，中等：130 个，困难：219 个。

## 基准数据集的核心特性
-  ✅ 多维度评估：语法正确性、语义准确性、执行有效性三层检查
-  🧠 动态难度级别：来自 Kaggle 数据集的 500 个中文问题（多种难度），涵盖多步推理、复杂嵌套查询和高级 SQL 特性
-  ✍️ 详细模式注释：丰富的模式信息，包括数据类型、自然语言别名、表关系和样本数据，帮助模型理解数据库结构
-  🌐 真实场景建模：更多模糊语言表达和更多来自蚂蚁集团实际生产场景的问题（正在准备中）

# 系统设计
基准测试模块的核心能力：
- Text2SQL 评估 API：提供创建评估任务的 API
- 基准测试执行框架：基于基准问题运行 Text2SQL 任务
- 结果比较框架：比较标准答案和 LLM 生成的 SQL 之间的结果，并聚合评估结果
- 数据集安装和数据库映射：安装基准测试数据集并将数据映射到数据库中，为 LLM SQL 查询提供服务

<p align="center">
  <img src={'/img/module/benchmark.png'} width="600px" />
</p>

# 评估指标

| 指标       | 公式                             | 描述                                                          |
|------------|----------------------------------|---------------------------------------------------------------|
| 可执行率   | 语法正确的样本数 / 总样本数      | 模型生成的 SQL 语句语法正确且能在数据库中正确执行的比例         |
| 准确率     | 语义正确的样本数 / 总样本数      | 模型生成的 SQL 语句语法正确、能在数据库中正确执行且语义正确的比例 |

# 数据集结构

## 标准基准结构
| 字段       | 描述                 | 示例                                                                        |
|------------|----------------------|-----------------------------------------------------------------------------|
| 编号       | 问题序号             | 1, 2...                                                                     |
| 数据集 ID  | 数据集 ID            | D2025050900161503000025249569, ...                                          |
| 用户问题   | 问题标题             | 各性别的平均年龄是多少，并按年龄顺序显示结果？                                |
| 自定义标签 | 问题来源，SQL 类型   | KAGGLE_DS_1, CTE1                                                           |
| 知识       | 所需知识上下文       | 暂无                                                                        |
| 标准答案 SQL | 问题的正确 SQL（基于阿里云 MaxCompute 语法） | SELECT gender, AVG(age) AS avg_age FROM users GROUP BY gender ORDER BY avg_age |
| 标准结果   | 在阿里云 MaxCompute 引擎上的正确 SQL 查询结果（部分问题有多个答案） | `{"性别":["Female","Male"],"平均年龄":["27.73","27.84"]}`                   |
| 是否排序   | 问题是否涉及排序     | `{"性别":["Female","Male"],"平均年龄":[27.73,27.84]}`                       |
| prompt    | 模型对话提示         | 已知以下数据集，包含了字段名及其采样信息：...                                 |

# 如何使用

## 环境设置
- 步骤 1：升级到 V0.7.4 并升级元数据库

    对于 SQLite，默认会自动升级表结构。对于 MySQL，您需要手动执行 DDL。文件 assets/schema/dbgpt.sql 包含当前版本的完整 DDL。版本特定的 DDL 变更可以在 assets/schema/upgrade 下找到。例如，如果您从 v0.7.1 升级到 v0.7.4，可以执行以下 DDL：

    ```
    mysql -h127.0.0.1 -uroot -p{your_password} < assets/schema/upgrade/v0_7_4/upgrade_to_v0.7.4.sql
    ```

- 步骤 2：启动 DB-GPT 服务，等待基准数据集自动加载。当您看到日志行时，数据集加载完成（大约需要 1~5 分钟）。

<p align="left">
  <img src={'/img/module/benchmark/env_load.png'} width="1000px"/>
</p>

- 步骤 3：在 DB-GPT 平台上注册 LLM
  - 方法 1：通过配置文件配置。参考：[ProxyModel 配置](http://docs.dbgpt.cn/docs/next/installation/advanced_usage/More_proxyllms)
  - 方法 2：通过产品页面配置。参考：[模型管理](http://docs.dbgpt.cn/docs/next/application/llms)

## 创建评估任务
- 步骤 1：点击"创建基准测试"创建评估任务
- 步骤 2：输入任务名称并选择模型列表
- 步骤 3：提交任务

<p align="left">
  <img src={'/img/module/benchmark/benchmark_create.png'} width="1000px"/>
</p>

- 步骤 4：等待任务完成（评估可能需要较长时间）

<p align="left">
  <img src={'/img/module/benchmark/benchmark_list.png'} width="1000px"/>
</p>

## 查看评估结果
- 当状态为"已完成"时，点击"查看详情"查看评估报告
- 报告显示：
  - 模型总数、问题数量、正确、错误和失败问题的数量
  - 每个轮次和模型：执行、正确、错误和失败问题的数量；可执行率；准确率
  - 可执行率和准确率的柱状图

> 正确：模型正确回答了问题。错误：模型生成的 SQL 语法正确但语义错误。失败：通常是 SQL 语法或语义错误。

<p align="left">
  <img src={'/img/module/benchmark/benchmark_report.png'} width="1000px"/>
</p>

## 下载评估结果
- 点击"下载评估结果"下载详细的 Excel 报告
- Excel 报告包括 LLM 执行详细信息和比较结果（显示在不同的工作表中）

<p align="left">
  <img src={'/img/module/benchmark/excel_info.png'} width="1000px"/>
</p>

## 数据集详情
- 点击"查看数据集详情"查看基准详细信息
  - 显示 Falcon 数据集中的表、字段和样本数据

<p align="left">
  <img src={'/img/module/benchmark/dataset_info.png'} width="1000px"/>
</p>

# Excel 评估结果数据结构

## Excel 评估结果示例

### 执行结果示例

<p align="left">
  <img src={'/img/module/benchmark/benchmark_excel_execute_result.png'} width="1000px"/>
</p>

### 执行结果数据结构
- **工作表名称：dataset_evaluation_result**

| 字段         | 描述         | 示例                                                                                                                               |
|--------------|--------------|------------------------------------------------------------------------------------------------------------------------------------|
| 编号         | 问题序号     | 1, 2...                                                                                                                            |
| 大模型名称   | 被评估模型名称 | DeepSeek-V3.1                                                                                                                      |
| 轮次         | 评估轮次     | 1                                                                                                                                  |
| 数据集 ID    | 问题对应数据集 ID | D2025050900161503000025249569                                                                                                      |
| 用户问题     | 评估问题     | 各性别的平均年龄是多少，并按年龄顺序显示结果？                                                                                        |
| 自定义标签   | 问题来源，SQL 类型 | KAGGLE_DS_1, CTE1                                                                                                                  |
| 知识         | 所需知识上下文 | 暂无                                                                                                                               |
| prompt     | 模型对话提示  | 已知以下数据集，包含了字段名及其采样信息：...                                                                                           |
| Cot 长度     | CoT 消耗的 tokens 数 | 100                                                                                                                                |
| LLM 输出结果  | LLM 生成的 SQL | select gender as `gender`, avg(cast(age as real)) as `average_age` from di_finance_data group by gender order by avg(cast(age as real)) |
| 结果执行     | LLM 生成 SQL 的查询结果 | `{"性别":["Female","Male"],"平均年龄":[27.73,27.84]}`                                                                                    |
| 执行结果的报错信息 | SQL 执行失败时的错误信息 |                                                                                                                                    |
| traceId    | 日志 ID      | 暂无                                                                                                                               |
| 耗时（秒）   | 消耗时间     | 10                                                                                                                                 |

## 比较结果示例

### 比较结果示例

<p align="left">
  <img src={'/img/module/benchmark/benchmark_excel_compare_result.png'} width="1000px"/>
</p>

### 比较结果数据结构
- **工作表名称：benchmark_compare_result**

| 字段             | 描述                                 | 示例                                                                                                                               |
|------------------|--------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| serialNo         | 问题序号                             | 1, 2...                                                                                                                            |
| analysisModelId  | 问题对应的数据集 ID                  | D2025050900161503000025249569                                                                                                      |
| question         | 评估问题                             | 各性别的平均年龄是多少，并按年龄顺序显示结果？                                                                                        |
| selfDefineTags   | 问题来源，SQL 类型                   | KAGGLE_DS_1, CTE1                                                                                                                  |
| prompt           | 模型对话提示                         | 已知以下数据集，包含了字段名及其采样信息：...                                                                                           |
| standardAnswerSql | 问题的正确 SQL（基于阿里云 MaxCompute 语法） | select gender as `gender`, avg(cast(age as real)) as `average_age` from di_finance_data group by gender order by avg(cast(age as real)) |
| standardAnswer   | 在阿里云 MaxCompute 引擎上的正确 SQL 查询结果 | `{"性别": ["Female", "Male"], "平均年龄": ["27.73", "27.84"]}`                                                                          |
| llmCode         | 被评估模型名称                       | DeepSeek-V3.1                                                                                                                      |
| llmOutput       | LLM 生成的 SQL                       | select gender as `gender`, avg(cast(age as real)) as `average_age` from di_finance_data group by gender order by avg(cast(age as real)) |
| executeResult   | LLM 生成 SQL 的查询结果               | `{"性别":["Female","Male"],"平均年龄":[27.73,27.84]}`                                                                                    |
| errorMsg        | 比较错误信息                         |                                                                                                                                    |
| compareResult   | 参考答案与 LLM 输出的比较结果         | RIGHT：正确；WRONG：错误；FAILED：失败（通常是 SQL 有问题）                                                                            |

# 当前支持的评估能力

## 指标
| 指标     | 支持情况 |
|----------|----------|
| 可执行率 | ✅        |
| 准确率   | ✅        |

## 数据集
| 数据集  | 支持情况 |
|---------|----------|
| Falcon  | ✅        |

## 输入/输出格式
| 格式    | 支持情况 |
|---------|----------|
| Excel   | ✅        |
| CSV     | ❌        |
| JSON    | ❌        |
| Yuque   | ❌        |

## 数据库
| 数据库类型 | 支持情况 |
|------------|----------|
| SQLite     | ✅        |
| MySQL      | ❌        |
| ODPS       | ❌        |

# 功能特性
- [x] 支持单轮多模型评估
- [x] 支持 Excel 文件
- [x] 支持 SQLite 数据库
- [ ] 支持多轮评估
- [ ] 支持评估 Agent
- [ ] 支持不同数据源
- [ ] 支持 CSV、JSON、Yuque 和其他文件系统
