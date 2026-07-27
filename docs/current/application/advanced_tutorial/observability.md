# 可观测性

**可观测性**是一种衡量系统内部状态如何从外部输出中推断出来的能力。在软件系统的语境中，可观测性是通过检查系统的输出来理解系统内部状态的能力。这对于调试、监控和维护系统非常重要。


## DB-GPT 中的可观测性

DB-GPT 通过以下机制提供可观测性：
- **日志记录**：DB-GPT 记录各种事件和指标，帮助您理解系统的内部状态。
- **链路追踪**：DB-GPT 提供追踪能力，帮助您理解请求在系统中的流转过程。

## 日志记录

您可以配置 DB-GPT 日志的日志级别和存储位置。默认情况下，日志存储在 DB-GPT 根目录下的 `logs` 目录中。您可以通过设置 `DBGPT_LOG_LEVEL` 和 `DBGPT_LOG_DIR` 环境变量来更改日志级别和存储位置。


## 链路追踪

DB-GPT 内置了追踪能力，允许您追踪请求在系统中的流转过程。


## 追踪存储

### 本地存储

DB-GPT 会将追踪信息存储在 DB-GPT 日志目录下的 `traces` 目录中，默认情况下，它们位于 `logs/dbgpt*.jsonl`。

如果您想了解更多关于追踪的本地存储及其使用方法，请参考[调试](./debugging)文档。


### OpenTelemetry 支持

