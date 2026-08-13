# 交接文档：2026-08-12 Docker 镜像修复 + 重新部署（sqlglot/mcp/全名查表）

> 项目：DB-GPT monorepo，半导体测试数据分析（st_embed / 商规EMBED），`/v1/chat/react-agent`
> 关联：`HANDOVER_20260812_docker_deploy.md`（首次部署）→ 本会话**排查遗留问题根因 → 修 Dockerfile + 代码 → 重新 build/上传/部署到 10.5.3.67**
> 本会话：定位并修复三大问题（镜像缺 sqlglot、mcp 未 pin、OpenMetadata 全名查表失败）；回到本地待办 Problem A（skill 不自动触发，未实施）

---

## 一、根因排查结论（部署遗留问题）

服务器新镜像 **8.31GB**（含全量 pin 依赖），旧镜像被重命名（dangling）。**部署配置本身无问题**（挂载/重启策略/add-host/tiktoken/模型配置/dbgpt.db 可写，全部正常，容器无崩溃，agent 主链路能跑通）。

| # | 问题 | 根因 | 状态 |
|---|---|---|---|
| 1 | `get_table_info`/`get_lineage` 报"未找到表/血缘" | **镜像缺 `sqlglot`**（`dolphinscheduler_client.py::_parse_task` 里 `from sqlglot import parse_one` 抛 ImportError 被吞 → 所有 SQL 任务跳过 → `_LINEAGE_CACHE` 恒空）。sqlglot 未在 `packages/*/pyproject.toml` 声明，本地靠 pyobvector（`uv sync` 全量 extras）传递带入，Dockerfile 只装部分 extras 所以没有。**包 diff 确认容器只缺这一个包** | ✅ 已修 |
| 2 | 重新 build 会回退 mcp 2.x | `Dockerfile.custom` 用 `uv pip install`（不读 uv.lock），mcp 未 pin → 2.x 破坏 `streamablehttp_client` import | ✅ 已修（pin 1.28.1） |
| 3 | OpenMetadata 带 schema 全名查不到表 | `_get_table_schema_rest` 只按 `t.name == table_name` 精确匹配裸名；MCP 兜底 fqn 用 `{schema}.{table}` 导致全名二次加前缀 `st_embed.st_embed.xxx`，且真实 FQN 是 `p_trino_iceberg.iceberg.st_embed.xxx` → 全名查表 404/空 | ✅ 已修 |
| 4 | `Unknown connector type 'dolphinscheduler'` | `dolphinscheduler` 类型不在 `dbgpt-ext/connector/catalog.json`（只有 8 个 MCP 类型+custom_mcp） | ⚠️ 既有后台噪音（本地也有），DS 血缘走 `_load_dolphinscheduler_config()` 直连 DB 不经 create_connector，不阻塞 |
| 5 | OpenMetadata REST 401 | 08-06 旧问题 | ✅ 当前未复现（本地全天无 401，容器 REST 正常） |

---

## 二、改动文件（未提交 git）

| 文件 | 改动 |
|---|---|
| `docker/Dockerfile.custom` | builder 阶段：`thrift==0.24.0` `thrift-sasl==0.4.3`（原 84 行）；新增 `COPY docker/requirements-pinned.txt` + `uv pip install -r /app/requirements-pinned.txt`（全量 pin） |
| `docker/requirements-pinned.txt` | **新增**：221 个第三方包全部 pin 到"部署容器实际验证可用版本"（从容器 pip freeze 生成 + 补 `sqlglot==30.15.0`）。用户明确要求**不用 uv.lock 版本**，按实际使用的来 |
| `packages/dbgpt-core/src/dbgpt/agent/util/openmetadata_client.py` | ① `_get_table_schema_rest` 表匹配改为：裸名/全名/真实 FQN 后缀都匹配（`q_bare`）；② `get_table_schema` MCP 兜底 fqn 取表名末段拼，避免 `st_embed.st_embed.xxx` 双前缀 |

**依赖版本（已实测）**：sqlglot 30.15.0、mcp 1.28.1、thrift 0.24.0、thrift-sasl 0.4.3、tiktoken 0.13.0、chromadb 0.6.3。

---

## 三、部署执行过程

