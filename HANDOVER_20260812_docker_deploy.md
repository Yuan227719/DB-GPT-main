# 交接文档：2026-08-12 Docker 镜像构建 + 服务器部署（bigdata001）

> 项目：DB-GPT monorepo，半导体测试数据分析（st_embed / 商规EMBED），`/v1/chat/react-agent`
> 关联：`HANDOVER_20260812_indicator_calc.md`（前端守卫/连接器固定/Problem A 待修）
> 本会话：**把 DB-GPT 打包成 Docker 镜像并部署到内网服务器 10.5.3.67，供多人使用**。镜像干净（代码+依赖+tzdata），数据挂载式。

---

## 一、部署概况

| 项 | 值 |
|---|---|
| 服务器 | `10.5.3.67`（bigdata001，CentOS，Docker 26.1.4） |
| 容器 | `dbgpt`，端口 **5670**，`--restart unless-stopped` |
| 镜像 | `dbgpt-custom:latest`（本地 + 服务器已 load） |
| 数据目录 | `/home/hadoop/dbgpt/`（configs + pilot/meta_data + pilot/data + pilot/message + tiktoken_cache） |
| 访问 | `http://10.5.3.67:5670` |
| 登录 | ssh `hadoop@10.5.3.67`（密码 `<server_sudo_password>`），docker 需 `sudo`（hadoop 不在 docker 组） |

**数据是挂载的，不是烧进镜像**（用户最终选择挂载式）：
- 挂载了用户本机拷贝的数据（历史对话 183 条、数据源配置、向量库）
- 镜像 = 干净代码 + 依赖 + tzdata + thrift_sasl + pool_pre_ping + mcp 1.28.1

---

## 二、镜像包含的修复（重要！每项都有血泪教训）

### 1. 时区：Dockerfile 加 tzdata + Asia/Shanghai
- **问题**：镜像 runtime 阶段没装 tzdata → 容器默认 UTC → 对话 `gmt_created` 存 UTC，前端显示"9小时前"错乱（本机 +8 无此问题）。
- **修复**：`Dockerfile.custom` runtime 阶段 `apt install tzdata` + `ENV TZ=Asia/Shanghai` + `ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime`。
- DB-GPT 写时间戳用 `datetime.now()`（`chat_history_db.py:53`），容器本地时区 = +8 后即正确。

### 2. thrift_sasl：Kyuubi 连接必需（Dockerfile + 手动装）
- **问题**：pyhive 连 Kyuubi 需要 `thrift_sasl`，镜像没装 → `st_embed` 加载失败 `No module named 'thrift_sasl'`。
- **修复**：`Dockerfile.custom` builder 阶段 `uv pip install ... "thrift-sasl"`（已加）。本会话用 `pip install thrift-sasl`（0.4.3，纯 wheel）+ commit 快速修复。
- 注意：`Dockerfile.custom` 用 `uv pip install`（**不读 uv.lock**），依赖版本会漂移到最新——见 mcp 教训。

### 3. Kyuubi 关闭连接 ConnectionResetError（pool_pre_ping）
- **问题**：`pool_recycle=300` 定期回收 Kyuubi 连接，关闭时若服务端已断 → `ConnectionResetError`（无害噪音，本机日志级别不同所以不明显）。
- **修复**：`conn_kyuubi.py:675` 加 `engine_args.setdefault("pool_pre_ping", True)`（取连接前 ping，静默丢弃死连接）。
- **已实测**：日志出现 `SELECT 1`（pre_ping 生效）。

### 4. ZK DNS 解析（--add-host）⚠️ 部署必须
- **问题**：容器内 DNS（Docker 默认）解析不了内网主机名 `p-szn-bigdata-zk-001` → Kyuubi ZK discovery 失败 → st_embed 连不上。
- **修复**：`docker run` 加 `--add-host p-szn-bigdata-zk-001:172.16.9.154 --add-host p-szn-bigdata-zk-002:172.16.9.155 --add-host p-szn-bigdata-zk-003:172.16.9.156`（IP 从宿主机 `/etc/hosts` 抄的）。
- 宿主机 `/etc/hosts` 有全套内网主机名映射，**容器不继承**，需手动 --add-host。

