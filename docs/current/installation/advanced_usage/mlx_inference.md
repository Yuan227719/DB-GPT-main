# MLX 推理

DB-GPT 支持 [MLX](https://github.com/ml-explore/mlx-lm) 推理，这是一个快速且易于使用的 LLM 推理和服务库。

## 安装依赖

`MLX` 是 DB-GPT 的可选依赖。您可以在安装依赖时添加 `--extra "mlx"` 来安装它。

```bash
# 使用 uv 安装 mlx 所需的依赖
# 安装核心依赖并选择所需的扩展
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "mlx" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

## 修改配置文件

安装依赖后，您可以修改配置文件以使用 `mlx` 提供商。

```toml
# 模型配置
[models]
[[models.llms]]
name = "Qwen/Qwen3-0.6B-MLX-4bit"
provider = "mlx"
# 如果未提供，模型将从 Hugging Face 模型中心下载
# 取消注释以下行以指定本地文件系统中的模型路径
# https://huggingface.co/Qwen/Qwen3-0.6B-MLX-4bit
# path = "the-model-path-in-the-local-file-system"
```

### 步骤 3：运行模型

您可以使用以下命令运行模型：

```bash
uv run dbgpt start webserver --config {your_config_file}
```
