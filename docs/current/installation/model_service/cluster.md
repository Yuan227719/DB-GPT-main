# 集群部署

## 安装命令行工具
以下所有操作均通过 `dbgpt` 命令完成。要使用 `dbgpt` 命令，您首先需要安装 `DB-GPT` 项目。您可以通过以下命令安装

```shell
$ pip install -e ".[default]"
```
也可以在脚本模式下使用
```shell
$ python pilot/scripts/cli_scripts.py
```

## 启动模型控制器
```shell
$ dbgpt start controller
```

## 查看日志
```shell
$ docker logs db-gpt-webserver-1 -f
```
默认情况下，`Model Server` 将在端口 `8000` 上启动

## 启动模型 Worker

:::tip
启动 `glm-4-9b-chat` 模型 Worker
:::

```shell
dbgpt start worker --model_name glm-4-9b-chat \
--model_path /app/models/glm-4-9b-chat \
--port 8001 \
--controller_addr http://127.0.0.1:8000
```

:::tip
启动 `vicuna-13b-v1.5` 模型 Worker
:::

```shell
dbgpt start worker --model_name vicuna-13b-v1.5 \
--model_path /app/models/vicuna-13b-v1.5 \
--port 8002 \
--controller_addr http://127.0.0.1:8000
```
:::info 注意
请确保使用您自己的模型名称和模型路径。

:::

## 启动嵌入模型 Worker

```shell
dbgpt start worker --model_name text2vec \
--model_path /app/models/text2vec-large-chinese \
--worker_type text2vec \
--port 8003 \
--controller_addr http://127.0.0.1:8000
```
:::info 注意
请确保使用您自己的模型名称和模型路径。

:::

## 启动重排序模型 Worker

```shell
dbgpt start worker --worker_type text2vec \
--rerank \
--model_path /app/models/bge-reranker-base \
--model_name bge-reranker-base \
--port 8004 \
--controller_addr http://127.0.0.1:8000
```
:::info 注意
请确保使用您自己的模型名称和模型路径。

:::

:::tip
查看和检查已部署的模型
:::

```shell
$ dbgpt model list

+-------------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|    Model Name     | Model Type |    Host    | Port | Healthy | Enabled | Prompt Template |       Last Heartbeat       |
+-------------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|   glm-4-9b-chat     |    llm     | 172.17.0.2 | 8001 |   True  |   True  |                 | 2023-09-12T23:04:31.287654 |
|  WorkerManager    |  service   | 172.17.0.2 | 8001 |   True  |   True  |                 | 2023-09-12T23:04:31.286668 |
|  WorkerManager    |  service   | 172.17.0.2 | 8003 |   True  |   True  |                 | 2023-09-12T23:04:29.845617 |
|  WorkerManager    |  service   | 172.17.0.2 | 8002 |   True  |   True  |                 | 2023-09-12T23:04:24.598439 |
|  WorkerManager    |  service   | 172.21.0.5 | 8004 |   True  |   True  |                 | 2023-09-12T23:04:24.598439 |
|     text2vec      |  text2vec  | 172.17.0.2 | 8003 |   True  |   True  |                 | 2023-09-12T23:04:29.844796 |
| vicuna-13b-v1.5   |    llm     | 172.17.0.2 | 8002 |   True  |   True  |                 | 2023-09-12T23:04:24.597775 |
| bge-reranker-base |  text2vec  | 172.21.0.5 | 8004 |   True  |   True  |                 | 2024-05-15T11:36:12.935012 |
+-------------------+------------+------------+------+---------+---------+-----------------+----------------------------+
```

## 使用模型服务

如上部署的模型服务可以通过 dbgpt_server 来使用。首先修改 `.env` 配置文件，更改连接的模型地址

```shell
dbgpt start webserver --light
```

## 启动 Webserver 

```shell
LLM_MODEL=vicuna-13b-v1.5
# 当前默认的 MODEL_SERVER 地址是 Model Controller 的地址
MODEL_SERVER=http://127.0.0.1:8000
```
`--light` 表示不启动嵌入模型服务。

或者可以通过命令直接启动并指定模型。
```shell
LLM_MODEL=glm-4-9b-chat dbgpt start webserver --light --remote_embedding
```

## 命令行使用
有关命令行的更多使用信息，您可以查看命令行帮助。以下是一个参考示例。

:::tip
查看 dbgpt 帮助 `dbgpt --help`
:::

