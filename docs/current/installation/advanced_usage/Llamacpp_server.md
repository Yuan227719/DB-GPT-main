# LLama.cpp Server

DB-GPT 支持原生 [llama.cpp server](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md)，
它支持并发请求和持续批处理推理。

## 安装依赖

您可以添加 `--extra "llama_cpp_server"` 来安装 llama-cpp server 所需的依赖。

如果您有 NVIDIA GPU，可以通过设置环境变量 `CMAKE_ARGS="-DGGML_CUDA=ON"` 来启用 CUDA 支持。

```bash
# 使用 uv 安装 llama-cpp 所需的依赖
# 安装核心依赖并选择所需的扩展
CMAKE_ARGS="-DGGML_CUDA=ON" uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "llama_cpp_server" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

否则，运行以下命令安装不带 CUDA 支持的依赖。

```bash
# 使用 uv 安装 llama-cpp 所需的依赖
# 安装核心依赖并选择所需的扩展
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "llama_cpp_server" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

## 下载模型

这里，我们以 `qwen2.5-0.5b-instruct` 模型为例。您可以从 [Huggingface](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) 下载该模型。

```bash
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true -O /tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf
````

## 修改配置文件

只需修改您的配置文件以使用 `llama.cpp.server` 提供商。

```toml
# 模型配置
[models]
[[models.llms]]
name = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
provider = "llama.cpp.server"
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF
# path = "the-model-path-in-the-local-file-system"
path = "/tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf"
```
