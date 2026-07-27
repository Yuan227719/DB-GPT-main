# 财务报表对话

   使用大模型进行财务报表分析正在成为垂直领域的热门应用。大模型不仅能够比人类更准确地理解复杂的财务规则，还能基于专业知识输出合理的分析结果。
   
使用 AWEL 构建财务报表知识构建工作流和财务报表智能问答工作流应用，可以帮助用户：
- 回答财务报表的基本信息问题
- 财务报表指标计算与分析问题
- 财务报表内容分析问题。

#### 财务报表知识构建工作流
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/knowledge_workflow.png'} width="1000px"/>
</p>

#### 财务报表智能机器人工作流
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/financial_robot_chat.png'} width="1000px"/>
</p>

# 如何使用
上传财务报表 PDF 并与财务报表进行对话

场景1：询问财务报表基本信息

<p align="left">
  <img src={'/img/chat_knowledge/fin_report/base_info_chat.jpg'} width="1000px"/>
</p>

场景2：计算财务报表指标
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/chat_indicator.png'} width="1000px"/>
</p>

场景3：分析财务报表
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/report_analyze.png'} width="1000px"/>
</p>


# 如何安装

步骤1：确保您的 dbgpt 版本 >= 0.5.10

步骤2：升级 Python 依赖
```
pip install pdfplumber
pip install fuzzywuzzy
```

步骤3：从 dbgpts 安装财务报表应用
```
# 安装 poetry
pip install poetry

# 安装财务报表知识处理流水线工作流与财务机器人应用工作流
dbgpt app install financial-robot-app financial-report-knowledge-factory

```

步骤4：从 https://www.modelscope.cn/models/AI-ModelScope/bge-large-zh-v1.5 下载预训练 embedding 模型
```
git clone https://www.modelscope.cn/models/AI-ModelScope/bge-large-zh-v1.5
```

```
#*******************************************************************#
#**                     财务报表对话配置                           **#
#*******************************************************************#
FIN_REPORT_MODEL=/app/DB-GPT/models/bge-large-zh-v1.5
```

步骤5：创建知识空间，选择 `FinancialReport` 领域类型
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/financial_space.png'} width="1000px"/>
</p>


步骤6：从 `docker/examples/fin_report` 上传财务报表，如果您想使用财务报表数据集，可以从 modelscope 下载。
```bash
git clone http://www.modelscope.cn/datasets/modelscope/chatglm_llm_fintech_raw_dataset.git
```
步骤7：自动分段，等待片刻

步骤8：与财务报表对话
<p align="left">
  <img src={'/img/chat_knowledge/fin_report/chat.jpg'} width="1000px"/>
</p>
