# DB-GPT 运行指南（本仓库定制版 v0.8.1）

> 面向接手本仓库的人：从零装环境 → 配模型 → 启动服务 → 前端构建，一条龙。
> 开发环境：Linux / WSL2。仓库为 DB-GPT monorepo，7 个 Python 包通过 uv workspace 管理。

---

## 1. 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | >= 3.10（当前 venv 用 3.11） | 用 `uv` 管理 |
| uv | 最新 | 依赖解析/安装 |
| make | 任意 | 编排质量/测试任务 |
| Node.js | 16+ | 前端构建（`web/`） |

### 安装 uv

```bash
# 方式 1：官方安装脚本（推荐，装到 ~/.local/bin，WSL2/Linux 通用）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 安装后确认 ~/.local/bin 在 PATH 中（或重新登录 shell）
export PATH="$HOME/.local/bin:$PATH"
uv --version

# 方式 2：已有 Python 时用 pip 装
pip install uv

# 方式 3：pipx
pipx install uv

# 方式 4：Rust
cargo install uv
```

> Windows（WSL 之外）：`irm https://astral.sh/uv/install.ps1 | iex`

---

## 2. 安装依赖

### 方式 A：`uv pip install -r requirements.txt`（推荐，全量 pin，221 个依赖）

```bash
uv venv .venv                       # 首次创建虚拟环境（或 python -m venv .venv）
source .venv/bin/activate
uv pip install --python .venv/bin/python -r requirements.txt
```

> 这份 pin 清单是从**本地/容器实测可用版本**生成的（`pip freeze` + 补 sqlglot 等），关键包版本：
> `sqlglot==30.15.0`、`mcp==1.28.1`、`thrift==0.24.0`、`tiktoken==0.13.0`、`chromadb==0.6.3`。
> **这是本仓库唯一经过验证、能保证 agent 主链路跑通的依赖集合。**

> 💡 为什么用 `uv pip install` 而不是 `pip install`：`requirements.txt` 全部 `==` 精确锁定，所以
> `uv pip install -r` 是**确定性安装、不会版本漂移**，产物与 pip 一致，只是快得多。
> 与 `uv sync` 完全不同——`uv sync` 走 pyproject/uv.lock 才会拉最新版（见下方方式 B 警告）。

### 方式 B：`uv sync`（上游默认，⚠️ 不推荐）

```bash
uv sync --all-packages --extra "base" --extra "proxy_openai" --extra "rag" --extra "storage_chromadb" --extra "dbgpts"
```

> ⚠️ **兼容性风险（踩过坑，针对 `uv sync` / 不带版本的 `uv pip install`）**：
> - `uv sync` 和 Dockerfile 里**不带版本参数**的 `uv pip install` **不读 `uv.lock`**，依赖版本漂移到最新。
> - **实际事故**：mcp 漂到 2.x → `from mcp.client.streamable_http import streamablehttp_client`（mcp 1.x API）import 失败 → OpenMetadata MCP 兜底崩溃，需离线装回 `mcp==1.28.1`（见 `HANDOVER_20260812_docker_deploy.md`）。
> - sqlglot 未在 `packages/*/pyproject.toml` 声明，`uv sync` 只是靠全量 extras 传递带入，一旦 extras 变化就会缺（见 `HANDOVER_20260812_docker_redeploy.md`）。
> - 因此**本仓库明确不用 uv.lock 版本**，一律以 `requirements.txt` 的 pin 为准。方式 A 的 `uv pip install -r requirements.txt` 不受此影响。

**注意**：本仓库 7 个包（`dbgpt-core` / `dbgpt-serve` / `dbgpt-app` / `dbgpt-ext` / `dbgpt-client` / `dbgpt-sandbox` / `dbgpt-accelerator`）都是 **editable 安装**，直接指向 `packages/` 源码，改代码立即生效，无需重装。

补充依赖清单（`requirements/` 目录）：
- `requirements/dev-requirements.txt` — 开发工具
- `requirements/lint-requirements.txt` — lint 工具

---

## 3. 配置文件

配置目录 `configs/`，每个 `*.toml` 是一个完整配置。**实际使用的是 `configs/openai.toml`**，它含真实 API key，已被 `.gitignore` 忽略，**不要提交到 git**。

### 3.1 关键配置项（以 `configs/openai.toml` 为例）

