# 计划：新增 Kyuubi 数据源支持

## 背景

用户通过 Kyuubi 代理访问 Trino 和 Spark 引擎的数据，Kyuubi 对外暴露 HiveServer2 协议。
引擎选择在 Kyuubi 服务端配置，客户端无需区分底层引擎。

## 技术分析

```
DB-GPT  ──(HiveServer2 / pyhive)──>  Kyuubi Server  ──┬──> Spark Engine
                                                      └──> Trino Engine
```

- Kyuubi 暴露 HiveServer2 协议（Thrift），与 Hive 完全兼容
- Python 端使用已有的 `pyhive`（`hive://` dialect），无需新依赖
- 不需要 `trino[sqlalchemy]` 包

## 改动清单（共 4 处）

### 1. 后端：DBType 枚举 (`schema.py`)

**文件**: `packages/dbgpt-ext/src/dbgpt_ext/datasource/schema.py`

新增一个枚举值：

```python
Kyuubi = DbInfo("kyuubi")
```

### 2. 后端：Kyuubi Connector (`conn_kyuubi.py`) — 新建文件

**文件**: `packages/dbgpt-ext/src/dbgpt_ext/datasource/rdbms/conn_kyuubi.py`

完全复用 `HiveConnector`（`conn_hive.py`），新建薄封装：

- `KyuubiParameters`：继承 `HiveParameters`，`__type__ = "kyuubi"`，默认 port=10009
- `KyuubiConnector`：继承 `HiveConnector`，`db_type = "kyuubi"`，`driver = "hive"`（同一个 pyhive dialect）

### 3. 后端：注册到 ConnectorManager (`connector_manager.py`)

**文件**: `packages/dbgpt-serve/src/dbgpt_serve/datasource/manages/connector_manager.py`

在 `on_init()` 中新增一行 import：

```python
from dbgpt_ext.datasource.rdbms.conn_kyuubi import KyuubiConnector  # noqa: F401
```

### 4. 前端：类型 + 映射 (`db.ts` + `constants.ts`)

**文件**: `web/types/db.ts` — DBType 联合类型加 `'kyuubi'`

**文件**: `web/utils/constants.ts` — dbMapper 加一条记录：

```typescript
kyuubi: {
  label: 'Kyuubi',
  icon: '/icons/kyuubi.png',
  desc: 'Apache Kyuubi - Multi-tenant Thrift JDBC/ODBC server for Spark & Trino.',
},
```

### （可选）前端图标

`web/public/icons/kyuubi.png`，用默认图标占位也行。

## 不做的部分

- **不新建 Trino Connector**：Trino 通过 Kyuubi 代理，走同一个 HiveServer2 协议
- **不新增 Python 依赖**：`pyhive` 已由 HiveConnector 引入

## 验证方式

1. 重启 DB-GPT，`GET /api/v2/serve/datasource-types` 包含 `kyuubi`
2. 前端下拉列表出现 Kyuubi 选项
3. 创建数据源：host 填 Kyuubi 地址，port 填 10009，测试连接和查询
