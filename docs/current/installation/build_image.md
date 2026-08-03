---
id: docker-build-guide
title: DB-GPT Docker 构建指南
sidebar_label: Docker 构建指南
description: 使用各种配置构建 DB-GPT Docker 镜像的全面指南
keywords:
  - DB-GPT
  - Docker
  - 构建
  - CUDA
  - OpenAI
  - VLLM
  - Llama-cpp
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import CodeBlock from '@theme/CodeBlock';

# DB-GPT Docker 构建指南

本指南提供了使用 `docker/base/build_image.sh` 脚本以各种配置构建 DB-GPT Docker 镜像的全面说明。

## 概述

DB-GPT 构建脚本允许您根据特定需求创建定制的 Docker 镜像。您可以选择预定义的安装模式，或通过指定特定的额外依赖、环境变量和其他设置来自定义构建。

## 可用安装模式

<Tabs>
  <TabItem value="default" label="默认" default>
    基于 CUDA 的镜像，包含标准功能。
    
    ```bash
    bash docker/base/build_image.sh
    ```
    
    包含：CUDA 支持、代理集成（OpenAI、Ollama、Zhipuai、Anthropic、Qianfan、Tongyi）、RAG 能力、Graph RAG、Hugging Face 集成和量化支持。
  </TabItem>
  <TabItem value="openai" label="OpenAI">
    基于 CPU 的镜像，针对 OpenAI API 使用进行了优化。
    
    ```bash
    bash docker/base/build_image.sh --install-mode openai
    ```
    
    包含：基础功能、所有代理集成和 RAG 能力，无需 GPU 加速。
  </TabItem>
  <TabItem value="vllm" label="VLLM">
    基于 CUDA 的镜像，带有 VLLM 用于优化推理。
    
    ```bash
    bash docker/base/build_image.sh --install-mode vllm
    ```
    
    包含：所有默认功能及 VLLM 高性能推理支持。
  </TabItem>
  <TabItem value="llama-cpp" label="Llama-cpp">
    基于 CUDA 的镜像，带有 Llama-cpp 支持。
    
    ```bash
    bash docker/base/build_image.sh --install-mode llama-cpp
    ```
    
    包含：所有默认功能及 Llama-cpp 和 Llama-cpp 服务器，通过 `CMAKE_ARGS="-DGGML_CUDA=ON"` 启用 CUDA 加速。
  </TabItem>
  <TabItem value="full" label="完整">
    基于 CUDA 的镜像，包含所有可用功能。
    
    ```bash
    bash docker/base/build_image.sh --install-mode full
    ```
    
    包含：其他模式的所有功能及嵌入能力。
  </TabItem>
</Tabs>

## 基本用法

### 查看可用模式

查看所有可用的安装模式及其配置：

```bash
bash docker/base/build_image.sh --list-modes
```

### 获取帮助

显示所有可用选项：

```bash
bash docker/base/build_image.sh --help
```

## 自定义选项

### Python 版本

DB-GPT 需要 Python 3.10 或更高版本。默认使用 Python 3.11，但您可以指定不同的版本：

```bash
bash docker/base/build_image.sh --python-version 3.10
```

### 自定义镜像名称

为构建的镜像设置自定义名称：

```bash
bash docker/base/build_image.sh --image-name mycompany/dbgpt
```

### 镜像名称后缀

为镜像名称添加后缀，用于版本标识或环境区分：

```bash
bash docker/base/build_image.sh --image-name-suffix v1.0
```

默认模式下将生成 `eosphorosai/dbgpt-v1.0`，特定模式下将生成 `eosphorosai/dbgpt-MODE-v1.0`。

### PIP 镜像源

选择不同的 PIP 索引地址：

```bash
bash docker/base/build_image.sh --pip-index-url https://pypi.org/simple
```

### Ubuntu 镜像源

控制是否使用清华 Ubuntu 镜像源：

```bash
bash docker/base/build_image.sh --use-tsinghua-ubuntu false
```

### 语言偏好

设置偏好的语言（默认为英语）：

```bash
bash docker/base/build_image.sh --language zh
```

## 高级自定义

### 自定义额外依赖

您可以自定义镜像中安装的 Python 包额外依赖：

<Tabs>
  <TabItem value="override" label="覆盖额外依赖" default>
    完全替换默认的额外依赖为您自己的选择：
    
    ```bash
    bash docker/base/build_image.sh --extras "base,proxy_openai,rag,storage_chromadb"
    ```
  </TabItem>
  <TabItem value="add" label="添加额外依赖">
    保留默认额外依赖并添加更多：
    
    ```bash
    bash docker/base/build_image.sh --add-extras "storage_milvus,storage_elasticsearch,datasource_postgres"
    ```
  </TabItem>
  <TabItem value="mode-specific" label="按模式添加">
    为特定安装模式添加额外依赖：
    
    ```bash
    bash docker/base/build_image.sh --install-mode vllm --add-extras "storage_milvus,datasource_postgres"
    ```
  </TabItem>
</Tabs>

#### 可用额外选项

以下是一些有用的额外依赖：

