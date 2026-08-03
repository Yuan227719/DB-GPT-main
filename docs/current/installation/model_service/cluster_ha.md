# 高可用

## 架构

以下是高可用集群的架构，更多细节可以在[集群部署](./cluster.md)模式和 [SMMF](../../modules/smmf.md) 模块中找到。

<p align="center">
  <img src={'/img/module/smmf.png'} width="600px" />
</p>

模型 Worker 和 API 服务器可以部署在不同的机器上，并且模型 Worker 和 API 服务器可以部署多个实例。
但模型控制器默认只有一个实例，因为它是一个有状态服务，存储了模型服务的所有元数据，具体来说，所有元数据都存储在名为 **Model Registry** 的组件中。

默认的模型注册表是 `EmbeddedModelRegistry`，它是一个简单的内存组件。
为了支持高可用，我们可以使用 `StorageModelRegistry` 作为模型注册表，
它可以使用数据库作为存储后端，例如 MySQL、SQLite 等。

因此，我们可以部署多个模型控制器实例，它们可以通过连接到同一个数据库来共享元数据。

现在让我们看看如何部署高可用集群。

## 部署高可用集群
为简单起见，我们将在两台机器（`server1` 和 `server2`）上部署两个模型控制器，
并在另一台机器（`server3`）上部署一个模型 Worker、一个嵌入模型 Worker 和一个 Web 服务器。

（当然，您也可以将它们全部部署在同一台机器的不同端口上。）

### 准备 MySQL 数据库

1. 安装 MySQL，为模型控制器创建一个数据库和一个用户。
2. 为模型控制器创建一个表，您可以使用以下 SQL 脚本来创建表。

```sql

-- 用于部署 DB-GPT 的模型集群（StorageModelRegistry）
CREATE TABLE IF NOT EXISTS `dbgpt_cluster_registry_instance` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '自增 ID',
  `model_name` varchar(128) NOT NULL COMMENT '模型名称',
  `host` varchar(128) NOT NULL COMMENT '模型主机',
  `port` int(11) NOT NULL COMMENT '模型端口',
  `weight` float DEFAULT 1.0 COMMENT '模型权重',
  `check_healthy` tinyint(1) DEFAULT 1 COMMENT '是否检查模型健康',
  `healthy` tinyint(1) DEFAULT 0 COMMENT '模型是否健康',
  `enabled` tinyint(1) DEFAULT 1 COMMENT '模型是否启用',
  `prompt_template` varchar(128) DEFAULT NULL COMMENT '模型实例的提示模板',
  `last_heartbeat` datetime DEFAULT NULL COMMENT '模型实例的最后心跳时间',
  `user_name` varchar(128) DEFAULT NULL COMMENT '用户名',
  `sys_code` varchar(128) DEFAULT NULL COMMENT '系统代码',
  `gmt_created` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `gmt_modified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_instance` (`model_name`, `host`, `port`, `sys_code`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COMMENT='集群模型实例表，用于注册和管理模型实例';

```

### 使用存储模型注册表启动模型控制器

我们需要在两台机器（`server1` 和 `server2`）上启动模型控制器，它们将通过连接到同一个数据库来共享元数据。

1. 在 `server1` 上启动模型控制器：

```bash
dbgpt start controller \
--port 8000 \
--registry_type database \
--registry_db_type mysql \
--registry_db_name dbgpt \
--registry_db_host 127.0.0.1 \
--registry_db_port 3306 \
--registry_db_user root \
--registry_db_password aa123456
```
2. 在 `server2` 上启动模型控制器：

```bash
dbgpt start controller \
--port 8000 \
--registry_type database \
--registry_db_type mysql \
--registry_db_name dbgpt \
--registry_db_host 127.0.0.1 \
--registry_db_port 3306 \
--registry_db_user root \
--registry_db_password aa123456
```

注意：请根据您的实际情况修改参数。

### 启动模型 Worker

:::tip
启动 `glm-4-9b-chat` 模型 Worker
:::

```shell
dbgpt start worker --model_name glm-4-9b-chat \
--model_path /app/models/glm-4-9b-chat \
--port 8001 \
--controller_addr "http://server1:8000,http://server2:8000"
```
这里我们使用 `server1` 和 `server2` 作为控制器地址，这样模型 Worker 可以向任何健康的控制器注册。

### 启动嵌入模型 Worker

```shell
dbgpt start worker --model_name text2vec \
--model_path /app/models/text2vec-large-chinese \
--worker_type text2vec \
--port 8003 \
--controller_addr "http://server1:8000,http://server2:8000"
```
:::info 注意
请确保使用您自己的模型名称和模型路径。

:::

### 部署 Web 服务器

```shell
LLM_MODEL=glm-4-9b-chat EMBEDDING_MODEL=text2vec \
dbgpt start webserver \
--light \
--remote_embedding \
--controller_addr "http://server1:8000,http://server2:8000"
```

### 显示您的模型实例

```bash
CONTROLLER_ADDRESS="http://server1:8000,http://server2:8000" dbgpt model list
```

恭喜！您已成功部署了 DB-GPT 的高可用集群。

## 使用 Docker Compose 部署高可用集群

如果您想了解更多关于部署高可用 DB-GPT 集群的信息，可以查看 `docker/compose_examples/ha-cluster-docker-compose.yml` 中的 docker compose 示例。
它使用 OpenAI LLM 和 OpenAI 嵌入模型，因此您可以直接运行它。

这里我们将展示如何使用 docker compose 部署 DB-GPT 的高可用集群。

首先，构建仅包含 openai 依赖的 docker 镜像：

```bash
bash ./docker/base/build_proxy_image.sh --pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

然后，运行以下命令启动高可用集群：

```bash
OPENAI_API_KEY="{your api key}" OPENAI_API_BASE="https://api.openai.com/v1" \
docker compose -f ha-cluster-docker-compose.yml up -d
```

## 问答

### 未来会支持更多的模型注册表类型吗？
是的。我们未来会支持更多的模型注册表类型，例如 `etcd`、`consul` 等。

### 如何使用 Kubernetes 部署高可用集群？
我们未来会提供一个 Helm chart 来使用 Kubernetes 部署高可用集群。
