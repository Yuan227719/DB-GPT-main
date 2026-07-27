# LLM 使用 FAQ

### 问题1: 如何使用 openai chatgpt 服务
修改您的 LLM_MODEL
````shell
LLM_MODEL=proxyllm
````

设置您的 OpenAI API 密钥

````shell
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
````

确保您的 OpenAI API 密钥可用

### 问题2: `python dbgpt_server --light` 和 `python dbgpt_server` 有什么区别

:::tip
python dbgpt_server --light 不会启动 LLM 服务。用户可以通过 `python llmserver` 单独部署 LLM 服务，dbgpt_server 通过设置 .env 中的 LLM_SERVER 环境变量来访问 LLM 服务。目的是允许分别部署 dbgpt 的后端服务和 LLM 服务。

python dbgpt_server 服务和 LLM 服务部署在同一实例上。当 dbgpt_server 启动服务时，它同时也会启动 LLM 服务。
:::

### 问题3: 如何使用多 GPU

DB-GPT 默认会使用所有可用的 GPU。您可以在 .env 文件中修改设置 `CUDA_VISIBLE_DEVICES=0,1` 来使用特定的 GPU ID。

或者，您也可以在启动命令之前指定要使用的 GPU ID，如下所示：

````shell
# 指定 1 个 GPU
CUDA_VISIBLE_DEVICES=0 python3 dbgpt/app/dbgpt_server.py

# 指定 4 个 GPU
CUDA_VISIBLE_DEVICES=3,4,5,6 python3 dbgpt/app/dbgpt_server.py
````

您可以在 .env 文件中修改设置 `MAX_GPU_MEMORY=xxGib` 来配置每个 GPU 的最大内存使用量。

### 问题4: 内存不足

DB-GPT 支持 8 位量化和 4 位量化。

您可以在 .env 文件中修改设置 `QUANTIZE_8bit=True` 或 `QUANTIZE_4bit=True` 来使用量化（默认启用 8 位量化）。

Llama-2-70b 使用 8 位量化可以在 80 GB 显存下运行，使用 4 位量化可以在 48 GB 显存下运行。

注意：您需要根据 [requirements.txt](https://github.com/eosphoros-ai/DB-GPT/blob/main/requirements.txt) 安装最新的依赖。
