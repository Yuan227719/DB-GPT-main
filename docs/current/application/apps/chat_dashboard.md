# Chat Dashboard

报表分析对应 DB-GPT 中的 `Chat Dashboard` 场景，可以通过自然语言进行智能报告生成和分析。它是生成式 BI（GBI）的基础能力之一。让我们来看看如何使用报表分析功能。

## 步骤
以下是使用报表分析的步骤：
- 1.数据准备
- 2.添加数据源
- 3.选择 Chat Dashboard 应用
- 4.开始对话


### 数据准备

为了更好地体验报表分析功能，我们在代码中内置了一些测试数据。要使用这些测试数据，我们首先需要创建一个测试库。
```SQL
CREATE DATABASE IF NOT EXISTS dbgpt_test CHARACTER SET utf8;
```

测试库创建完成后，可以通过脚本一键初始化测试数据。

```python
python docker/examples/dashboard/test_case_mysql_data.py
```

### 添加数据源

添加数据源的步骤与 [Chat Data](./chat_data.md) 相同。在数据源管理标签页中选择对应的数据库类型，然后创建即可。填写必要的信息以完成创建。


### 选择 Chat Dashboard

数据源添加完成后，在首页场景页面选择 `Chat Dashboard` 进行报表分析。

<p align="center">
  <img src={'/img/app/chat_dashboard_v0.6.jpg'} width="800px" />
</p>


### 开始对话
在右侧对话框中输入具体问题，即可开始数据对话。


:::info 提示

⚠️ 数据对话对模型能力要求较高，`ChatGPT/GPT-4` 的成功率较高。其他开源模型可以尝试 `qwen2`
:::

<p align="center">
  <img src={'/img/app/chat_dashboard_display_v0.6.jpg'} width="800px" />
</p>
