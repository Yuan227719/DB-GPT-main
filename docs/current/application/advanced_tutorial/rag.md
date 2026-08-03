# RAG 参数调整
每个知识空间都支持参数自定义，包括向量检索的相关参数以及知识问答提示的参数。

如下图所示，点击"知识"会触发弹窗对话框。点击"参数"按钮进入参数调整界面。
![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/f02039ea-01d7-493a-acd9-027020d54267)


<Tabs
  defaultValue="Embedding"
  values={[
    {label: '嵌入参数', value: 'Embedding'},
    {label: '提示参数', value: 'Prompt'},
    {label: '摘要参数', value: 'Summary'},
  ]}>
  <TabItem value="Embedding" label="嵌入参数">

![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/8a69aba0-3b28-449d-8fd8-ce5bf8dbf7fc)

:::tip 嵌入参数
* topk：基于相似度得分的前 k 个向量。
* recall_score：设置检索相似向量的相似度阈值分数。介于 0 和 1 之间。默认值为 0.3。
* recall_type：召回类型。目前仅支持基于向量相似度的 topk。
* model：用于创建文本或其他数据向量表示的模型。
* chunk_size：处理中使用的数据块大小。默认值为 500。
* chunk_overlap：相邻数据块之间的重叠量。默认值为 50。
:::
 </TabItem>

<TabItem value="Prompt" label="提示参数">

![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/00f12903-8d70-4bfb-9f58-26f03a6a4773)

:::tip 提示参数
* scene：上下文参数，用于定义提示词的使用场景或环境。
* template：提示词的预定义结构或格式，有助于确保 AI 系统生成符合期望风格或语调的响应。
* max_token：提示词中允许的最大 token 数或字数。 
:::

 </TabItem>

<TabItem value="Summary" label="摘要参数">

![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/96782ba2-e9a2-4173-a003-49d44bf874cc)

:::tip 摘要参数
* max_iteration：摘要最大迭代调用 LLM 次数，默认为 5。数值越大，文档摘要效果越好，但耗时更长。
* concurrency_limit：摘要并发调用 LLM 的默认数量，默认为 3。
:::

 </TabItem>

</Tabs>

# 知识查询重写
在 `.env` 文件中设置 `KNOWLEDGE_SEARCH_REWRITE=True`，然后重启服务器。

```shell
# 是否启用聊天知识搜索重写模式
KNOWLEDGE_SEARCH_REWRITE=True
```

# 更改向量数据库
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="Chroma"
  values={[
    {label: 'Chroma', value: 'Chroma'},
    {label: 'Milvus', value: 'Milvus'},
    {label: 'Weaviate', value: 'Weaviate'},
    {label: 'OceanBase', value: 'OceanBase'},
  ]}>
  <TabItem value="Chroma" label="Chroma">

在 `.env` 文件中设置 `VECTOR_STORE_TYPE`。

```shell
### Chroma 向量数据库配置
VECTOR_STORE_TYPE=Chroma
#CHROMA_PERSIST_PATH=/root/DB-GPT/pilot/data
```
 </TabItem>

<TabItem value="Milvus" label="Milvus">
    

在 `.env` 文件中设置 `VECTOR_STORE_TYPE`

```shell
### Milvus 向量数据库配置
VECTOR_STORE_TYPE=Milvus
MILVUS_URL=127.0.0.1
MILVUS_PORT=19530
#MILVUS_USERNAME
#MILVUS_PASSWORD
#MILVUS_SECURE=
  ```
 </TabItem>

<TabItem value="Weaviate" label="Weaviate">

在 `.env` 文件中设置 `VECTOR_STORE_TYPE`

```shell
### Weaviate 向量数据库配置
VECTOR_STORE_TYPE=Weaviate
#WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network
 ```
 </TabItem>

<TabItem value="OceanBase" label="OceanBase">

在 `.env` 文件中设置 `VECTOR_STORE_TYPE`

```shell
OB_HOST=127.0.0.1
OB_PORT=2881
OB_USER=root@test
OB_DATABASE=test
## 可选
# OB_PASSWORD=
## 可选：如果设置了 {OB_ENABLE_NORMALIZE_VECTOR}，则存储在 OceanBase 中的向量会被归一化。
# OB_ENABLE_NORMALIZE_VECTOR=True
```
 </TabItem>
</Tabs>
