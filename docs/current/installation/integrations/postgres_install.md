# Postgres

Postgres 是一个功能强大的开源对象关系型数据库系统。它是一个多用户数据库管理系统，具有诸如多版本并发控制（MVCC）、时间点恢复、表空间、异步复制、嵌套事务（保存点）、在线/热备份、高级查询规划器/优化器以及预写式日志（用于容错）等高级功能。

在本示例中，我们将展示如何在 DB-GPT 数据源中使用 Postgres。使用 Postgres 实现数据源可以在一定程度上缓解向量数据库检索带来的不确定性和可解释性问题。

### 安装依赖

首先，你需要安装 `dbgpt postgres datasource` 库。

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_postgres" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 准备 Postgres

准备 Postgres 数据库服务，参考 [Postgres 安装文档](https://www.postgresql.org/download/)。

然后运行以下命令启动 Web 服务器：
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

你也可以使用以下命令启动 Web 服务器：
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### Postgres 配置
<p align="left">
  <img src={'https://github.com/user-attachments/assets/affa5ef2-09d6-404c-951e-1220a0dce235'} width="1000px"/>
</p>
