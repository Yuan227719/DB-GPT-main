# SMMF
面向服务的多模型管理框架（SMMF，Service-oriented Multi-model Management Framework）

# 简介

在 AIGC 应用探索和生产落地中，难以避免直接对接模型服务，但目前大模型推理部署还没有事实上的标准，新模型不断发布、新的训练方法不断提出，我们需要花费大量时间来适配不断变化的底层模型环境，这在一定程度上制约了 AIGC 应用的探索和落地。

# 系统设计
为了简化模型适配过程，提高模型部署效率和性能，我们提出了面向服务的多模型管理框架（SMMF）。

<p align="center">
  <img src={'/img/module/smmf_layer.png'} width="360px" />
</p>

SMMF 由两部分组成：模型推理层和模型部署层。模型推理层对应模型推理框架 vLLM、TGI 和 TensorRT 等。模型部署层向下连接推理层，向上提供模型服务能力。模型部署框架基于推理框架，提供多模型实例、多推理框架、多云、自动扩缩容<sup>[1]</sup> 和可观测性<sup>[2]</sup> 等能力。

<p align="center">
  <img src={'/img/module/smmf.png'} width="600px" />
</p>

在 DB-GPT 中，SMMF 具体如上图所示：顶层对应服务和应用程序层（如 DB-GPT WebServer、Agent 系统、应用程序等）。下一层是模型部署框架层，包括向应用层提供模型服务的 API Server 和 Model Handle、整个部署框架的元数据管理和控制中心 Model Controller，以及直接与推理框架和底层环境对接的 Model Worker。再下一层是推理框架层，包括 vLLM、llama.cpp 和 FastChat（由于 DB-GPT 直接使用 FastChat 的推理接口，这里也将 FastChat 归类为推理框架），大语言模型（Vicuna、Llama、Baichuan、ChatGLM 等）部署在推理框架中。最底层是实际的部署环境，包括 Kubernetes、Ray、AWS、阿里云、私有云等。

## SMMF 特性
- 支持多模型和多推理框架

- 可扩展性和稳定性

- 高框架性能

- 可管理和可监控

- 轻量级

### 多模型和多推理框架
当前大模型领域的发展日新月异。新模型不断发布，模型训练和推理方面的新方法不断提出。我们判断这种情况将持续一段时间。

对于大多数探索和实施 AIGC 应用场景的用户来说，这种情况既有优势也有劣势。一个典型的缺点是被模型"牵着鼻子走"，需要不断尝试和探索新模型和新推理框架。

在 DB-GPT 中，直接提供了对 FastChat、vLLM 和 llama.cpp 的无缝支持。理论上，DB-GPT 支持它们所支持的所有模型。如果您对推理速度和战术能力有需求，可以直接使用 vLLM；如果您希望 CPU 或 Mac 的 M1/M2 芯片也能获得良好的推理性能，可以使用 llama.cpp。此外，DB-GPT 还支持代理模型，例如：OpenAI、Azure、Google Bard、通义千问、百川、讯飞星火、百度文心、智谱 AI 等。

