# Ollama

Ollama 是一个模型服务平台，可以让您在几秒钟内部署模型。它是一个很棒的工具。

### 安装 Ollama
如果您的系统是 Linux。
```bash
curl -fsSL https://ollama.com/install.sh | sh
```
其他环境，请参考 [Ollama 官方网站](https://ollama.com/)。

### 拉取模型
1. 拉取 LLM
```bash
ollama pull qwen:0.5b
```
2. 拉取嵌入模型。
```bash
ollama pull nomic-embed-text
```

3. 安装 ollama 包。
```bash
# 使用 uv 安装 Ollama 代理所需的依赖
uv sync --all-packages \
--extra "base" \
--extra "proxy_ollama" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### 配置模型

修改您的 toml 配置文件以使用 `ollama` 提供商。

```toml
# 模型配置
[models]
[[models.llms]]
name = "qwen:0.5b"
provider = "proxy/ollama"
api_base = "http://localhost:11434"
api_key = ""

[[models.embeddings]]
name = "bge-m3:latest"
provider = "proxy/ollama"
api_url = "http://localhost:11434"
api_key = ""
```
