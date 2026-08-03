# 快速开始基础 AWEL 工作流

## 安装

首先，安装 dbgpt 及必要的依赖：

```shell
pip install dbgpt --upgrade
pip install openai
```

创建一个 Python 文件 `simple_sdk_llm_example_dag.py` 并写入以下内容：

```python
import asyncio
from dbgpt.core.awel import DAG
from dbgpt.core.operators import (
    PromptBuilderOperator,
    RequestBuilderOperator,
)
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.model.operators import LLMOperator

with DAG("simple_sdk_llm_example_dag") as dag:
    prompt_task = PromptBuilderOperator(
        "Write a SQL of {dialect} to query all data of {table_name}."
    )
    model_pre_handle_task = RequestBuilderOperator(model="gpt-3.5-turbo")
    llm_task = LLMOperator(OpenAILLMClient())
    prompt_task >> model_pre_handle_task >> llm_task
    
output = asyncio.run(
    llm_task.call({
        "dialect": "MySQL", 
        "table_name": "users"
    }
))
print(output)
```

配置 OpenAI API 的环境变量：

```bash
export OPENAI_API_KEY=sk-xx
export OPENAI_API_BASE=https://xx:80/v1
```

运行 Python 文件：

```bash
python simple_sdk_llm_example_dag.py
```

输出将如下所示：
```plaintext
ModelOutput(text='SELECT * FROM users;', error_code=0, model_context=None, finish_reason=None, usage={'completion_tokens': 5, 'prompt_tokens': 19, 'total_tokens': 24}, metrics=None)
```

恭喜！您已经掌握了 AWEL 的基本用法。更多示例请参考 **[cookbook](/docs/awel/cookbook/)**。

我们建议您阅读 **[AWEL 教程](/docs/awel/tutorial/)** 以了解更多关于 AWEL 的内容。