### 支持的 LLM
#### 开源模型
  - [Vicuna](https://huggingface.co/Tribbiani/vicuna-13b)
  - [vicuna-13b-v1.5](https://huggingface.co/lmsys/vicuna-13b-v1.5)
  - [LLama2](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf)
  - [baichuan2-13b](https://huggingface.co/baichuan-inc/Baichuan2-13B-Chat)
  - [baichuan2-7b](https://huggingface.co/baichuan-inc/Baichuan2-7B-Chat)
  - [chatglm-6b](https://huggingface.co/THUDM/chatglm-6b)
  - [chatglm2-6b](https://huggingface.co/THUDM/chatglm2-6b)
  - [chatglm3-6b](https://huggingface.co/THUDM/chatglm3-6b)
  - [falcon-40b](https://huggingface.co/tiiuae/falcon-40b)
  - [internlm-chat-7b](https://huggingface.co/internlm/internlm-chat-7b)
  - [internlm-chat-20b](https://huggingface.co/internlm/internlm-chat-20b)
  - [qwen-7b-chat](https://huggingface.co/Qwen/Qwen-7B-Chat)
  - [qwen-14b-chat](https://huggingface.co/Qwen/Qwen-14B-Chat)
  - [wizardlm-13b](https://huggingface.co/WizardLM/WizardLM-13B-V1.2)
  - [orca-2-7b](https://huggingface.co/microsoft/Orca-2-7b)
  - [orca-2-13b](https://huggingface.co/microsoft/Orca-2-13b)
  - [openchat_3.5](https://huggingface.co/openchat/openchat_3.5)
  - [zephyr-7b-alpha](https://huggingface.co/HuggingFaceH4/zephyr-7b-alpha)
  - [mistral-7b-instruct-v0.1](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.1)
  - [Yi-34B-Chat](https://huggingface.co/01-ai/Yi-34B-Chat)

#### 代理模型
  - [OpenAI·ChatGPT](https://api.openai.com/)
  - [百川·Baichuan](https://platform.baichuan-ai.com/)
  - [阿里·通义](https://www.aliyun.com/product/dashscope)
  - [Google·Bard](https://bard.google.com/)
  - [百度·文心](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
  - [智谱·ChatGLM](http://open.bigmodel.cn/)
  - [讯飞·星火](https://xinghuo.xfyun.cn/)

:::info
更多 LLM，请参考[源代码](https://github.com/eosphoros-ai/DB-GPT/blob/main/pilot/configs/model_config.py)
:::

### 可扩展性和稳定性
云原生领域解决了海量计算资源管理、控制、调度和利用的核心痛点。让计算的价值得到充分释放，使大规模计算成为无处不在的技术。

在大模型领域，我们也关注模型推理过程中对计算资源的爆发式需求。因此，在生产实施中，具备调度超级计算能力的多模型管理是我们的关注重点。鉴于 Kubernetes 和 Istio 等计算调度层在过去几年中的出色成就，我们在多模型管理和控制中充分借鉴了相关设计理念。

一个相对完整的模型部署框架需要多个部分，包括直接与底层推理框架对接的 Model Worker、管理和维护多个模型组件的 Model Controller，以及对外提供模型服务能力的 Model API。Model Worker 必须是可扩展的。它可以是专门部署大语言模型的 Model Worker，也可以是用于部署 Embedding 模型的 Model Worker。当然，也可以基于部署环境，如物理机环境、Kubernetes 环境和某些特定云环境，根据服务商提供的云环境选择不同的 Model Worker。

用于管理元数据的 Model Controller 也需要可扩展，并且必须针对不同的部署环境和不同的模型管理和控制需求选择不同的 Model Controller。此外，从技术角度来看，模型服务与传统微服务有很多共同点。在微服务中，微服务中的某个服务可以有多个服务实例，所有服务实例统一注册到注册中心。服务调用者根据服务名称从注册中心拉取对应服务名称的服务列表，然后根据某种负载均衡策略选择特定的服务实例进行调用。

在模型部署中，也可以考虑类似的架构。某个模型可以有多个模型实例。所有模型实例统一注册到模型注册中心，然后模型服务调用者根据模型名称到注册中心拉取模型实例列表，然后根据模型的负载均衡策略调用特定的模型实例。

这里我们引入模型注册中心，负责在 Model Controller 中存储模型实例元数据。它可以直接使用现有微服务中的注册中心作为实现（如 nacos、eureka、etcd 和 console 等），这样整个部署系统可以实现高可用。

### 高框架性能

框架层不应成为模型推理性能的瓶颈。大多数情况下，硬件和推理框架决定了模型服务的能力，而模型推理的部署和优化是一个复杂的工程，不合适的框架设计可能会增加这种复杂性。我们认为，为了在性能方面"不拖后腿"，部署框架主要关注两点：

避免过度封装：封装越多、链路越长，排查性能问题就越困难。

高性能通信设计：高性能通信设计涉及诸多方面，在此不一一赘述。由于 Python 目前在 AIGC 应用中占据主导地位，在 Python 中，异步接口对服务性能至关重要。因此，模型服务层只提供异步接口，以便与模型推理框架对接层兼容，如果模型推理框架提供异步接口则直接对接，否则使用同步转异步的任务支持。

### 可管理和可监控
在 AIGC 应用探索或 AIGC 应用生产实施中，我们需要模型部署系统具备一定的管理能力，能够通过 API 或命令行对部署的模型实例进行一定的管理和控制（例如：上线、下线、重启、调试等）。

可观测性是生产系统非常重要的能力。我们认为可观测性在 AIGC 应用中至关重要。因为用户体验以及用户与系统之间的交互更加复杂，除了传统的观测指标外，我们更加关注用户的输入信息和相应场景的上下文信息。调用了哪个模型实例和模型参数、模型的输出内容和响应时间、用户反馈等。

我们可以从这些信息中发现模型服务的一些性能瓶颈和用户体验数据。

响应延迟如何？

是否解决了用户问题，以及从用户内容中提取用户满意度等。

这些是进一步优化整个应用的基础。

### 轻量级
考虑到支持的众多模型和推理框架，我们需要努力避免不必要的依赖，确保用户可以按需安装。

在 DB-GPT 中，用户可以按需安装自己的依赖。一些主要的可选依赖如下：

- 安装最基本的依赖 `pip install -e .` 或 `pip install -e ".[core]"`

- 安装基础框架的依赖 `pip install -e ".[framework]"`

- 安装 OpenAI 代理模型的依赖 `pip install -e ".[openai]"`

- 安装默认依赖 `pip install -e ".[default]"`

- 安装 vLLM 推理框架的依赖 `pip install -e ".[vllm]"`

- 安装模型量化部署的依赖 `pip install -e ".[quantization]"`

- 安装知识库相关依赖 `pip install -e ".[knowledge]"`

- 安装 PyTorch 依赖 `pip install -e ".[torch]"`

- 安装 llama.cpp 的依赖 `pip install -e ".[llama_cpp]"`

- 安装向量化数据库依赖 `pip install -e ".[vstore]"`

- 安装数据源依赖 `pip install -e ".[datasource]"`

## 实现
有关多模型相关实现，请参考[源代码](https://github.com/eosphoros-ai/DB-GPT/tree/main/pilot/model)

# 附录
`[1]` `[2]` 自动扩缩容和可观测性等功能仍在孵化中，尚未实现。
