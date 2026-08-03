# 评估

开始使用评估 API


### 创建评估

```python
POST /api/v2/serve/evaluate/evaluation
```
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="curl_evaluation"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_evaluation'},
    {label: 'Python', value: 'python_evaluation'},
  ]
}>

<TabItem value="curl_evaluation">

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X POST "http://localhost:5670/api/v2/serve/evaluate/evaluation" 
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json" \
-d '{
  "scene_key": "recall",
  "scene_value":147,
  "context":{"top_k":5},
  "sys_code":"xx",
  "evaluate_metrics":["RetrieverHitRateMetric","RetrieverMRRMetric","RetrieverSimilarityMetric"],
  "datasets": [{
            "query": "what awel talked about",
            "doc_name":"awel.md"
        }]
}'

```
 </TabItem>

<TabItem value="python_evaluation">


```python
from dbgpt_client import Client
from dbgpt_client.evaluation import run_evaluation
from dbgpt.serve.evaluate.api.schemas import EvaluateServeRequest

DBGPT_API_KEY = "dbgpt"
client = Client(api_key=DBGPT_API_KEY)
request = EvaluateServeRequest(
    # 评估的场景类型，例如支持 app、recall
    scene_key="recall",
    # 例如 app id（当 scene_key 为 app 时），space id（当 scene_key 为 recall 时）
    scene_value="147",
    context={"top_k": 5},
    evaluate_metrics=[
        "RetrieverHitRateMetric",
        "RetrieverMRRMetric",
        "RetrieverSimilarityMetric",
    ],
    datasets=[
        {
            "query": "what awel talked about",
            "doc_name": "awel.md",
        }
    ],
)
data = await run_evaluation(client, request=request)

```

 </TabItem>
</Tabs>

#### 请求体
请求 <a href="#the-evaluation-request">评估对象</a>

当 scene_key 为 app 时，请求体应如下所示：
```json

{
  "scene_key": "app",
  "scene_value":"2c76eea2-83b6-11ef-b482-acde48001122",
  "context":{"top_k":5, "prompt":"942acd7e33b54ce28565f89f9b278044","model":"zhipu_proxyllm"},
  "sys_code":"xx",
  "evaluate_metrics":["AnswerRelevancyMetric"],
  "datasets": [{
            "query": "what awel talked about",
            "doc_name":"awel.md"
        }]
}
```

当 scene_key 为 recall 时，请求体应如下所示：
```json

{
  "scene_key": "recall",
  "scene_value":"2c76eea2-83b6-11ef-b482-acde48001122",
  "context":{"top_k":5, "prompt":"942acd7e33b54ce28565f89f9b278044","model":"zhipu_proxyllm"},
  "evaluate_metrics":["RetrieverHitRateMetric", "RetrieverMRRMetric", "RetrieverSimilarityMetric"],
  "datasets": [{
            "query": "what awel talked about",
            "doc_name":"awel.md"
        }]
}
```

#### 响应体
返回 <a href="#the-evaluation-object">评估对象</a> 列表


### 评估请求对象

________
<b>scene_key</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

评估的场景类型，例如支持 app、recall

--------
<b>scene_value</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

评估的场景值，例如 app id（当 scene_key 为 app 时），space id（当 scene_key 为 recall 时）

--------
<b>context</b> <font color="gray"> object </font> <font color="red"> 必填 </font>

评估的上下文
- top_k <font color="gray"> int </font> <font color="red"> 必填 </font>
- prompt <font color="gray"> string </font> 提示词代码
- model <font color="gray"> string </font> LLM 模型名称

--------
evaluate_metrics <font color="gray"> array </font> <font color="red"> 必填 </font>

评估的评估指标，
例如
- <b>AnswerRelevancyMetric</b>：答案相关性指标（当 scene_key 为 app 时）
- <b>RetrieverHitRateMetric</b>：命中率计算在 top-k 检索文档中找到正确答案的查询比例。简单来说，就是衡量系统在前几次猜测中答对的频率。（当 scene_key 为 recall 时）
- <b>RetrieverMRRMetric</b>：对于每个查询，MRR 通过查看排名最高的相关文档的位置来评估系统的准确性。具体来说，它是所有查询中这些排名的倒数平均值。因此，如果第一个相关文档是排名第一的结果，则倒数排名为 1；如果是第二名，则倒数排名为 1/2，依此类推。（当 scene_key 为 recall 时）
- <b>RetrieverSimilarityMetric</b>：嵌入相似度指标（当 scene_key 为 recall 时）

--------
datasets <font color="gray"> array </font> <font color="red"> 必填 </font>


评估的数据集


--------


### 评估结果

________
<b>prediction</b> <font color="gray">string</font>

预测结果
________
<b>contexts</b> <font color="gray">string</font>

RAG 检索块的上下文
________
<b>score</b> <font color="gray">float</font>

预测的得分
________
<b>passing</b> <font color="gray">bool</font>

预测是否通过
________
<b>metric_name</b> <font color="gray">string</font>

评估的指标名称
________
<b>prediction_cost</b> <font color="gray">int</font>

评估的预测成本
________
<b>query</b> <font color="gray">string</font>

评估的查询
________
<b>raw_dataset</b> <font color="gray">object</font>

评估的原始数据集
________
<b>feedback</b> <font color="gray">string</font>

LLM 评估的反馈
________