```toml
[system]
language = "${env:DBGPT_LANG:-en}"
api_keys = []                 # 服务对外访问白名单，空 = 不限制
encrypt_key = "your_secret_key"

# 服务端口
[service.web]
host = "0.0.0.0"
port = 5670                   # ← 默认端口 5670

# 元数据数据库（sqlite 即可）
[service.web.database]
type = "sqlite"
path = "pilot/meta_data/dbgpt.db"

# 向量库
[rag.storage.vector]
type = "chroma"
persist_path = "pilot/data"

# LLM + Embedding
[models]
[[models.llms]]
name = "Deepseek-V4-Flash"            # 模型显示名
provider = "proxy/openai"             # 走 OpenAI 兼容接口
api_base = "https://aicode.longsys.com/v1"   # 网关地址
api_key = "<你的 API key>"

[[models.embeddings]]
name = "qwen3-embedding"
provider = "proxy/openai"
api_url = "https://aicode.longsys.com/v1/embeddings"
api_key = "<你的 API key>"
```

### 3.2 没有真实 key 时的模板

`configs/dbgpt-proxy-openai.toml` 用 `${env:...}` 占位，可从环境变量读取：

```bash
export OPENAI_API_KEY=xxx
export OPENAI_API_BASE=https://aicode.longsys.com/v1
export LLM_MODEL_NAME=Deepseek-V4-Flash
export EMBEDDING_MODEL_NAME=qwen3-embedding
```

### 3.3 其他示例配置

`configs/` 下按模型后端分：`dbgpt-local-*.toml`（本地模型 vllm/ollama/llama.cpp/qwen/glm）、
`dbgpt-proxy-*.toml`（OpenAI/DeepSeek/硅基流动/通义/智谱 等代理）。

---

## 4. 启动服务

```bash
cd /home/taoyuan/projects/DB-GPT-main

# 后台启动（推荐）
nohup .venv/bin/dbgpt start webserver --config configs/openai.toml \
  >> /tmp/dbgpt_server.log 2>&1 &

# 或前台启动（方便看日志）
.venv/bin/dbgpt start webserver --config configs/openai.toml
```

- 启动后访问 **http://localhost:5670**
- 日志：`tail -f /tmp/dbgpt_server.log`
- 首次运行若没找到配置会进入交互式 setup wizard，非交互环境加 `--yes` 跳过

### 停止 / 常用子命令

```bash
.venv/bin/dbgpt stop webserver    # 停止 web 服务
.venv/bin/dbgpt stop all          # 停止所有（webserver/controller/worker/apiserver）

.venv/bin/dbgpt start apiserver   # 仅 API（无 Web UI）
.venv/bin/dbgpt start controller  # 模型控制节点
.venv/bin/dbgpt start worker      # 模型工作节点
```

> 说明：旧版的 `dbgpt-start` 命令已并入 `dbgpt` CLI，启动 web 用 `dbgpt start webserver`。

---

## 5. 前端

后端自带前端静态资源，改动 `web/` 后需重新构建并拷贝到后端目录：

```bash
cd web
npm install
npm run compile          # = next build + next export，产物在 web/out
# 拷贝到后端静态目录
rm -rf ../packages/dbgpt-app/src/dbgpt_app/static/web
cp -r out ../packages/dbgpt-app/src/dbgpt_app/static/web/
```

- 前端开发模式：`cd web && npm run dev`（热更新，NODE_OPTIONS 已配 16GB）
- **常见坑**：`next build` 偶发 OOM 被杀 → 用 `NODE_OPTIONS="--max_old_space_size=8192"` 且预留 ~14GB 内存重试；`.next` 缓存陈旧时先 `rm -rf .next out`。
- `next.config.js` 已设 `ignoreBuildErrors: true`。

---

## 6. 常用质量/测试命令

```bash
make fmt          # 格式化 + 排序 import（ruff）
make fmt-check    # 只检查不修改
make mypy         # 类型检查（仅 dbgpt-core）
make test         # 单元测试（pytest --pyargs dbgpt）
make pre-commit   # fmt-check + test + test-doc + mypy
```

---

## 7. 生产部署（Docker，用 uv 构建镜像）

生产镜像用 **`docker/Dockerfile.custom`**（CPU-only、无 CUDA、走远程 OpenAI 兼容 API），依赖安装走
**`uv pip install`**（不用 `uv sync`：uv.lock 把包 URL pin 到 pythonhosted.org，国内下载极慢；`uv pip install`
尊重 `--index-url` 走清华镜像）。服务器：内网 `10.5.3.67:5670`。

### 7.1 镜像要点