DB-GPT 也支持 [OpenTelemetry](https://opentelemetry.io/) 进行分布式追踪。现在，您可以通过 OpenTelemetry 协议（OTLP）将追踪导出到与 OpenTelemetry 兼容的后端，如 Jaeger、Zipkin 等。

要启用 OpenTelemetry 支持，您需要安装以下包：

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

然后，修改您的 `.env` 文件以启用 OpenTelemetry 追踪：

```bash
## 是否启用 DB-GPT 向 OpenTelemetry 发送追踪
TRACER_TO_OPEN_TELEMETRY=True
## 更多详情请参见 https://opentelemetry-python.readthedocs.io/en/latest/exporter/otlp/otlp.html
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317
```
在上述配置中，您可以将 `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` 更改为您的 OTLP 收集器或后端，我们默认使用 gRPC 端点。

这里，我们以 Jaeger 为例来展示如何使用 OpenTelemetry 追踪 DB-GPT。

### Jaeger 支持

以下是通过 Docker 使用 Jaeger 追踪 DB-GPT 的示例：

运行 Jaeger 一体化镜像：

```bash
docker run --rm --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  -p 14250:14250 \
  -p 14268:14268 \
  -p 14269:14269 \
  -p 9411:9411 \
  jaegertracing/all-in-one:1.58
```
然后，像上面一样修改您的 `.env` 文件以启用 OpenTelemetry 追踪。

```bash
TRACER_TO_OPEN_TELEMETRY=True
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317
```

启动 DB-GPT 服务器：

```bash
dbgpt start webserver
```

现在，您可以通过 `http://localhost:16686` 访问 Jaeger UI 来查看追踪信息。

以下是一些 Jaeger UI 的截图示例：

**搜索追踪页面**
<p align="left">
  <img src={'/img/application/advanced_tutorial/observability_img1.png'} width="720px"/>
</p>

**显示普通对话追踪**

<p align="left">
  <img src={'/img/application/advanced_tutorial/observability_img2.png'} width="720px"/>
</p>

**显示对话详情标签**

<p align="left">
  <img src={'/img/application/advanced_tutorial/observability_img3.png'} width="720px"/>
</p>

**显示 Agent 对话追踪**

<p align="left">
  <img src={'/img/application/advanced_tutorial/observability_img4.png'} width="720px"/>
</p>

**显示集群中的追踪**

### 使用 Docker Compose 的 Jaeger 支持

如果您想使用 docker-compose 启动 DB-GPT 和 Jaeger，可以使用以下 `docker-compose.yml` 文件：

```yaml
# 一个使用 docker-compose 启动启用了可观测性的集群的示例。
version: '3.10'

services:
  jaeger:
    image: jaegertracing/all-in-one:1.58
    restart: unless-stopped
    networks:
      - dbgptnet
    ports:
      # 提供前端服务
      - "16686:16686"
      # 通过 Thrift-compact 协议接收 jaeger.thrift（大多数 SDK 使用）
      - "6831:6831"
      # 通过 HTTP 接收 OpenTelemetry 协议（OTLP）
      - "4318:4318"
      # 通过 gRPC 接收 OpenTelemetry 协议（OTLP）
      - "4317:4317"
      - "14268:14268"
    environment:
      - LOG_LEVEL=debug
      - SPAN_STORAGE_TYPE=badger
      - BADGER_EPHEMERAL=false
      - BADGER_DIRECTORY_VALUE=/badger/data
      - BADGER_DIRECTORY_KEY=/badger/key
    volumes:
      - jaeger-badger:/badger
    user: root
  controller:
    image: eosphorosai/dbgpt:latest
    command: dbgpt start controller
    restart: unless-stopped
    environment:
      - TRACER_TO_OPEN_TELEMETRY=True
      - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4317
      - DBGPT_LOG_LEVEL=DEBUG
    networks:
      - dbgptnet
  llm-worker:
    image: eosphorosai/dbgpt:latest
    command: dbgpt start worker --model_type proxy --model_name chatgpt_proxyllm --model_path chatgpt_proxyllm --proxy_server_url ${OPENAI_API_BASE}/chat/completions --proxy_api_key ${OPENAI_API_KEY} --controller_addr http://controller:8000
    environment:
      # 您真实的 OpenAI 模型名称，例如 gpt-3.5-turbo, gpt-4o
      - PROXYLLM_BACKEND=gpt-3.5-turbo
      - TRACER_TO_OPEN_TELEMETRY=True
      - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4317
      - DBGPT_LOG_LEVEL=DEBUG
    depends_on:
      - controller
    restart: unless-stopped
    networks:
      - dbgptnet
    ipc: host
  embedding-worker:
    image: eosphorosai/dbgpt:latest
    command: dbgpt start worker --worker_type text2vec --model_name proxy_http_openapi --model_path proxy_http_openapi --proxy_server_url ${OPENAI_API_BASE}/embeddings --proxy_api_key ${OPENAI_API_KEY} --controller_addr http://controller:8000
    environment:
      - proxy_http_openapi_proxy_backend=text-embedding-3-small
      - TRACER_TO_OPEN_TELEMETRY=True
      - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4317
      - DBGPT_LOG_LEVEL=DEBUG
    depends_on:
      - controller
    restart: unless-stopped
    networks:
      - dbgptnet
    ipc: host
  webserver:
    image: eosphorosai/dbgpt:latest
    command: dbgpt start webserver --light --remote_embedding --controller_addr http://controller:8000
    environment:
      - LLM_MODEL=chatgpt_proxyllm
      - EMBEDDING_MODEL=proxy_http_openapi
      - TRACER_TO_OPEN_TELEMETRY=True
      - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4317
    depends_on:
      - controller
      - llm-worker
      - embedding-worker
    volumes:
      - dbgpt-data:/app/pilot/data
      - dbgpt-message:/app/pilot/message
    ports:
      - 5670:5670/tcp
    restart: unless-stopped
    networks:
      - dbgptnet
volumes:
  dbgpt-data:
  dbgpt-message:
  jaeger-badger:
networks:
  dbgptnet:
    driver: bridge
    name: dbgptnet
```

您可以使用以下命令启动集群：

```bash
OPENAI_API_KEY="{您的 API 密钥}" OPENAI_API_BASE="https://api.openai.com/v1" docker compose up -d
```
请将 `{your api key}` 替换为您的真实 OpenAI API 密钥，并将 `https://api.openai.com/v1` 替换为您的真实 OpenAI API 基础 URL。
您可以在 `docker/compose_examples/observability/docker-compose.yml` 文档中查看更多关于 docker-compose 文件的详细信息。

集群启动后，您可以通过 `http://localhost:16686` 访问 Jaeger UI 来查看追踪信息。

**显示 RAG 对话追踪**

<p align="left">
  <img src={'/img/application/advanced_tutorial/observability_img5.png'} width="720px"/>
</p>

在上面的截图中，您可以看到 DB-GPT 控制器、LLM Worker 和 Web 服务器之间的跨服务通信追踪。
