---
sidebar_position: 1
title: Docker 部署
---

# Docker 部署

在单个 Docker 容器中运行 DB-GPT——无需 Python 环境配置。

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

## 前置条件

- 已安装并运行 [Docker](https://docs.docker.com/get-docker/)
- GPU 模式需要：[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

## 使用 API 代理部署（无需 GPU）

最快速的入门方式。使用云 LLM 提供者——无需 GPU。

### 第 1 步 — 拉取镜像

```bash
docker pull eosphorosai/dbgpt-openai:latest
```

### 第 2 步 — 运行容器

<Tabs>
  <TabItem value="siliconflow" label="SiliconFlow" default>

```bash
docker run -it --rm \
  -e SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY} \
  -p 5670:5670 \
  --name dbgpt \
  eosphorosai/dbgpt-openai
```

将 `${SILICONFLOW_API_KEY}` 替换为您从 [SiliconFlow](https://cloud.siliconflow.cn/account/ak) 获取的实际密钥。

  </TabItem>
  <TabItem value="openai" label="OpenAI">

```bash
docker run -it --rm \
  -e OPENAI_API_KEY=${OPENAI_API_KEY} \
  -v ./configs/dbgpt-proxy-openai.toml:/app/configs/dbgpt-proxy-openai.toml \
  -p 5670:5670 \
  --name dbgpt \
  eosphorosai/dbgpt-openai \
  dbgpt start webserver --config /app/configs/dbgpt-proxy-openai.toml
```

  </TabItem>
</Tabs>

### 第 3 步 — 打开 Web UI

在浏览器中访问 **[http://localhost:5670](http://localhost:5670)**。

---

## 使用 GPU 部署（本地模型）

在您的 NVIDIA GPU 上本地运行模型。

### 第 1 步 — 下载模型

<Tabs>
  <TabItem value="modelscope" label="ModelScope（中国）" default>

```bash
mkdir -p ./models && cd ./models
git lfs install
git clone https://www.modelscope.cn/Qwen/Qwen2.5-Coder-0.5B-Instruct.git
git clone https://www.modelscope.cn/BAAI/bge-large-zh-v1.5.git
cd ..
```

  </TabItem>
  <TabItem value="huggingface" label="Hugging Face">

```bash
mkdir -p ./models && cd ./models
git lfs install
git clone https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct
git clone https://huggingface.co/BAAI/bge-large-zh-v1.5
cd ..
```

  </TabItem>
</Tabs>

### 第 2 步 — 创建配置文件

创建 `dbgpt-local-gpu.toml`：

```toml
[models]
[[models.llms]]
name = "Qwen2.5-Coder-0.5B-Instruct"
provider = "hf"
path = "/app/models/Qwen2.5-Coder-0.5B-Instruct"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
path = "/app/models/bge-large-zh-v1.5"
```

### 第 3 步 — 运行容器

```bash
docker run --ipc host --gpus all \
  -it --rm \
  -p 5670:5670 \
  -v ./dbgpt-local-gpu.toml:/app/configs/dbgpt-local-gpu.toml \
  -v ./models:/app/models \
  --name dbgpt \
  eosphorosai/dbgpt \
  dbgpt start webserver --config /app/configs/dbgpt-local-gpu.toml
```

| 标志 | 用途 |
|---|---|
| `--ipc host` | 启用主机 IPC 模式以获得更好的性能 |
| `--gpus all` | 允许容器使用所有可用的 GPU |
| `-v ./models:/app/models` | 将本地模型挂载到容器中 |

### 第 4 步 — 打开 Web UI

在浏览器中访问 **[http://localhost:5670](http://localhost:5670)**。

---

## 持久化数据（可选）

默认情况下，容器停止时数据会丢失。要持久化数据：

```bash
mkdir -p ./pilot/data ./pilot/message ./pilot/alembic_versions
```

将这些卷挂载添加到您的 `docker run` 命令中：

```bash
-v ./pilot/data:/app/pilot/data \
-v ./pilot/message:/app/pilot/message \
-v ./pilot/alembic_versions:/app/pilot/meta_data/alembic/versions
```

并在 TOML 文件中配置数据库路径：

```toml
[service.web.database]
type = "sqlite"
path = "/app/pilot/message/dbgpt.db"
```

## 构建您自己的镜像

要从源码构建自定义 Docker 镜像：

```bash
# 代理镜像（无需 GPU）
bash docker/base/build_proxy_image.sh

# 完整镜像（支持 GPU）
bash docker/base/build_image.sh
```

:::info
有关详细的构建选项，请参阅 `bash docker/base/build_image.sh --help`。
:::

## 目录结构

设置完成后，您的工作目录结构如下：

```
.
├── dbgpt-local-gpu.toml    # 您的配置文件
├── models/
│   ├── Qwen2.5-Coder-0.5B-Instruct/
│   └── bge-large-zh-v1.5/
└── pilot/                  # （可选）持久化数据
    ├── data/
    └── message/
```

## 下一步

| 主题 | 链接 |
|---|---|
| Docker Compose（多服务） | [Docker Compose](/docs/getting-started/deploy/docker-compose) |
| 集群部署 | [Cluster](/docs/getting-started/deploy/cluster) |
| 模型提供者 | [Providers](/docs/getting-started/providers/) |
