# 命令行使用

除了接口使用外，本项目还提供了丰富的命令行工具。可以实现模型部署、服务部署及启停、知识库操作（查看、删除、文档加载）、调试和问题定位等能力。

以下是对相关命令行工具使用的系统性介绍。

## 准备工作

在使用 dbgpt 命令之前，首先需要完成项目的安装。详细安装教程请参考：[源码安装](../../installation/sourcecode.md)


## 使用说明
命令行提供了多种能力，我们可以通过以下命令查看。
如图所示，我们可以看到 `dbgpt` 的命令列表，包括 `install`、`knowledge`、`model`、`start`、`stop` 和 `trace`

```python
~ dbgpt --help
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
  stop       Stop specific server.
  trace      Analyze and visualize trace spans.
```

## 安装
`install` 命令提供各种依赖包和插件的安装和使用

:::info
Agent 目前正在重构中，相关功能将在下一个版本中提供
:::

## 知识库命令
`dbgpt knowledge` 命令主要提供与知识库相关的操作。当前主要命令包括 `delete`、`list` 和 `load`

```python
~ dbgpt knowledge --help
Already connect 'dbgpt'
Usage: dbgpt knowledge [OPTIONS] COMMAND [ARGS]...

  Knowledge command line tool

Options:
  --address TEXT  Address of the Api server(If not set, try to read from
                  environment variable: API_ADDRESS).  [default:
                  http://127.0.0.1:5670]
  --help          Show this message and exit.

Commands:
  delete  Delete your knowledge space or document in space
  list    List knowledge space
  load    Load your local documents to DB-GPT
```

#### 加载命令
`dbgpt knowledge load` 指的是知识库文档的加载。你可以通过 load 命令批量加载知识库文档。

```python
~ dbgpt knowledge load --help
Already connect 'dbgpt'
Usage: dbgpt knowledge load [OPTIONS]

  Load your local documents to DB-GPT

Options:
  --space_name TEXT         Your knowledge space name  [default: default]
  --vector_store_type TEXT  Vector store type.  [default: Chroma]
  --local_doc_path TEXT     Your document directory or document file path.
                            [default: /Users/magic/workspace/github/eosphoros-
                            ai/DB-GPT/pilot/datasets]
  --skip_wrong_doc          Skip wrong document.
  --overwrite               Overwrite existing document(they has same name).
  --max_workers INTEGER     The maximum number of threads that can be used to
                            upload document.
  --pre_separator TEXT      Preseparator, this separator is used for pre-
                            splitting before the document is actually split by
                            the text splitter. Preseparator are not included
                            in the vectorized text.
  --separator TEXT          This is the document separator. Currently, only
                            one separator is supported.
  --chunk_size INTEGER      Maximum size of chunks to split.
  --chunk_overlap INTEGER   Overlap in characters between chunks.
  --help                    Show this message and exit.
```


<p align="left">
  <img src={'/img/cli/kbqa.gif'} width="720px"/>
</p>

#### 列表命令
`dbgpt knowledge list` 命令主要展示与知识库相关的信息。例如显示知识空间、文档内容、Chunk 内容等。

```python
~ dbgpt knowledge list --help
Already connect 'dbgpt'
Usage: dbgpt knowledge list [OPTIONS]

  List knowledge space

Options:
  --space_name TEXT               Your knowledge space name. If None, list all
                                  spaces
  --doc_id INTEGER                Your document id in knowledge space. If Not
                                  None, list all chunks in current document
  --page INTEGER                  The page for every query  [default: 1]
  --page_size INTEGER             The page size for every query  [default: 20]
  --show_content                  Query the document content of chunks
  --output [text|html|csv|latex|json]
                                  The output format
  --help                          Show this message and exit.
```
#### 删除命令
删除命令支持知识库和文档的删除。你可以通过 `dbgpt knowledge delete --help` 查看相关命令详情

```python
~ dbgpt knowledge delete --help
Already connect 'dbgpt'
Usage: dbgpt knowledge delete [OPTIONS]

  Delete your knowledge space or document in space

Options:
  --space_name TEXT  Your knowledge space name  [default: default]
  --doc_name TEXT    The document name you want to delete. If doc_name is
                     None, this command will delete the whole space.
  -y                 Confirm your choice
  --help             Show this message and exit.
```