### 5. tiktoken tokenizer 离线缓存 ⚠️ 服务器必须
- **问题**：tiktoken 首次用 `cl100k_base` 要联网下载 `openaipublic.blob.core.windows.net`，**服务器访问不了外网** → agent 报错。
- **修复**：从本机下载 `cl100k_base.tiktoken`（1.7M），按 tiktoken 缓存路径放服务器并挂载：
  - 路径：`{cache_dir}/{sha1(url)}`，`cache_key = sha1("https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken")` = `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`
  - 文件放 `/home/hadoop/dbgpt/tiktoken_cache/9b5ad71b2ce5302211f9c61530b329a4922fc6a4`（**无扩展名**，文件名就是 cache_key）
  - 容器 `-v /home/hadoop/dbgpt/tiktoken_cache:/tmp/data-gym-cache`（tiktoken 默认缓存目录）
  - ⚠️ 教训：tiktoken 缓存文件名是 `cache_key`（不带 .tiktoken），不是 `{cache_key}/cl100k_base.tiktoken`。

### 6. mcp 版本降级 2.0.0 → 1.28.1 ⚠️ get_table_info 必需
- **问题**：镜像 mcp=2.0.0（uv pip install 取最新），代码用 `from mcp.client.streamable_http import streamablehttp_client`（mcp 1.x API）→ import 失败 → `get_table_info` 的 OpenMetadata MCP 兜底崩溃。
- **修复**：从本机下载 `mcp==1.28.1` wheel + 依赖（清华镜像），传服务器容器**离线安装**（`pip install --no-index --find-links=/tmp/mcp_wheels "mcp==1.28.1"`）。
- **已实测**：`streamablehttp_client import OK`。
- ⚠️ 教训：`Dockerfile.custom` 用 `uv pip install` 不锁版本，mcp 漂到 2.x。**应在 Dockerfile 里 pin `mcp<2`**（本会话没 pin，只离线改了运行中的容器，**重新 build 镜像会回到 2.x**）。

---

## 三、部署命令（完整）

### 构建镜像（本机 WSL）
```bash
cd /home/taoyuan/projects/DB-GPT-main
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile.custom -t dbgpt-custom:latest .
docker save -o dbgpt-custom.tar dbgpt-custom:latest
```

### 传服务器
```bash
sshpass -p '<server_sudo_password>' scp -o ServerAliveInterval=30 dbgpt-custom.tar hadoop@10.5.3.67:/tmp/
# 校验 md5！scp 2G 易中断导致 tar 损坏（docker load 报 invalid tar header）
# 本地: md5sum dbgpt-custom.tar；服务器: md5sum /tmp/dbgpt-custom.tar 必须一致
```