```shell
dbgpt --help

Already connect 'dbgpt'
Usage: dbgpt [OPTIONS] COMMAND [ARGS]...

Options:
  --log-level TEXT  Log level
  --version         Show the version and exit.
  --help            Show this message and exit.

Commands:
  install    Install dependencies, plugins, etc.
  knowledge  Knowledge command line tool
  model      Clients that manage model serving
  start      Start specific server.
  stop       Start specific server.
  trace      Analyze and visualize trace spans.
```

:::tip
查看 dbgpt start 命令 `dbgpt start --help`
:::

```shell
dbgpt start --help

Already connect 'dbgpt'
Usage: dbgpt start [OPTIONS] COMMAND [ARGS]...

  Start specific server.

Options:
  --help  Show this message and exit.

Commands:
  apiserver   Start apiserver
  controller  Start model controller
  webserver   Start webserver(dbgpt_server.py)
  worker      Start model worker
(dbgpt_env) magic@B-4TMH9N3X-2120 ~ %
```

:::tip
查看 dbgpt start model service 帮助命令 `dbgpt start worker --help`
:::

```shell
dbgpt start worker --help

Already connect 'dbgpt'
Usage: dbgpt start worker [OPTIONS]

  Start model worker

Options:
  --model_name TEXT               Model name  [required]
  --model_path TEXT               Model path  [required]
  --worker_type TEXT              Worker type
  --worker_class TEXT             Model worker class,
                                  pilot.model.cluster.DefaultModelWorker
  --model_type TEXT               Model type: huggingface, llama.cpp, proxy
                                  and vllm  [default: huggingface]
  --host TEXT                     Model worker deploy host  [default: 0.0.0.0]
  --port INTEGER                  Model worker deploy port  [default: 8001]
  --daemon                        Run Model Worker in background
  --limit_model_concurrency INTEGER
                                  Model concurrency limit  [default: 5]
  --standalone                    Standalone mode. If True, embedded Run
                                  ModelController
  --register                      Register current worker to model controller
                                  [default: True]
  --worker_register_host TEXT     The ip address of current worker to register
                                  to ModelController. If None, the address is
                                  automatically determined
  --controller_addr TEXT          The Model controller address to register
  --send_heartbeat                Send heartbeat to model controller
                                  [default: True]
  --heartbeat_interval INTEGER    The interval for sending heartbeats
                                  (seconds)  [default: 20]
  --log_level TEXT                Logging level
  --log_file TEXT                 The filename to store log  [default:
                                  dbgpt_model_worker_manager.log]
  --tracer_file TEXT              The filename to store tracer span records
                                  [default:
                                  dbgpt_model_worker_manager_tracer.jsonl]
  --tracer_storage_cls TEXT       The storage class to storage tracer span
                                  records
  --device TEXT                   Device to run model. If None, the device is
                                  automatically determined
  --prompt_template TEXT          Prompt template. If None, the prompt
                                  template is automatically determined from
                                  model path, supported template: zero_shot,vi
                                  cuna_v1.1,llama-2,codellama,alpaca,baichuan-
                                  chat,internlm-chat
  --max_context_size INTEGER      Maximum context size  [default: 4096]
  --num_gpus INTEGER              The number of gpus you expect to use, if it
                                  is empty, use all of them as much as
                                  possible
  --max_gpu_memory TEXT           The maximum memory limit of each GPU, only
                                  valid in multi-GPU configuration
  --cpu_offloading                CPU offloading
  --load_8bit                     8-bit quantization
  --load_4bit                     4-bit quantization
  --quant_type TEXT               Quantization datatypes, `fp4` (four bit
                                  float) and `nf4` (normal four bit float),
                                  only valid when load_4bit=True  [default:
                                  nf4]
  --use_double_quant              Nested quantization, only valid when
                                  load_4bit=True  [default: True]
  --compute_dtype TEXT            Model compute type
  --trust_remote_code             Trust remote code  [default: True]
  --verbose                       Show verbose output.
  --help                          Show this message and exit.
```

:::tip
查看 dbgpt model service 相关命令 `dbgpt model --help`
:::

```shell
dbgpt model --help


Already connect 'dbgpt'
Usage: dbgpt model [OPTIONS] COMMAND [ARGS]...

  Clients that manage model serving

Options:
  --address TEXT  Address of the Model Controller to connect to. Just support
                  light deploy model, If the environment variable
                  CONTROLLER_ADDRESS is configured, read from the environment
                  variable
  --help          Show this message and exit.

Commands:
  chat     Interact with your bot from the command line
  list     List model instances
  restart  Restart model instances
  start    Start model instances
  stop     Stop model instances
```