```bash
# 1. build（本地 WSL，build 输出 /tmp/dbgpt_build.log）
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile.custom -t dbgpt-custom:latest .
# 新镜像 8.31GB / tar 3.3G（md5 dfabe726fdb5d133b7e8202091176124）

# 2. 上传：3.3G 大文件 scp 会卡死（~2G 处停滞），改用分块 500MB 上传
split -b 500M -d -a 2 dbgpt-custom.tar dbgpt-custom.tar.part   # 7 块
# 逐块 scp 到 /tmp/dbgpt_parts/，服务器 cat 拼接 → /tmp/dbgpt-custom.tar
# md5 校验必须一致！scp 大文件易损坏

# 3. 服务器部署
echo '<server_sudo_password>' | sudo -S docker load -i /tmp/dbgpt-custom.tar   # 旧镜像自动改名 dangling
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

**数据持久化**：dbgpt.db 在挂载目录 `/home/hadoop/dbgpt/`（非 /tmp），`docker rm -f` 不丢数据；`/tmp` 被清空/服务器重启均不影响容器运行（`--restart unless-stopped` 自动恢复），`/tmp` 里只有安装包 tar。

---

## 四、部署验证结果

| 验证项 | 结果 |
|---|---|
| 镜像内依赖 | sqlglot 30.15.0 / mcp 1.28.1 / thrift 0.24.0 / tiktoken 0.13.0 ✅ |
| 全名/裸名查表 | `st_embed.dws_indicator_d`→3941字符、`dws_indicator_d`→3932字符，均 OK ✅ |
| DS 血缘 | `dws_indicator_d` found=True（5 上游/29 字段）、`dws_indicator_w`（8 上游/23 字段）✅ |
| 端到端提问 | "FL412E SHCS26074748 各工序良率趋势"→ 完整答案（MT0~MT3 良率表 + 结论 + HTML 报告）✅ |
| 服务器在用 | 日志出现其他用户提问（"昨天接入了多少工单"），多人使用正常 |

**注意**：之前测试时用 `docker run` 在**服务器上**跑的是**旧镜像**（新镜像还没 load），导致误判 mcp import 失败；新镜像在**本地实测**四种写法全通。测试代码要放容器里跑记得挂载脚本（`docker cp` 只进运行中的容器）。

---

## 五、当前运行状态

- **服务器**（10.5.3.67:5670）：新容器 `dbgpt`（id `f9b234930fe6`），health OK，`--restart unless-stopped`
- **本机**：后端 PID 3596544（端口 5670）还跑着**旧代码**——`openmetadata_client.py` 的全名查表修复**需重启才生效**（重启命令见下）
- **代码改动**（未提交）：Dockerfile.custom、openmetadata_client.py、docker/requirements-pinned.txt（新增）

---

## 六、待办 / 清理

### 1. Problem A：skill 不自动触发（未实施）⏳
- 现象：指标类问题（良率/坏块/ECC 等）不触发 indicator-calc，agent 直接 sql_query 探索。
- 拟修复：`agentic_data_api.py:2265` `pre_matched_skill` 处加"强指标词自动预匹配"（参考 `_mentions_excel`:2296），命中直接设 `pre_matched_skill=indicator-calc`；**上传文件时跳过**。关键词清单待用户确认（建议强词：良率/DPPM/FBB/坏块/ECC/温度/电流/burnin/烧录/老化/箱线图/箱型图/测试工单/测试样品/周报/日报/失效；不匹配宽泛词：工单/趋势/月）。详见 `HANDOVER_20260812_indicator_calc.md` 二节。

### 2. 清理项
- 服务器 `/tmp/dbgpt-custom.tar`（3.3G）——镜像已 load 且验证可用，可删可留（用户未定）
- 服务器旧镜像 dangling `<none>`——验证稳定后 `sudo docker image prune -f`
- 本机 `dbgpt-custom.tar`（3.3G）——重装备份，用完可删

---

## 七、如何重启 / 测试

### 重启本地后端（改 Python 后）
```bash
cd /home/taoyuan/projects/DB-GPT-main
pkill -f "dbgpt start webserver"; sleep 3
nohup .venv/bin/dbgpt start webserver --config configs/openai.toml >> /tmp/dbgpt_server.log 2>&1 &
```

### 重新 build + 部署（若再改镜像）
```bash
cd /home/taoyuan/projects/DB-GPT-main
DOCKER_BUILDKIT=1 docker build -f docker/Dockerfile.custom -t dbgpt-custom:latest .
docker save -o dbgpt-custom.tar dbgpt-custom:latest
split -b 500M -d -a 2 dbgpt-custom.tar dbgpt-custom.tar.part   # 大文件必须分块上传！
# 逐块 scp → 服务器 cat 拼接 → md5 校验 → docker load → docker rm -f + docker run（见三节）
```

### 回归测试重点
1. `get_table_info("st_embed.dws_indicator_d")` / `get_lineage` 应返回血缘（不再"未找到表"）
2. `get_table_schema` 带不带 `st_embed.` 前缀都能查（实测四种写法全通）
3. 指标类问题应触发 indicator-calc（Problem A 修复后）
4. 服务器 `http://10.5.3.67:5670` 多人并发（模型 API 是共享瓶颈，建议同时 2-3 个以内）

---

## 八、关键文件索引

| 文件 | 作用 |
|---|---|
| `docker/Dockerfile.custom` | 依赖安装（`uv pip install` 不读 uv.lock）；sqlglot/mcp/thrift/tiktoken 全量 pin |
| `docker/requirements-pinned.txt` | 221 个第三方包固定版本（容器实际验证可用版 + sqlglot） |
| `openmetadata_client.py:423+` | `_get_table_schema_rest` 全名/裸名/FQN 匹配（q_bare） |
| `openmetadata_client.py:408+` | MCP fqn 用表名末段，避免 `st_embed.st_embed.xxx` |
| `dolphinscheduler_client.py:119+` | `_parse_task` 依赖 sqlglot（镜像修复后血缘恢复） |
| `agentic_data_api.py:2265` | `pre_matched_skill`（Problem A 修复点） |
