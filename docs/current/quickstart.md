---
sidebar_position: 0
---
# 快速开始

DB-GPT 支持多种开源和闭源模型的安装和使用。不同模型对环境与资源的要求不同。如果需要本地模型部署，则需要 GPU 资源。API 代理模型所需资源相对较少，可以在 CPU 机器上部署和启动。

:::info 注意
- 详细的安装和部署教程请参见[安装](./installation)。
- 本页面仅介绍基于 ChatGPT 代理和本地 GLM 模型的部署。
:::

## 环境准备

### 下载源代码

:::tip
下载 DB-GPT
:::

```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

### 环境设置

- 默认数据库使用 SQLite，因此在默认启动模式下无需安装数据库。如果您需要使用其他数据库，请参考下面的[高级教程](./application/advanced_tutorial/rag.md)。从 0.7.0 版本开始，DB-GPT 使用 uv 进行环境和包管理，提供更快、更稳定的依赖管理。

:::info 注意
有以下几种方式安装 uv：
:::

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="uv_sh"
  values={[
    {label: '命令（macOS 和 Linux）', value: 'uv_sh'},
    {label: 'PyPI', value: 'uv_pypi'},
    {label: '其他', value: 'uv_other'},
  ]}>
  <TabItem value="uv_sh" label="命令">
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
  </TabItem>

  <TabItem value="uv_pypi" label="PyPI">
使用 pipx 安装 uv。

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade pipx
python -m pipx ensurepath
pipx install uv --global
```
  </TabItem>

  <TabItem value="uv_other" label="其他">

您可以在 [uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/) 中查看更多安装方法。
  </TabItem>

</Tabs>

然后，您可以运行 `uv --version` 来检查 uv 是否安装成功。

```bash
uv --version
```

## 部署 DB-GPT
:::tip
如果您在中国地区，可以在命令末尾添加 --index-url=https://pypi.tuna.tsinghua.edu.cn/simple。如下所示：
```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts" \
--index-url=https://pypi.tuna.tsinghua.edu.cn/simple
```
我们建议您将 pypi 索引配置到环境变量 `UV_INDEX_URL` 中。
示例：
```bash
echo "export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple" >> ~/.bashrc
```

本教程假设您能够与依赖下载源建立网络通信。
:::

### 安装依赖

<Tabs
  defaultValue="openai"
  values={[
    {label: 'OpenAI（代理）', value: 'openai'},
    {label: 'DeepSeek（代理）', value: 'deepseek'},
    {label: 'GLM4（本地）', value: 'glm-4'},
    {label: 'VLLM（本地）', value: 'vllm'},
    {label: 'LLAMA_CPP（本地）', value: 'llama_cpp'},
    {label: 'Ollama（代理）', value: 'ollama'},
  ]}>

  <TabItem value="openai" label="OpenAI（代理）">

```bash
# 使用 uv 安装 OpenAI 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 运行 Web 服务器

要使用 OpenAI 代理运行 DB-GPT，您必须在 `configs/dbgpt-proxy-openai.toml` 配置文件中提供 OpenAI API 密钥，或者通过环境变量 `OPENAI_API_KEY` 提供。

```toml
# 模型配置
[models]
[[models.llms]]
...
api_key = "your-openai-api-key"
[[models.embeddings]]
...
api_key = "your-openai-api-key"
```

然后运行以下命令启动 Web 服务器：

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```
在上述命令中，`--config` 指定了配置文件，`configs/dbgpt-proxy-openai.toml` 是 OpenAI 代理模型的配置文件，您也可以根据需要使用其他配置文件或创建自己的配置文件。

或者，您也可以使用以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

  </TabItem>
<TabItem value="deepseek" label="DeepSeek（代理）">

