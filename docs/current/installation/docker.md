import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Docker 部署

## Docker 镜像准备

有两种方式准备 Docker 镜像。
1. 从官方镜像拉取
2. 本地构建，参见 [构建 Docker 镜像](./build_image.md)

在实际使用中，您**任选一种**即可。

## 使用代理模型部署

在此部署方式中，您不需要 GPU 环境。

1. 从官方镜像仓库拉取，[Eosphoros AI Docker Hub](https://hub.docker.com/u/eosphorosai)

```bash
docker pull eosphorosai/dbgpt-openai:latest
```

2. 运行 Docker 容器

此示例要求您为 SiliconFlow API 提供有效的 API key。您可以通过在 [SiliconFlow](https://siliconflow.cn/) 注册并创建 API key 来获取，地址为 [API Key](https://cloud.siliconflow.cn/account/ak)。或者，设置 `AIMLAPI_API_KEY` 以使用 AI/ML API 服务。

```bash
docker run -it --rm -e SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY} \
 -p 5670:5670 --name dbgpt eosphorosai/dbgpt-openai
```
或使用 AI/ML API：
```bash
docker run -it --rm -e AIMLAPI_API_KEY=${AIMLAPI_API_KEY} \
 -p 5670:5670 --name dbgpt eosphorosai/dbgpt-openai
```

请将 `${SILICONFLOW_API_KEY}` 或 `${AIMLAPI_API_KEY}` 替换为您自己的 API key。

然后您可以在浏览器中访问 [http://localhost:5670](http://localhost:5670)。

## 使用 GPU 部署（本地模型）

在此部署方式中，您需要一个 GPU 环境。

在运行 Docker 容器之前，您需要安装 NVIDIA Container Toolkit。更多信息请参考官方文档 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)。

在此部署方式中，您将使用本地模型，而不是从 Hugging Face 或 ModelScope 模型中心下载。如果您已经将模型下载到本地机器，或者想要使用来自不同来源的模型，这将非常有用。

### 步骤 1：下载模型

在运行 Docker 容器之前，您需要将模型下载到本地机器。您可以使用 Hugging Face 或 ModelScope（推荐中国用户使用）来下载模型。

<Tabs>
<TabItem value="modelscope" label="从 ModelScope 下载">

1. 如果您尚未安装 `git` 和 `git-lfs`，请先安装：

   ```bash
   sudo apt-get install git git-lfs
   ```

2. 在当前工作目录中创建一个 `models` 目录：

   ```bash
   mkdir -p ./models
   ```

3. 使用 `git` 将模型仓库克隆到 `models` 目录：

   ```bash
   cd ./models
   git lfs install
   git clone https://www.modelscope.cn/Qwen/Qwen2.5-Coder-0.5B-Instruct.git
   git clone https://www.modelscope.cn/BAAI/bge-large-zh-v1.5.git
   cd ..
   ```

   这会将模型下载到 `./models/Qwen2.5-Coder-0.5B-Instruct` 和 `./models/bge-large-zh-v1.5` 目录中。

</TabItem>
<TabItem value="huggingface" label="从 Hugging Face 下载">

1. 如果您尚未安装 `git` 和 `git-lfs`，请先安装：

   ```bash
   sudo apt-get install git git-lfs
   ```

2. 在当前工作目录中创建一个 `models` 目录：

   ```bash
   mkdir -p ./models
   ```

3. 使用 `git` 将模型仓库克隆到 `models` 目录：

   ```bash
   cd ./models
   git lfs install
   git clone https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct
   git clone https://huggingface.co/BAAI/bge-large-zh-v1.5
   cd ..
   ```

   这会将模型下载到 `./models/Qwen2.5-Coder-0.5B-Instruct` 和 `./models/bge-large-zh-v1.5` 目录中。

</TabItem>
</Tabs>

---

### 步骤 2：准备配置文件

创建一个名为 `dbgpt-local-gpu.toml` 的 `toml` 文件，并添加以下内容：

```toml
[models]
[[models.llms]]
name = "Qwen2.5-Coder-0.5B-Instruct"
provider = "hf"
# 指定本地文件系统中的模型路径
path = "/app/models/Qwen2.5-Coder-0.5B-Instruct"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# 指定本地文件系统中的模型路径
path = "/app/models/bge-large-zh-v1.5"
```

此配置文件指定了 Docker 容器内部模型的本地路径。

---

### 步骤 3：运行 Docker 容器

挂载本地 `models` 目录来运行 Docker 容器：

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

#### 命令说明：
- `--ipc host`：启用主机 IPC 模式以获得更好的性能。
- `--gpus all`：允许容器使用所有可用的 GPU。
- `-v ./dbgpt-local-gpu.toml:/app/configs/dbgpt-local-gpu.toml`：将本地配置文件挂载到容器中。
- `-v ./models:/app/models`：将本地 `models` 目录挂载到容器中。
- `eosphorosai/dbgpt`：使用的 Docker 镜像。
- `dbgpt start webserver --config /app/configs/dbgpt-local-gpu.toml`：使用指定的配置文件启动 webserver。

---

### 步骤 4：访问应用

容器运行后，您可以在浏览器中访问 [http://localhost:5670](http://localhost:5670) 来使用应用。

---

### 步骤 5：持久化数据（可选）

为了确保在容器停止或移除时数据不会丢失，您可以将 `pilot/data` 和 `pilot/message` 目录映射到本地机器。这些目录存储了应用数据和消息。

1. 创建本地目录用于数据持久化：

   ```bash
   mkdir -p ./pilot/data
   mkdir -p ./pilot/message
   mkdir -p ./pilot/alembic_versions
   ```

2. 修改 `dbgpt-local-gpu.toml` 配置文件，指向正确的路径：

   ```toml
   [service.web.database]
   type = "sqlite"
   path = "/app/pilot/message/dbgpt.db"
   ```

3. 使用额外的卷挂载来运行 Docker 容器：

   ```bash
   docker run --ipc host --gpus all \
     -it --rm \
     -p 5670:5670 \
     -v ./dbgpt-local-gpu.toml:/app/configs/dbgpt-local-gpu.toml \
     -v ./models:/app/models \
     -v ./pilot/data:/app/pilot/data \
     -v ./pilot/message:/app/pilot/message \
     -v ./pilot/alembic_versions:/app/pilot/meta_data/alembic/versions \
     --name dbgpt \
     eosphorosai/dbgpt \
     dbgpt start webserver --config /app/configs/dbgpt-local-gpu.toml
   ```

   这可以确保 `pilot/data` 和 `pilot/message` 目录持久化在您的本地机器上。

---

### 目录结构总结

完成上述步骤后，您的目录结构应如下所示：

```
.
├── dbgpt-local-gpu.toml
├── models
│   ├── Qwen2.5-Coder-0.5B-Instruct
│   └── bge-large-zh-v1.5
├── pilot
│   ├── data
│   └── message
```

此设置确保模型和应用数据存储在本地并挂载到 Docker 容器中，使您能够使用它们而不会丢失数据。
