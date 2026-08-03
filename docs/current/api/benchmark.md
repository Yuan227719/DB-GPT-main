# 数据集基准测试

开始使用基准测试 API


### 创建数据集基准测试任务

```python
POST /api/v2/serve/evaluate/execute_benchmark_task
```

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X POST "http://localhost:5670/api/v2/serve/evaluate/execute_benchmark_task" \
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json" \
-d '{
    "scene_value": "Falcon_benchmark_01",
    "model_list": ["DeepSeek-V3.1", "Qwen3-235B-A22B"]
}'

```

#### 基准测试请求对象

________
<b>scene_key</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

评估的场景类型，例如支持 app、recall

--------
<b>scene_value</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

基准测试的场景值，例如标注评估任务名称

--------
<b>model_list</b> <font color="gray"> object </font> <font color="red"> 必填 </font>

将要执行的基准测试模型名称列表，例如 ["DeepSeek-V3.1","Qwen3-235B-A22B"]
注意：需要输入在 db-gpt 平台上配置的模型名称。

--------
<b>temperature</b> <font color="gray"> float </font>

LLM 模型的温度参数，默认为 0.7

--------
<b>max_tokens</b> <font color="gray"> int </font>

LLM 模型的最大 token 数，默认为 None

--------


#### 基准测试结果

________
<b>status</b> <font color="gray">string</font>

基准测试状态，例如 success、failed、running
________


### 查询基准测试任务列表

```python
GET /api/v2/serve/evaluate/benchmark_task_list
```

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X GET "http://localhost:5670/api/v2/serve/evaluate/benchmark_task_list?page=1&page_size=20" \ 
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json"

```

#### 基准测试任务列表请求对象

________
<b>page</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

查询任务列表页码，默认为 1

--------
<b>page_size</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

查询任务列表每页大小，默认为 20

--------


#### 基准测试任务列表结果

```json
{
    "success": true,
    "err_code": null,
    "err_msg": null,
    "data": {
        "items": [
            {
                "evaluate_code": "1ec15dcbf5d54124bd5a5d23992af35d",
                "scene_key": "dataset",
                "scene_value": "local_benchmark_task_for_Qwen",
                "datasets_name": "Falcon评测集",
                "input_file_path": "2025_07_27_public_500_standard_benchmark_question_list.xlsx",
                "output_file_path": "/DB-GPT/pilot/benchmark_meta_data/result/1ec15dcbf5d54124bd5a5d23992af35d/202510201650_multi_round_benchmark_result.xlsx",
                "model_list": [
                    "Qwen3-Coder-480B-A35B-Instruct"
                ],
                "context": {
                    "benchmark_config": "{\"file_parse_type\":\"EXCEL\", \"format_type\":\"TEXT\", \"content_type\":\"SQL\", \"benchmark_mode_type\":\"EXECUTE\", \"scene_key\":\"dataset\", \"temperature\":0.6, \"max_tokens\":6000}"
                },
                "user_name": null,
                "user_id": null,
                "sys_code": "benchmark_system",
                "parallel_num": 1,
                "state": "running",
                "temperature": null,
                "max_tokens": null,
                "log_info": null,
                "gmt_create": "2025-10-20 16:50:46",
                "gmt_modified": "2025-10-20 16:50:46",
                "cost_time": null,
                "round_time": 1
            }
        ],
        "total_count": 80,
        "total_pages": 4,
        "page": 1,
        "page_size": 20
    }
}
```

________
<b>evaluate_code</b> <font color="gray">string</font>

基准测试任务的唯一编码
________
<b>scene_key</b> <font color="gray">string</font>

基准测试任务场景，例如 dataset
________
<b>scene_value</b> <font color="gray">string</font>

基准测试任务名称
________
<b>datasets_name</b> <font color="gray">string</font>

基准测试执行的数据集名称
________
<b>input_file_path</b> <font color="gray">string</font>

基准测试数据集文件路径
________
<b>output_file_path</b> <font color="gray">string</font>

基准测试执行结果文件路径
________
<b>model_list</b> <font color="gray">object</font>

基准测试执行的模型列表
________
<b>context</b> <font color="gray">object</font>

基准测试任务上下文
________
<b>user_name</b> <font color="gray">string</font>

基准测试任务用户名
________
<b>user_id</b> <font color="gray">string</font>

基准测试任务用户 ID
________
<b>sys_code</b> <font color="gray">string</font>

基准测试任务系统代码，例如 benchmark_system
________
<b>parallel_num</b> <font color="gray">int</font>

基准测试任务执行并行数
________
<b>state</b> <font color="gray">string</font>

基准测试任务状态，例如 running、success、failed
________
<b>temperature</b> <font color="gray">float</font>

基准测试任务的 LLM 温度参数
________
<b>max_tokens</b> <font color="gray">int</font>

基准测试任务的 LLM 最大 token 数
________
<b>log_info</b>  <font color="gray">int</font>

如果基准测试任务执行出错，将显示错误信息
________
<b>gmt_create</b> <font color="gray">string</font>

任务创建时间
________
<b>gmt_modified</b> <font color="gray">string</font>

任务完成时间
________
<b>cost_time</b> <font color="gray">int</font>

基准测试任务耗时
________
<b>round_time</b> <font color="gray">int</font>

基准测试任务执行轮次
________


### 基准测试对比结果

```python
GET /api/v2/serve/evaluate/benchmark/result/{evaluate_code}
```

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X GET "http://localhost:5670/api/v2/serve/evaluate/benchmark/result/{evaluate_code}" \
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json"

```

#### 基准测试请求对象

________
<b>evaluate_code</b> <font color="gray"> string </font> <font color="red"> 必填 </font>

基准测试任务的唯一编码

--------

#### 基准测试结果

```json
{
    "success": true,
    "err_code": null,
    "err_msg": null,
    "data": {
        "evaluate_code": "c827a274b4084f5dbce4c630f5267239",
        "scene_value": "Falcon评测集_benchmark",
        "summaries": [
            {
                "roundId": 1,
                "llmCode": "Qwen3-Coder-480B-A35B-Instruct",
                "right": 136,
                "wrong": 269,
                "failed": 95,
                "exception": 0,
                "accuracy": 0.272,
                "execRate": 0.81,
                "outputPath": "/DB-GPT/pilot/benchmark_meta_data/result/c827a274b4084f5dbce4c630f5267239/202510181449_multi_round_benchmark_result.xlsx"
            }
        ]
    }
}
```

________
<b>roundId</b> <font color="gray">string</font>

基准测试任务执行轮次
________
<b>llmCode</b> <font color="gray">string</font>

基准测试任务执行的模型名称
________
<b>right</b> <font color="gray">int</font>
基准测试任务执行正确的题目数量
________
<b>wrong</b> <font color="gray">int</font>
基准测试任务执行错误的题目数量
________
<b>failed</b> <font color="gray">int</font>
基准测试任务执行失败的题目数量
________
<b>exception</b> <font color="gray">int</font>
基准测试任务执行异常的题目数量
________
<b>accuracy</b> <font color="gray">float</font>
基准测试任务题目列表执行准确率
________
<b>execRate</b> <font color="gray">float</font>
基准测试任务题目列表可执行率
________
<b>outputPath</b> <font color="gray">string</font>
基准测试任务执行结果输出文件路径
________