```bash
# 使用 uv 安装 OpenAI 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 运行 Web 服务器

要使用 DeepSeek 代理运行 DB-GPT，您必须在 `configs/dbgpt-proxy-deepseek.toml` 中提供 DeepSeek API 密钥。

您可以在 `configs/dbgpt-proxy-deepseek.toml` 配置文件中指定嵌入模型，默认嵌入模型是 `BAAI/bge-large-zh-v1.5`。如果您想使用其他嵌入模型，可以修改 `configs/dbgpt-proxy-deepseek.toml` 配置文件，在 `[[models.embeddings]]` 部分指定嵌入模型的 `name` 和 `provider`。provider 可以是 `hf`。最后，您需要在依赖安装命令末尾添加 `--extra "hf"`。以下是更新后的命令：
```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts" \
--extra "hf" \
--extra "cpu"
```

**模型配置**：
```toml
# 模型配置
[models]
[[models.llms]]
# name = "deepseek-chat"
name = "deepseek-reasoner"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"
[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
path = "/data/models/bge-large-zh-v1.5"
```

然后运行以下命令启动 Web 服务器：

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```
在上述命令中，`--config` 指定了配置文件，`configs/dbgpt-proxy-deepseek.toml` 是 DeepSeek 代理模型的配置文件，您也可以根据需要使用其他配置文件或创建自己的配置文件。

或者，您也可以使用以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-deepseek.toml
```

  </TabItem>
  <TabItem value="glm-4" label="GLM4（本地）">

```bash
# 使用 uv 安装 GLM4 所需的依赖
# 安装核心依赖并选择所需的扩展
uv sync --all-packages \
--extra "base" \
--extra "cuda121" \
--extra "hf" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

### 运行 Web 服务器

要使用本地模型运行 DB-GPT。您可以修改 `configs/dbgpt-local-glm.toml` 配置文件来指定模型路径和其他参数。

```toml
# 模型配置
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
```
在上述配置文件中，`[[models.llms]]` 指定了 LLM 模型，`[[models.embeddings]]` 指定了嵌入模型。如果您不提供 `path` 参数，模型将根据 `name` 参数从 Hugging Face 模型仓库下载。

然后运行以下命令启动 Web 服务器：

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-glm.toml
```

  </TabItem>
    <TabItem value="vllm" label="VLLM（本地）">

```bash
# 使用 uv 安装 vllm 所需的依赖
# 安装核心依赖并选择所需的扩展
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "vllm" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

### 运行 Web 服务器

要使用本地模型运行 DB-GPT。您可以修改 `configs/dbgpt-local-vllm.toml` 配置文件来指定模型路径和其他参数。

```toml
# 模型配置
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "vllm"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
```
在上述配置文件中，`[[models.llms]]` 指定了 LLM 模型，`[[models.embeddings]]` 指定了嵌入模型。如果您不提供 `path` 参数，模型将根据 `name` 参数从 Hugging Face 模型仓库下载。

然后运行以下命令启动 Web 服务器：

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-vllm.toml
```

  </TabItem>
  <TabItem value="llama_cpp" label="LLAMA_CPP（本地）">

如果您有 Nvidia GPU，可以通过设置环境变量 `CMAKE_ARGS="-DGGML_CUDA=ON"` 启用 CUDA 支持。

```bash
# 使用 uv 安装 llama-cpp 所需的依赖
# 安装核心依赖并选择所需的扩展
CMAKE_ARGS="-DGGML_CUDA=ON" uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "llama_cpp" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

否则，运行以下命令安装不带 CUDA 支持的依赖。
```bash
# 使用 uv 安装 llama-cpp 所需的依赖
# 安装核心依赖并选择所需的扩展
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "llama_cpp" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

### 运行 Web 服务器

要使用本地模型运行 DB-GPT。您可以修改 `configs/dbgpt-local-llama-cpp.toml` 配置文件来指定模型路径和其他参数。

```toml
# 模型配置
[models]
[[models.llms]]
name = "DeepSeek-R1-Distill-Qwen-1.5B"
provider = "llama.cpp"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型仓库下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
```
在上述配置文件中，`[[models.llms]]` 指定了 LLM 模型，`[[models.embeddings]]` 指定了嵌入模型。如果您不提供 `path` 参数，模型将根据 `name` 参数从 Hugging Face 模型仓库下载。

然后运行以下命令启动 Web 服务器：

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-llama-cpp.toml
```

  </TabItem>
    <TabItem value="ollama" label="Ollama（代理）">

```bash
# 使用 uv 安装 Ollama 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_ollama" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 运行 Web 服务器

要使用 Ollama 代理运行 DB-GPT，您必须在 `configs/dbgpt-proxy-ollama.toml` 配置文件中提供 Ollama API 地址。

```toml
# 模型配置
[models]
[[models.llms]]
...
api_base = "your-ollama-api-base"
[[models.embeddings]]
...
api_base = "your-ollama-api-base"
```

然后运行以下命令启动 Web 服务器：

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-ollama.toml
```
在上述命令中，`--config` 指定了配置文件，`configs/dbgpt-proxy-ollama.toml` 是 Ollama 代理模型的配置文件，您也可以根据需要使用其他配置文件或创建自己的配置文件。

或者，您也可以使用以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-ollama.toml
```

  </TabItem>
</Tabs>

## （可选）更多配置

您可以查看[配置](./config/config-reference)以了解更多配置选项。

例如，如果您想配置 LLM 模型，可以在 [LLM 配置](./config-reference/llm/) 中查看所有可用选项。

再例如，如果您想了解如何配置 vllm 模型，可以在 [VLLM 配置](./config-reference/llm/vllm_adapter_vllmdeploymodelparameters_1d4a24.mdx) 中查看所有可用选项。

## DB-GPT 安装帮助工具

如果您需要安装方面的帮助，可以使用 `uv` 脚本获取帮助。

```bash
uv run install_help.py --help
```

## 生成安装命令

您可以通过交互模式使用 `uv` 脚本生成安装命令。

```bash
uv run install_help.py install-cmd --interactive
```

您也可以生成包含 OpenAI 代理模型所有依赖的安装命令。

```bash
uv run install_help.py install-cmd --all
```

您可以查看所有依赖和扩展。

```bash
uv run install_help.py list
```

## 访问网站

打开浏览器并访问 [`http://localhost:5670`](http://localhost:5670)

### （可选）单独运行 Web 前端

您也可以单独运行 Web 前端：

```bash
cd web && npm install
cp .env.template .env
// 将 API_BASE_URL 设置为您的 DB-GPT 服务器地址，通常为 http://localhost:5670
npm run dev
```
打开浏览器并访问 [`http://localhost:3000`](http://localhost:3000)
