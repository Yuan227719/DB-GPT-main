# DB-GPT 集成

DB-GPT 集成了许多数据源和 RAG 存储提供商。

集成包

# 数据源提供商

| 提供商    | 支持    | 安装包                |
|-------------|-----------|---------------------------------|
| MySQL       | ✅       | --extra datasource_mysql        |
| OceanBase   | ✅       |                                 |
| ClickHouse  | ✅       | --extra datasource_clickhouse   |
| Hive        | ✅       | --extra datasource_hive         |
| MSSQL       | ✅       | --extra datasource_mssql        |
| PostgreSQL  | ✅       | --extra datasource_postgres     |
| ApacheDoris | ✅       |                                 |
| StarRocks   | ✅       |                                 |
| Spark       | ✅       | --extra datasource_spark        |
| Oracle      | ✅       | --extra datasource_oracle       |
| Gaussdb     | ✅       | --extra datasource_postgres     |
| openGauss   | ✅       | --extra datasource_postgres     |

# RAG 存储提供商

| 提供商    | 支持    | 安装包               |
|-------------|-----------|--------------------------------|
| Chroma      | ✅         | --extra storage_chroma         |       
| Milvus      | ✅         | --extra storage_milvus         |       
| Elasticsearch | ✅         | --extra storage_elasticsearch   |        
| OceanBase   | ✅         | --extra storage_obvector      |

# Graph RAG 存储提供商

| 提供商 | 支持 | 安装包 |
|----------|----------|------------------|
| TuGraph  | ✅        | --extra graph_rag|
| Neo4j    | ✅         |                  |
