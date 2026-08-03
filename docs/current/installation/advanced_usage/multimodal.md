# DB-GPT 中的多模态支持

DB-GPT 支持多模态能力，允许您处理各种数据类型，如文本、图像和音频。本指南将帮助您设置和使用 DB-GPT 中的多模态功能。

本指南包括运行本地模型和代理模型。

## 运行本地模型

在本节中，我们将以 [Kimi-VL-A3B-Thinking](https://huggingface.co/moonshotai/Kimi-VL-A3B-Thinking)
模型为例，演示如何运行本地多模态模型。

### 步骤 1：安装依赖

确保已安装所需的依赖。您可以通过运行以下命令来安装：

```bash
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts" \
--extra "model_vl" \
--extra "hf_kimi"
```

### 步骤 2：修改配置文件

安装依赖后，您可以修改配置文件以使用 `Kimi-VL-A3B-Thinking` 模型。

您可以创建新的配置文件或修改现有文件。以下是一个示例配置文件：

```toml
# 模型配置
[models]
[[models.llms]]
name = "moonshotai/Kimi-VL-A3B-Thinking"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
```

### 步骤 3：运行模型

您可以使用以下命令运行模型：

```bash
uv run dbgpt start webserver --config {your_config_file}
```

### 步骤 4：在 DB-GPT 中使用模型

目前，DB-GPT 仅支持图像输入，并且仅支持 `Chat Normal` 场景。

您可以点击聊天窗口中的 `+` 按钮上传图像。然后在输入框中输入您的问题并按下回车。模型将处理图像并根据图像内容提供响应。

<p align="left">
  <img src={'/img/installation/advanced_usage/dbgpt-multimodal-local.jpg'} width="720px"/>
</p>

## 运行代理模型

在本节中，我们将以托管在 [SiliconFlow](https://siliconflow.cn/) 上的 [Qwen/Qwen2.5-VL-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-32B-Instruct) 为例，演示如何运行代理多模态模型。

### 步骤 1：安装依赖

确保已安装所需的依赖。您可以通过运行以下命令来安装：

```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts" \
--extra "model_vl" \
--extra "file_s3"
```

现在，大多数代理模型无法接收原始图像数据，因此您需要将图像上传到存储服务（如 S3、MinIO、阿里云 OSS 等），然后为图像生成一个公共 URL。由于许多存储服务提供兼容 S3 的 API，您可以使用 `file_s3` 额外依赖将图像上传到您的存储服务。

### 步骤 2：修改配置文件

安装依赖后，您可以修改配置文件以使用 `Qwen/Qwen2.5-VL-32B-Instruct` 模型。
您可以创建新的配置文件或修改现有文件。以下是一个示例配置文件：

```toml
# 模型配置
[[models.llms]]
name = "Qwen/Qwen2.5-VL-32B-Instruct"
provider = "proxy/siliconflow"
api_key = "${env:SILICONFLOW_API_KEY}"


[[serves]]
type = "file"
# 文件服务器的默认后端
default_backend = "s3"

[[serves.backends]]
# 使用腾讯云 COS 兼容 S3 的 API 作为文件服务器
type = "s3"
endpoint = "https://cos.ap-beijing.myqcloud.com"
region = "ap-beijing"
access_key_id = "${env:COS_SECRETID}"
access_key_secret = "${env:COS_SECRETKEY}"
fixed_bucket = "{your_bucket_name}"
```

或者，您可以使用阿里云 OSS 存储服务作为文件服务器（您需要先安装依赖 `--extra "file_oss"`）。

```toml
[[serves]]
type = "file"
# 文件服务器的默认后端
default_backend = "oss"

[[serves.backends]]
type = "oss"
endpoint = "https://oss-cn-beijing.aliyuncs.com"
region = "oss-cn-beijing"
access_key_id = "${env:OSS_ACCESS_KEY_ID}"
access_key_secret = "${env:OSS_ACCESS_KEY_SECRET}"
fixed_bucket = "{your_bucket_name}"
```

### 步骤 3：运行模型
您可以使用以下命令运行模型：

```bash
uv run dbgpt start webserver --config {your_config_file}
```

### 步骤 4：在 DB-GPT 中使用模型

<p align="left">
  <img src={'/img/installation/advanced_usage/dbgpt-multimodal-proxy.jpg'} width="720px"/>
</p>
