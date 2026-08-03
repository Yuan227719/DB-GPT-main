# 源码部署

## 环境要求

| 启动模式         | CPU * 内存    |       GPU      |         备注  |
|:--------------------:|:------------:|:--------------:|:---------------:|
|     代理模型          |    4C * 8G      |        无    |  代理模型不依赖 GPU                         |
|     本地模型          |    8C * 32G     |       24G      |  本地启动最好使用 24G 及以上显存的 GPU   |

## 环境准备

### 下载源码

:::tip
下载 DB-GPT
:::

```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

:::info 注意
有几种安装 uv 的方式：
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

  <TabItem value="uv_pypi" label="Pypi">
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

### 安装依赖

<Tabs
  defaultValue="openai"
  values={[
    {label: 'OpenAI（代理）', value: 'openai'},
    {label: 'DeepSeek（代理）', value: 'deepseek'},
    {label: 'GLM4（本地）', value: 'glm-4'},
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

### 运行 Webserver

要使用 OpenAI 代理运行 DB-GPT，您必须在 `configs/dbgpt-proxy-openai.toml` 配置文件中提供 OpenAI API key，或在环境变量中通过 `OPENAI_API_KEY` 提供。

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

然后运行以下命令启动 webserver：

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```
在上述命令中，`--config` 指定了配置文件，`configs/dbgpt-proxy-openai.toml` 是 OpenAI 代理模型的配置文件，您也可以根据需要使用其他配置文件或创建自己的配置文件。

另外，您也可以使用以下命令启动 webserver：
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

### 运行 Webserver

要使用 DeepSeek 代理运行 DB-GPT，您必须在 `configs/dbgpt-proxy-deepseek.toml` 中提供 DeepSeek API key。

您可以在 `configs/dbgpt-proxy-deepseek.toml` 配置文件中指定嵌入模型，默认的嵌入模型是 `BAAI/bge-large-zh-v1.5`。如果您想使用其他嵌入模型，可以修改 `configs/dbgpt-proxy-deepseek.toml` 配置文件，在 `[[models.embeddings]]` 部分指定嵌入模型的 `name` 和 `provider`。provider 可以是 `hf`。

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
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
path = "/data/models/bge-large-zh-v1.5"
```

然后运行以下命令启动 webserver：

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```
在上述命令中，`--config` 指定了配置文件，`configs/dbgpt-proxy-deepseek.toml` 是 DeepSeek 代理模型的配置文件，您也可以根据需要使用其他配置文件或创建自己的配置文件。

另外，您也可以使用以下命令启动 webserver：
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

### 运行 Webserver

要使用本地模型运行 DB-GPT，您可以修改 `configs/dbgpt-local-glm.toml` 配置文件来指定模型路径和其他参数。

```toml
# 模型配置
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
```
在上述配置文件中，`[[models.llms]]` 指定了 LLM 模型，`[[models.embeddings]]` 指定了嵌入模型。如果您未提供 `path` 参数，模型将根据 `name` 参数从 Hugging Face 模型中心下载。

然后运行以下命令启动 webserver：

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-glm.toml
```

  </TabItem>
</Tabs>

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

## 安装 DB-GPT 应用数据库
<Tabs
  defaultValue="sqlite"
  values={[
    {label: 'SQLite', value: 'sqlite'},
    {label: 'MySQL', value: 'mysql'},
  ]}>
<TabItem value="sqlite" label="sqlite">

:::tip 注意

您无需在 SQLite 中单独创建与 DB-GPT 应用相关的数据库表；
默认情况下，它们会自动为您创建。

:::

修改您的 toml 配置文件，使用 SQLite 作为数据库（默认设置）。
```toml
[service.web.database]
type = "sqlite"
path = "pilot/meta_data/dbgpt.db"
```

 </TabItem>
<TabItem value="mysql" label="MySQL">

:::warning 注意

从 0.4.7 版本开始，出于安全考虑，我们移除了 MySQL 数据库 Schema 的自动生成。

:::

1. 首先，执行 MySQL 脚本来创建数据库和表。

```bash
$ mysql -h127.0.0.1 -uroot -p{your_password} < ./assets/schema/dbgpt.sql
```

2. 其次，修改您的 toml 配置文件，使用 MySQL 作为数据库。

```toml
[service.web.database]
type = "mysql"
host = "127.0.0.1"
port = 3306
user = "root"
database = "dbgpt"
password = "aa123456"
```
请将 `host`、`port`、`user`、`database` 和 `password` 替换为您自己的 MySQL 数据库设置。

 </TabItem>
</Tabs>

## 测试数据（可选）
DB-GPT 项目默认内置了一部分测试数据，可以通过以下命令加载到本地数据库中进行测试
- **Linux**

```bash
bash ./scripts/examples/load_examples.sh

```
- **Windows**

```bash
.\scripts\examples\load_examples.bat
```

:::

## 访问网站
打开浏览器并访问 [`http://localhost:5670`](http://localhost:5670)