| 项 | 配置 |
|---|---|
| 基础镜像 | `ubuntu:22.04`，Python 3.11 |
| 依赖安装 | `uv pip install`，关键 pin：`chromadb==0.6.3`（1.x 破坏性 API 变更）、`thrift==0.24.0`、`thrift-sasl==0.4.3`、`mcp==1.28.1`（2.x 破坏 `streamablehttp_client`）、`sqlglot==30.15.0`（未声明依赖，必须显式 pin） |
| 全量 pin | `docker/requirements-pinned.txt`（221 个，容器实测可用版本） |
| 时区 | `Asia/Shanghai`（UTC 会破坏对话时间戳） |
| 数据目录 | `/app/pilot/{data,meta_data}` 挂载持久化 |
| CMD | `dbgpt start webserver --config configs/openai.toml` |
| 大小 | 镜像 8.31GB / tar 3.3G |

### 7.2 构建（本地 WSL）

```bash
cd /home/taoyuan/projects/DB-GPT-main
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile.custom -t dbgpt-custom:latest .
# 构建输出建议重定向到日志：... 2>&1 | tee /tmp/dbgpt_build.log
```

### 7.3 上传服务器（大文件必须分块）

```bash
docker save -o dbgpt-custom.tar dbgpt-custom:latest
# tar 3.3G，直接 scp 会在 ~2G 处卡死，用分块 500MB：
split -b 500M -d -a 2 dbgpt-custom.tar dbgpt-custom.tar.part   # 7 块
# 逐块 scp 到服务器 /tmp/dbgpt_parts/，服务器 cat 拼接 → /tmp/dbgpt-custom.tar
# ⚠️ md5 校验必须一致（scp 大文件易损坏）
md5sum dbgpt-custom.tar.part*    # 本地与服务器对比
```

### 7.4 服务器部署（10.5.3.67）

```bash
echo '<sudo密码>' | sudo -S docker load -i /tmp/dbgpt-custom.tar   # 旧镜像自动变 dangling
echo '<sudo密码>' | sudo -S docker rm -f dbgpt

echo '<sudo密码>' | sudo -S docker run -d --name dbgpt -p 5670:5670 \
  --add-host p-szn-bigdata-zk-001:172.16.9.154 \
  --add-host p-szn-bigdata-zk-002:172.16.9.155 \
  --add-host p-szn-bigdata-zk-003:172.16.9.156 \
  -v /home/hadoop/dbgpt/configs:/app/configs \
  -v /home/hadoop/dbgpt/pilot/meta_data:/app/pilot/meta_data \
  -v /home/hadoop/dbgpt/pilot/data:/app/pilot/data \
  -v /home/hadoop/dbgpt/pilot/message:/app/pilot/message \
  -v /home/hadoop/dbgpt/tiktoken_cache:/tmp/data-gym-cache \
  --restart unless-stopped \
  dbgpt-custom:latest
```

> **持久化**：dbgpt.db 等数据在挂载目录 `/home/hadoop/dbgpt/`（不在 /tmp），`docker rm -f` 不丢数据；
> `--restart unless-stopped` 服务器重启自动恢复。
> **add-host** 是 ZK 三节点的 hosts 映射（Kyuubi/DS 血缘直连用），必须带上。

### 7.5 更简单的 compose 方式

`docker-compose.custom.yml` 挂载了 `./configs` 和 `./packages`（改 Python 代码不用重建镜像）：

```bash
# 服务器上：放好 configs/openai.toml 后
docker compose -f docker-compose.custom.yml up -d
docker compose -f docker-compose.custom.yml logs -f webserver
```

### 7.6 部署后回归重点

1. `get_table_info("st_embed.dws_indicator_d")` 血缘应返回（不再"未找到表"）
2. `get_table_schema` 带不带 `st_embed.` 前缀都能查
3. 指标类问题应触发 indicator-calc 技能
4. 服务器多人并发注意：模型 API 是共享瓶颈，建议同时 2-3 个以内

---

## 8. 常见问题

| 现象 | 处理 |
|---|---|
| 模型请求很慢（单次 1–3 分钟） | 多为模型后端（aicode 网关）请求排队，非代码问题 |
| Deepseek 偶发输出 DSML 而非 ReAct | 模型输出格式漂移，agent 第一轮可能直接 terminate |
| 前端改动不生效 | 需 `npm run compile` 并把 `web/out` 拷贝回 `static/web` 再重启 |
| 想换模型 | 改 `configs/openai.toml` 里 `[[models.llms]]`，重启生效 |

---

## 9. 相关文档

- `CLAUDE.md` — 构建/测试命令、架构说明
- `requirements.txt` — 全量 pin 依赖清单
- `HANDOVER_*.md` — 各期问题诊断与修复交接（agent 诊断、指标技能、Docker 部署等）
- `docs/` — Docusaurus 官方文档站点