### 服务器部署
```bash
ssh hadoop@10.5.3.67   # 密码 <server_sudo_password>
echo '<server_sudo_password>' | sudo -S docker load -i /tmp/dbgpt-custom.tar
echo '<server_sudo_password>' | sudo -S docker rm -f dbgpt
echo '<server_sudo_password>' | sudo -S docker run -d --name dbgpt -p 5670:5670 \
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

### 看日志
```bash
ssh hadoop@10.5.3.67
echo '<server_sudo_password>' | sudo -S docker logs -f dbgpt
```

---

## 四、数据目录（服务器 `/home/hadoop/dbgpt/`）

| 目录 | 内容 | 来源 |
|---|---|---|
| `configs/` | openai.toml（LLM 配置，含 API key） | 本机拷贝 |
| `pilot/meta_data/` | `dbgpt.db`（231M，数据源配置+历史对话） | 本机拷贝 |
| `pilot/data/` | chromadb 向量库（294M） | 本机拷贝 |
| `pilot/message/` | 消息附件 | 本机拷贝 |
| `tiktoken_cache/` | cl100k_base.tiktoken（cache_key 命名） | 本机下载 |

⚠️ 注意：挂载数据后，**服务器上新增的对话写在容器可写层**（不是挂载目录的 dbgpt.db），`docker rm` 会丢。若要持久化，应挂载 meta_data 时用能写的方式（当前 bind mount 的是本机拷贝的只读文件，SQLite 写会改文件——实际上 writable，但容器 rm 后挂载文件仍在）。

---

## 五、已知问题 / 待办

### 1. OpenMetadata REST tables API 401（未彻底解决）⚠️
- `get_table_schema` 的 REST 优先路径：`GET /api/v1/tables` 返回 **401**（`_build_headers` 的 bearer token 对 tables API 无效或权限不足），回退 MCP。
- `get_glossary_term` 走 `/api/v1/glossaries` 成功（认证 OK）——所以**术语能查、表结构不能**。
- **当前状态**：mcp 降到 1.28.1 后 MCP 兜底可用，get_table_info 应能通过 MCP 拿到表结构（**未最终验证**）。
- **待办**：① 前端实测 get_table_info 是否恢复；② 若 REST 401 仍挡路，查 OpenMetadata token 权限/token 有效期。

### 2. 镜像需要手动修 mcp（重新 build 会回退 2.x）⚠️
- 当前服务器容器是离线装了 mcp 1.28.1 修复的。**Dockerfile 没 pin mcp**，重新 build 镜像会装回 2.0.0，get_table_info 又挂。
- **待办**：`Dockerfile.custom` builder 阶段加 `"mcp<2"` 或 `mcp==1.28.1`，下次 build 一次到位。

### 3. 服务器访问不了外网
- 清华 PyPI（pypi.tuna）也不通 → 容器内装包必须**离线 wheel**（本机下载 + scp + docker cp + `--no-index --find-links`）。
- tiktoken 同理（cl100k tokenizer 要离线放缓存）。

### 4. docker 需要 sudo
- `hadoop` 不在 docker 组，所有 docker 命令要 `echo '<server_sudo_password>' | sudo -S docker ...`。
- 可选：`sudo usermod -aG docker hadoop`（需重新登录生效）。

### 5. 服务器网络：无线 AP 隔离（用户本机）
- 用户本机（WSL）不能直接让同事访问（AP 隔离），所以才走"部署到服务器"方案。服务器在有线内网，无此问题。

### 6. ConnectionResetError（Kyuubi 关闭）
- 已加 `pool_pre_ping`，日志噪音应减少。不影响功能。

---

## 六、本会话改了哪些文件（未提交 git）

| 文件 | 改动 |
|---|---|
| `docker/Dockerfile.custom` | +tzdata、+`thrift-sasl`、+`TZ=Asia/Shanghai`（mcp pin 待加） |
| `packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_kyuubi.py:675` | +`pool_pre_ping=True` |
| 服务器容器（commit 未入库） | mcp 1.28.1、thrift_sasl、tzdata（离线装 + docker commit 前已 commit 到镜像） |

本地镜像 `dbgpt-custom:latest` 已含：tzdata + thrift_sasl + pool_pre_ping + mcp 1.28.1（通过多次 commit 累积，**非** Dockerfile 全量 build 的产物，但 Dockerfile 已同步关键改动）。

---

## 七、给新会话的下一步建议

1. **验证 get_table_info 恢复**：在 `http://10.5.3.67:5670` 前端问"FL412E 项目 SHCS26074748 工单的各工序良率趋势如何？"，确认 get_table_info 不再报"未找到表"、sql_query 能执行（前端绑定 st_embed 后应带 database_name）。
2. **Dockerfile 加 mcp pin**：`uv pip install ... "mcp==1.28.1"`，避免重新 build 回退 2.x。
3. **OpenMetadata REST 401**：若 get_table_info 仍失败，查 tables API 的 bearer token 权限。
4. **服务器数据持久化**：确认挂载的 dbgpt.db 可写、容器 rm 后数据不丢；考虑用 volume 而非 bind mount 只读文件。
5. **既有待办**：Problem A（skill 不自动触发，见 `HANDOVER_20260812_indicator_calc.md`）；方案 7 经验闭环（暂缓）；burnin 未完成样品。
