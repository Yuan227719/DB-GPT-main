# Docker-Compose 部署

## 通过 Docker-Compose 运行

此示例要求您为 SiliconFlow API 提供有效的 API key。您可以通过在 [SiliconFlow](https://siliconflow.cn/) 注册并创建 API key 来获取，地址为 [API Key](https://cloud.siliconflow.cn/account/ak)。
或者，您也可以通过设置 `AIMLAPI_API_KEY` 来使用 [AI/ML API](https://aimlapi.com/)。

```bash
SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY} docker compose up -d
```
或使用 AI/ML API：
```bash
AIMLAPI_API_KEY=${AIMLAPI_API_KEY} docker compose up -d
```

如果部署成功，您将看到以下输出。
```bash
[+] Running 3/3
 ✔ Network dbgptnet              Created                                            0.0s 
 ✔ Container db-gpt-db-1         Started                                            0.2s 
 ✔ Container db-gpt-webserver-1  Started                                            0.2s 
```

## 查看日志
```bash
docker logs db-gpt-webserver-1 -f
```

:::info 注意

更多配置内容，您可以查看 `docker-compose.yml` 文件
:::

## 访问
打开浏览器并访问 [http://localhost:5670](http://localhost:5670)
