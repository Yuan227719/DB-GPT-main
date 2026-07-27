# 数据库资源

数据库资源 `DBResource` 是一种用于与数据库交互的资源。
它是 `Resource` 类的子类，提供了与数据库交互的方式。

以下是 `DBResource` 类的一些实现：
- `RDBMSConnectorResource`：一种用于连接关系型数据库管理系统（RDBMS）的资源，例如 MySQL、PostgreSQL 等。
- `SQLiteDBResource`：`RDBMSConnectorResource` 类的一个具体实现，用于连接 SQLite 数据库。
- `DatasourceResource`：一种用于连接 DB-GPT 中各种数据源的资源。
它仅在您在 DB-GPT 环境（在 DB-GPT 网页服务器中运行）中运行智能体时生效。

在前面的章节[智能体与数据库](../../introduction/database)中，我们已经介绍了
如何在 DB-GPT 智能体中使用数据库资源，您可以参考该部分获取更多详细信息。

## 工作原理

（即将推出...）
