# vLLM 推理

DB-GPT 支持 [vLLM](https://github.com/vllm-project/vllm) 推理，这是一个快速且易于使用的 LLM 推理和服务库。

## 安装依赖

`vLLM` 是 DB-GPT 的可选依赖。您可以在安装依赖时添加 `--extra "vllm"` 来安装它。

```bash
# 使用 uv 安装 vllm 所需的依赖
# 安装核心依赖并选择所需的扩展
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "vllm" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

## 修改配置文件

安装依赖后，您可以修改配置文件以使用 `vllm` 提供商。

```toml
# 模型配置
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "vllm"
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# path = "the-model-path-in-the-local-file-system"
```

关于 `vLLM` 支持的模型列表的更多信息，请参考 [vLLM 支持的模型文档](https://docs.vllm.ai/en/latest/models/supported_models.html#supported-models)。
