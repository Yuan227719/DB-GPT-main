# AI/ML API

### AI/ML API 提供 300+ 种 AI 模型，包括 Deepseek、Gemini、ChatGPT。这些模型以企业级速率限制和正常运行时间运行。

### 本节介绍如何将 AI/ML API 提供商与 DB-GPT 一起使用。

1. 在 [AI/ML API](https://aimlapi.com/app/?utm_source=db_gpt&utm_medium=github&utm_campaign=integration) 注册并生成 API key。
2. 将环境变量 `AIMLAPI_API_KEY` 设置为您的 key。
3. 在启动 DB-GPT 时使用 `configs/dbgpt-proxy-aimlapi.toml` 配置。

### 您可以在 [https://aimlapi.com/models/](https://aimlapi.com/models/?utm_source=db_gpt&utm_medium=github&utm_campaign=integration) 查找模型。

### 或者您可以使用 docker/base/Dockerfile 结合 AI/ML API 运行 DB-GPT：

```dockerfile
# 暴露 Web 服务器的端口，如果您想直接从 Dockerfile 运行
EXPOSE 5670

# 设置 AIMLAPI API key 的环境变量
ENV AIMLAPI_API_KEY="***"

# 只需取消注释 Dockerfile 中的以下行即可使用 AI/ML API：
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-aimlapi.toml"]
```
