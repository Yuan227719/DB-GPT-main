# Hive

在本示例中，我们将展示如何在 DB-GPT 数据源中使用 Hive。使用 Hive 实现数据源可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，你需要安装 `dbgpt hive datasource` 库。

```bash
uv sync --all-packages \
--extra "base" \
--extra "datasource_hive" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 准备 Hive

准备 Hive 数据库服务，参考 [Hive 安装文档](https://cwiki.apache.org/confluence/display/Hive/GettingStarted)。

然后运行以下命令启动 Web 服务器：
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

你也可以使用以下命令启动 Web 服务器：
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### Hive 配置

<p align="left">
  <img src={'https://github.com/user-attachments/assets/40fb83c5-9b12-496f-8249-c331adceb76f'} width="1000px"/>
</p>
