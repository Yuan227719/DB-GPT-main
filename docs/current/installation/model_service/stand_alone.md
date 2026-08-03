# 单机部署

## 准备
```bash
# 下载源码
git clone https://github.com/eosphoros-ai/DB-GPT.git

cd DB-GPT
```

## 环境安装

```bash
# 创建虚拟环境
conda create -n dbgpt_env python=3.10

# 激活虚拟环境
conda activate dbgpt_env
```

## 安装依赖

```bash
pip install -e ".[default]"
```

## 模型下载

下载 LLM 和嵌入模型

:::info 注意

如果没有 GPU 资源，建议使用代理模型，例如 OpenAI、Qwen、ERNIE Bot 等。
:::

```bash
mkdir models && cd models

# 下载嵌入模型，例如：text2vec-large-chinese
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

:::tip

设置代理 API 并修改 `.env` 配置
:::

```bash
# 设置 LLM_MODEL 类型
LLM_MODEL=proxyllm
# 设置您的代理 API key 和代理服务器 URL
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
```

:::info 注意
如果有 GPU 资源，您可以使用本地模型进行部署
:::

```bash
mkdir models && cd models

# 下载嵌入模型，例如：glm-4-9b-chat
git clone https://huggingface.co/THUDM/glm-4-9b-chat

# 下载嵌入模型，例如：text2vec-large-chinese
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese

popd

```

## 命令行启动

```bash
LLM_MODEL=glm-4-9b-chat 
dbgpt start webserver --port 6006
```
默认情况下，`dbgpt start webserver` 命令将在一个 Python 进程中启动 `webserver`、`model controller` 和 `model worker`。在上述命令中，指定了端口 `6006`。

## 查看和验证模型服务

:::tip
查看并显示所有模型服务
:::
```bash
dbgpt model list 
```

```bash
# 结果
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|    Model Name   | Model Type |    Host    | Port | Healthy | Enabled | Prompt Template |       Last Heartbeat       |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
| glm-4-9b-chat |    llm     | 172.17.0.9 | 6006 |   True  |   True  |                 | 2023-10-16T19:49:59.201313 |
|  WorkerManager  |  service   | 172.17.0.9 | 6006 |   True  |   True  |                 | 2023-10-16T19:49:59.246756 |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+

```
其中 `WorkerManager` 是 `Model Workers` 的管理进程

:::tip
检查并验证模型服务
:::
```bash
dbgpt model chat --model_name glm-4-9b-chat
```

上述命令将启动一个交互页面，允许您通过终端与模型进行对话。

```bash
Chatbot started with model glm-4-9b-chat. Type 'exit' to leave the chat.


You: Hello
Bot: Hello! How can I assist you today?

You: 
```