<p align="left">
  <img src={'/img/cli/kd_new.gif'} width="720px"/>
</p>


## 模型命令
模型相关命令主要用于部署多个模型时的操作。关于模型集群部署，可以查看[集群部署模式](../../installation/model_service/cluster.md)。

```python
~ dbgpt model --help
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

#### 聊天命令
你可以使用 `dbgpt model chat` 命令在命令行终端与模型进行通信

```python
~ dbgpt model chat --help
Already connect 'dbgpt'
Usage: dbgpt model chat [OPTIONS]

  Interact with your bot from the command line

Options:
  --model_name TEXT  The name of model  [required]
  --system TEXT      System prompt
  --help             Show this message and exit.
```

#### 列表命令

```python
~ dbgpt model list --help
Already connect 'dbgpt'
Usage: dbgpt model list [OPTIONS]

  List model instances

Options:
  --model_name TEXT  The name of model
  --model_type TEXT  The type of model
  --help             Show this message and exit.
```

#### 重启命令
可以通过 `dbgpt model restart` 命令重启模型

```python
~ dbgpt model restart  --help
Already connect 'dbgpt'
Usage: dbgpt model restart [OPTIONS]

  Restart model instances

Options:
  --model_name TEXT  The name of model  [required]
  --model_type TEXT  The type of model
  --help             Show this message and exit.
```

#### 启动命令
可以通过 `dbgpt model start` 命令启动模型
```python
~ dbgpt model start  --help
Already connect 'dbgpt'
Usage: dbgpt model start [OPTIONS]

  Start model instances

Options:
  --model_name TEXT           The model name to deploy  [required]
  --model_path TEXT           The model path to deploy
  --host TEXT                 The remote host to deploy model  [default:
                              30.183.153.197]
  --port INTEGER              The remote port to deploy model  [default: 5000]
  --worker_type TEXT          Worker type  [default: llm]
  --device TEXT               Device to run model. If None, the device is
                              automatically determined
  --model_type TEXT           Model type: huggingface, llama.cpp, proxy and
                              vllm  [default: huggingface]
  --prompt_template TEXT      Prompt template. If None, the prompt template is
                              automatically determined from model path,
                              supported template: zero_shot,vicuna_v1.1,llama-
                              2,codellama,alpaca,baichuan-chat,internlm-chat
  --max_context_size INTEGER  Maximum context size  [default: 4096]
  --num_gpus INTEGER          The number of gpus you expect to use, if it is
                              empty, use all of them as much as possible
  --max_gpu_memory TEXT       The maximum memory limit of each GPU, only valid
                              in multi-GPU configuration
  --cpu_offloading            CPU offloading
  --load_8bit                 8-bit quantization
  --load_4bit                 4-bit quantization
  --quant_type TEXT           Quantization datatypes, `fp4` (four bit float)
                              and `nf4` (normal four bit float), only valid
                              when load_4bit=True  [default: nf4]
  --use_double_quant          Nested quantization, only valid when
                              load_4bit=True  [default: True]
  --compute_dtype TEXT        Model compute type
  --trust_remote_code         Trust remote code  [default: True]
  --verbose                   Show verbose output.
  --help                      Show this message and exit.
```

#### 停止命令
`dbgpt model stop` 命令主要负责停止模型。

```python
~ dbgpt model stop  --help
Already connect 'dbgpt'
Usage: dbgpt model stop [OPTIONS]

  Stop model instances

Options:
  --model_name TEXT  The name of model  [required]
  --model_type TEXT  The type of model
  --host TEXT        The remote host to stop model  [required]
  --port INTEGER     The remote port to stop model  [required]
  --help             Show this message and exit.
```


<p align="left">
  <img src={'/img/cli/cli_m.gif'} width="720px"/>
</p>

## 启动/停止命令
`dbgpt start` 和 `dbgpt stop` 相关命令是一组与服务注册发现相关的接口。分别有 `apiserver`、`controller`、`worker` 和 `webserver`。

```python
~ dbgpt start --help
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
```

#### API 服务器
你可以通过 `dbgpt start apiserver` 启动模型的 API 服务。默认启动端口为 8100。

```python
~ dbgpt start apiserver --help
Already connect 'dbgpt'
Usage: dbgpt start apiserver [OPTIONS]

  Start apiserver

