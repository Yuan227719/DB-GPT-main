# 数据源

DB-GPT 的数据源模块旨在管理企业的结构化和半结构化数据资产，将数据库、数据仓库、数据湖等连接到 DB-GPT 框架中，快速构建基于数据的智能应用和大模型。目前，DB-GPT 支持一些常见的数据源，也支持自定义扩展。

<p align="center">
  <img src={'/img/app/datasource.jpg'} width="800px" />
</p>


您可以通过右上角的 **Add a data source** 按钮来添加数据源。在弹出的对话框中，选择相应的数据库类型并填写所需参数即可完成添加。

## 支持的数据源类型

当前文档已覆盖或正在扩展以下数据源：

- MySQL
- SQLite
- ClickHouse
- PostgreSQL
- DuckDB
- Hive
- MSSQL
- Oracle
- OceanBase
- GaussDB
- openGauss
- Apache Doris
- StarRocks
- Vertica

<p align="center">
  <img src={'/img/app/datasource_add.jpg'} width="800px" />
</p>
