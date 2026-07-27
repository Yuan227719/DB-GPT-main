# KBQA FAQ

### 问题1: text2vec-large-chinese 未找到

请确保您已正确下载 text2vec-large-chinese 嵌入模型

```tip
centos: yum install git-lfs
ubuntu: apt-get install git-lfs -y
macos: brew install git-lfs
```
```bash
cd models
git lfs clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

### 问题2: 如何在 DB-GPT 中更改向量数据库类型

更新 .env 文件并设置 VECTOR_STORE_TYPE。

DB-GPT 目前支持 Chroma（默认）、Milvus（>2.1）、Weaviate、Valkey、OceanBase 向量数据库。
如果您想更改向量数据库，请更新 .env 文件，设置您的向量存储类型，VECTOR_STORE_TYPE=Chroma（目前仅支持 Chroma 和 Milvus（>2.1），如果您设置 Milvus，请设置 MILVUS_URL 和 MILVUS_PORT）。

如果您想使用 OceanBase，请先通过以下命令启动 docker 容器：
```shell
docker run --name=ob433 -e MODE=slim -p 2881:2881 -d quay.io/oceanbase/oceanbase-ce:4.3.3.0-100000142024101215
```

下载配套包：
```shell
pip install --upgrade --quiet pyobvector
```

检查与 OceanBase 的连接并设置向量数据的内存使用比例：
```python
from pyobvector import ObVecClient

tmp_client = ObVecClient()
tmp_client.perform_raw_text_sql(
    "ALTER SYSTEM ob_vector_memory_limit_percentage = 30"
)
```

然后在 .env 文件中设置以下变量：
```shell
VECTOR_STORE_TYPE=OceanBase
OB_HOST=127.0.0.1
OB_PORT=2881
OB_USER=root@test
OB_DATABASE=test
## 可选
# OB_PASSWORD=
## 可选：如果设置了 {OB_ENABLE_NORMALIZE_VECTOR}，存储在 OceanBase 中的向量将被归一化。
# OB_ENABLE_NORMALIZE_VECTOR=True
```
如果您想支持更多向量数据库，您可以自行集成。[如何集成](https://db-gpt.readthedocs.io/en/latest/modules/vector.html)
```commandline
#*******************************************************************#
#**                  向量存储设置                                  **#
#*******************************************************************#
VECTOR_STORE_TYPE=Chroma
#MILVUS_URL=127.0.0.1
#MILVUS_PORT=19530
#MILVUS_USERNAME
#MILVUS_PASSWORD
#MILVUS_SECURE=

#WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network
```
### 问题3: 当我使用 vicuna-13b 时，发现了一些非法字符，如下所示。
<p align="left">
  <img src="https://github.com/eosphoros-ai/DB-GPT/assets/13723926/088d1967-88e3-4f72-9ad7-6c4307baa2f8" width="800px" />
</p>

将 KNOWLEDGE_SEARCH_TOP_SIZE 设置更小或 KNOWLEDGE_CHUNK_SIZE 设置更小，然后重启服务器。

### 问题4: 空间添加错误 (pymysql.err.OperationalError) (1054, "Unknown column 'knowledge_space.context' in 'field list'")

1. 关闭 dbgpt_server（按 ctrl c）

2. 为 knowledge_space 表添加 context 列

```commandline
mysql -h127.0.0.1 -uroot -p {your_password}
```

3. 执行 sql ddl

```commandline
mysql> use knowledge_management;
mysql> ALTER TABLE knowledge_space ADD COLUMN context TEXT COMMENT "arguments context";
```

4. 重启 dbgpt 服务

### 问题5: 使用 Mysql，如何使用 DB-GPT KBQA

构建 Mysql KBQA 系统数据库模式。

```bash
$ mysql -h127.0.0.1 -uroot -p{your_password} < ./assets/schema/knowledge_management.sql
```