Options:
  --host TEXT                Model API server deploy host  [default: 0.0.0.0]
  --port INTEGER             Model API server deploy port  [default: 8100]
  --daemon                   Run Model API server in background
  --controller_addr TEXT     The Model controller address to connect
                             [default: http://127.0.0.1:8000]
  --api_keys TEXT            Optional list of comma separated API keys
  --log_level TEXT           Logging level
  --log_file TEXT            The filename to store log  [default:
                             dbgpt_model_apiserver.log]
  --tracer_file TEXT         The filename to store tracer span records
                             [default: dbgpt_model_apiserver_tracer.jsonl]
  --tracer_storage_cls TEXT  The storage class to storage tracer span records
  --help                     Show this message and exit.

```
`start apiserver`
```python
~ dbgpt start apiserver

    Already connect 'dbgpt'
    2023-12-07 14:35:21 B-4TMH9N3X-2120.local pilot.component[95201] INFO Register component with name dbgpt_model_registry and instance: <pilot.model.cluster.controller.controller.ModelRegistryClient object at 0x28f4e0c70>
    2023-12-07 14:35:21 B-4TMH9N3X-2120.local pilot.component[95201] INFO Register component with name dbgpt_worker_manager_factory and instance: <pilot.model.cluster.worker.manager._DefaultWorkerManagerFactory object at 0x28f4e2110>
    2023-12-07 14:35:21 B-4TMH9N3X-2120.local pilot.component[95201] INFO Register component with name dbgpt_model_api_server and instance: <pilot.model.cluster.apiserver.api.APIServer object at 0x28f4e2170>
    INFO:     Started server process [95201]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://0.0.0.0:8100 (Press CTRL+C to quit)
    INFO:     127.0.0.1:56638 - "GET /docs HTTP/1.1" 200 OK
    INFO:     127.0.0.1:56665 - "GET /openapi.json HTTP/1.1" 200 OK
    ^CINFO:     Shutting down
    INFO:     Waiting for application shutdown.
    INFO:     Application shutdown complete.
    INFO:     Finished server process [95201]
```


#### 控制器命令
可以通过 `dbgpt start controller` 启动管理和控制服务。默认启动端口为 8000

```python
~ dbgpt start --help
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
(dbgpt_env) magic@B-4TMH9N3X-2120 ~ % dbgpt start controller
Already connect 'dbgpt'
INFO:     Started server process [96797]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### Web 服务器命令
可以通过 `dbgpt start webserver` 启动前端服务，默认端口为 5670，可通过 `http://127.0.0.1:5670` 访问

```python
~ dbgpt start webserver --help
Already connect 'dbgpt'
Usage: dbgpt start webserver [OPTIONS]

  Start webserver(dbgpt_server.py)

Options:
  --host TEXT                Webserver deploy host  [default: 0.0.0.0]
  --port INTEGER             Webserver deploy port  [default: 5000]
  --daemon                   Run Webserver in background
  --controller_addr TEXT     The Model controller address to connect. If None,
                             read model controller address from environment
                             key `MODEL_SERVER`.
  --model_name TEXT          The default model name to use. If None, read
                             model name from environment key `LLM_MODEL`.
  --share                    Whether to create a publicly shareable link for
                             the interface. Creates an SSH tunnel to make your
                             UI accessible from anywhere.
  --remote_embedding         Whether to enable remote embedding models. If it
                             is True, you need to start a embedding model
                             through `dbgpt start worker --worker_type
                             text2vec --model_name xxx --model_path xxx`
  --log_level TEXT           Logging level
  --light                    enable light mode
  --log_file TEXT            The filename to store log  [default:
                             dbgpt_webserver.log]
  --tracer_file TEXT         The filename to store tracer span records
                             [default: dbgpt_webserver_tracer.jsonl]
  --tracer_storage_cls TEXT  The storage class to storage tracer span records
  --disable_alembic_upgrade  Whether to disable alembic to initialize and
                             upgrade database metadata
  --help                     Show this message and exit.
```


<p align="left">
  <img src={'/img/cli/start_cli_new.gif'} width="720px"/>
</p>

#### Worker 命令

`dbgpt start worker` 主要用于启动工作模型。详细用法请参考[集群部署](../../installation/model_service/cluster.md)


## 调试

dbgpt 项目提供了丰富的调试命令。详细用法请参考[调试](./debugging.md)
