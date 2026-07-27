# 代理 LLM

DB-GPT 可以通过代理 LLM 部署在硬件要求较低的服务器上。DB-GPT 支持许多代理 LLM，例如 OpenAI、Azure、DeepSeek、Ollama 等。

## 安装和配置

安装带有代理 LLM 支持的 DB-GPT 需要使用 `uv` 包管理器，以获得更快更稳定的依赖管理体验。

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'OpenAI', value: 'openai'},
    {label: 'Azure', value: 'azure'},
    {label: 'DeepSeek', value: 'deepseek'},
    {label: 'Ollama', value: 'ollama'},
    {label: 'Qwen', value: 'qwen'},
    {label: 'ChatGLM', value: 'chatglm'},
    {label: '文心', value: 'erniebot'},
  ]}>
  <TabItem value="openai" label="OpenAI">

### 安装依赖

```bash
# 使用 uv 安装 OpenAI 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置 OpenAI

编辑 `configs/dbgpt-proxy-openai.toml` 配置文件，指定您的 OpenAI API key：

```toml
# 模型配置
[models]
[[models.llms]]
name = "gpt-3.5-turbo"
provider = "proxy/openai"
api_key = "your-openai-api-key"
# 可选：要使用 GPT-4，将 name 改为 "gpt-4" 或 "gpt-4-turbo"

[[models.embeddings]]
name = "text-embedding-ada-002"
provider = "proxy/openai"
api_key = "your-openai-api-key"
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

  </TabItem>
  <TabItem value="azure" label="Azure">

### 安装依赖

```bash
# 使用 uv 安装 Azure OpenAI 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置 Azure OpenAI

编辑 `configs/dbgpt-proxy-azure.toml` 配置文件，指定您的 Azure OpenAI 设置：

```toml
# 模型配置
[models]
[[models.llms]]
name = "gpt-35-turbo"  # 或您的部署模型名称
provider = "proxy/openai"
api_base = "https://your-resource-name.openai.azure.com/"
api_key = "your-azure-openai-api-key"
api_version = "2023-05-15"  # 或您的特定 API 版本
api_type = "azure"
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-azure.toml
```

  </TabItem>
  <TabItem value="deepseek" label="DeepSeek">

### 安装依赖

```bash
# 使用 uv 安装 DeepSeek 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置 DeepSeek

编辑 `configs/dbgpt-proxy-deepseek.toml` 配置文件，指定您的 DeepSeek API key：

```toml
# 模型配置
[models]
[[models.llms]]
# name = "deepseek-chat"
name = "deepseek-reasoner"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```

  </TabItem>
  <TabItem value="ollama" label="Ollama">

### 安装依赖

```bash
# 使用 uv 安装 Ollama 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_ollama" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置 Ollama

编辑 `configs/dbgpt-proxy-ollama.toml` 配置文件，指定您的 Ollama API base：

```toml
# 模型配置
[models]
[[models.llms]]
name = "llama3"  # 或 Ollama 实例中可用的任何其他模型
provider = "proxy/ollama"
api_base = "http://localhost:11434" # 您的 Ollama API base 地址

[[models.embeddings]]
name = "nomic-embed-text"  # 或 Ollama 中的任何其他嵌入模型
provider = "proxy/ollama"
api_base = "http://localhost:11434" # 您的 Ollama API base 地址
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-ollama.toml
```

  </TabItem>
  <TabItem value="qwen" label="Qwen（通义）">

### 安装依赖

```bash
# 使用 uv 安装阿里云 Qwen（通义）代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_tongyi" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置 Qwen

创建或编辑配置文件（例如 `configs/dbgpt-proxy-tongyi.toml`）：

```toml
# 模型配置
[models]
[[models.llms]]
name = "qwen-turbo"  # 或 qwen-max、qwen-plus
provider = "proxy/tongyi"
api_key = "your-tongyi-api-key"
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-tongyi.toml
```

  </TabItem>
  <TabItem value="chatglm" label="ChatGLM（智谱）">

### 安装依赖

```bash
# 使用 uv 安装智谱（ChatGLM）代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_zhipuai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置 ChatGLM

创建或编辑配置文件（例如 `configs/dbgpt-proxy-zhipu.toml`）：

```toml
# 模型配置
[models]
[[models.llms]]
name = "glm-4"  # 或其他可用的模型版本
provider = "proxy/zhipu"
api_key = "your-zhipu-api-key"
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-zhipu.toml
```

  </TabItem>
  <TabItem value="erniebot" label="文心（ERNIE）">

### 安装依赖

```bash
# 使用 uv 安装百度文心代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置文心

创建或编辑配置文件（例如 `configs/dbgpt-proxy-wenxin.toml`）：

```toml
# 模型配置
[models]
[[models.llms]]
name = "ERNIE-Bot-4.0"  # 或 ernie-bot、ernie-bot-turbo
provider = "proxy/wenxin"
api_key = "your-wenxin-api-key"
api_secret = "your-wenxin-api-secret"
```

### 运行 Webserver

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-wenxin.toml
```

  </TabItem>
</Tabs>

:::info 注意
如果您在中国地区，可以在 `uv sync` 命令末尾添加 `--index-url=https://pypi.tuna.tsinghua.edu.cn/simple` 以加快包下载速度。
:::

## 访问网站

启动 webserver 后，打开浏览器并访问 [`http://localhost:5670`](http://localhost:5670)