| 额外包 | 描述 |
|--------------|-------------|
| `storage_milvus` | 与 Milvus 的向量存储集成 |
| `storage_valkey` | 与 Valkey 的向量存储集成 |
| `storage_elasticsearch` | 与 Elasticsearch 的向量存储集成 |
| `datasource_postgres` | PostgreSQL 数据库连接器 |
| `vllm` | VLLM 优化推理集成 |
| `llama_cpp` | Llama-cpp Python 绑定 |
| `llama_cpp_server` | Llama-cpp HTTP 服务器 |

您可以在本地 DB-GPT 仓库中运行 `uv run install_help.py list` 查看所有可用的额外依赖。

### 环境变量

DB-GPT 构建支持通过环境变量进行专门构建。主要使用的环境变量是 `CMAKE_ARGS`，对于 Llama-cpp 编译尤为重要。

<Tabs>
  <TabItem value="override-env" label="覆盖环境变量" default>
    替换默认的环境变量：
    
    ```bash
    bash docker/base/build_image.sh --env-vars "CMAKE_ARGS=\"-DGGML_CUDA=ON -DLLAMA_CUBLAS=ON\""
    ```
  </TabItem>
  <TabItem value="add-env" label="添加环境变量">
    添加额外的环境变量：
    
    ```bash
    bash docker/base/build_image.sh --install-mode llama-cpp --add-env-vars "FORCE_CMAKE=1"
    ```
  </TabItem>
</Tabs>

:::note
对于 Llama-cpp 模式，`CMAKE_ARGS="-DGGML_CUDA=ON"` 会自动设置以启用 CUDA 加速。
:::

### Docker 网络

指定构建时使用的 Docker 网络：

```bash
bash docker/base/build_image.sh --network host
```

### 自定义 Dockerfile

使用自定义 Dockerfile：

```bash
bash docker/base/build_image.sh --dockerfile Dockerfile.custom
```

## 示例场景

### 企业版 DB-GPT 集成 PostgreSQL 和 Elasticsearch

构建集成了 PostgreSQL 和 Elasticsearch 支持的全功能企业版：

```bash
bash docker/base/build_image.sh --install-mode full \
  --add-extras "storage_elasticsearch,datasource_postgres" \
  --image-name-suffix enterprise \
  --python-version 3.10 \
  --load-examples false
```

### 针对特定硬件优化的 Llama-cpp

使用自定义 Llama-cpp 优化标志构建：

```bash
bash docker/base/build_image.sh --install-mode llama-cpp \
  --env-vars "CMAKE_ARGS=\"-DGGML_CUDA=ON -DGGML_AVX2=OFF -DGGML_AVX512=ON\"" \
  --python-version 3.11
```

### 轻量级 OpenAI 代理

构建最小化的 OpenAI 代理镜像：

```bash
bash docker/base/build_image.sh --install-mode openai \
  --use-tsinghua-ubuntu false \
  --pip-index-url https://pypi.org/simple \
  --load-examples false
```

### 集成 Milvus 的开发构建

构建集成 Milvus 支持的开发版本：

```bash
bash docker/base/build_image.sh --install-mode vllm \
  --add-extras "storage_milvus" \
  --image-name-suffix dev
```

## 故障排除

<details>
<summary>常见构建问题</summary>

### CUDA 未找到

如果遇到 CUDA 相关错误：

```bash
# 尝试使用不同的 CUDA 基础镜像
bash docker/base/build_image.sh --base-image nvidia/cuda:12.1.0-devel-ubuntu22.04
```

### 包安装失败

如果额外依赖安装失败：

```bash
# 尝试使用较少的额外依赖以隔离问题
bash docker/base/build_image.sh --extras "base,proxy_openai,rag"
```

### 网络问题

如果遇到网络问题：

```bash
# 使用特定网络
bash docker/base/build_image.sh --network host
```

</details>

## API 参考

### 脚本选项

| 选项 | 描述 | 默认值 |
|--------|-------------|---------------|
| `--install-mode` | 安装模式 | `default` |
| `--base-image` | 基础 Docker 镜像 | `nvidia/cuda:12.4.0-devel-ubuntu22.04` |
| `--image-name` | Docker 镜像名称 | `eosphorosai/dbgpt` |
| `--image-name-suffix` | 镜像名称后缀 | ` ` |
| `--pip-index-url` | PIP 镜像地址 | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| `--language` | 界面语言 | `en` |
| `--load-examples` | 加载示例数据 | `true` |
| `--python-version` | Python 版本 | `3.11` |
| `--use-tsinghua-ubuntu` | 使用清华 Ubuntu 镜像源 | `true` |
| `--extras` | 要安装的额外包 | 取决于模式 |
| `--add-extras` | 额外的附加包 | ` ` |
| `--env-vars` | 构建环境变量 | 取决于模式 |
| `--add-env-vars` | 额外的环境变量 | ` ` |
| `--dockerfile` | 要使用的 Dockerfile | `Dockerfile` |
| `--network` | 要使用的 Docker 网络 | ` ` |

## 其他资源

- [DB-GPT 文档](https://github.com/eosphoros-ai/DB-GPT)
- [Docker 文档](https://docs.docker.com/)
- [CUDA 文档](https://docs.nvidia.com/cuda/)
