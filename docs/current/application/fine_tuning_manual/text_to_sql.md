# Text2SQL 微调
我们已将 Text2SQL 相关的微调代码拆分到 `DB-GPT-Hub` 子项目中，您也可以直接查看源代码。

## 微调流水线

Text2SQL 流水线主要包括以下过程：
- [构建环境](#构建环境)
- [数据处理](#数据处理)
- [模型训练](#模型训练)
- [模型合并](#模型合并)
- [模型预测](#模型预测)
- [模型评估](#模型评估)


## 构建环境
我们建议使用 conda 虚拟环境来构建 Text2SQL 微调环境

```python
git clone https://github.com/eosphoros-ai/DB-GPT-Hub.git
cd DB-GPT-Hub
conda create -n dbgpt_hub python=3.10 
conda activate dbgpt_hub
conda install -c conda-forge poetry>=1.4.0
poetry install
```

当前项目支持多种 LLM，可按需下载。在本教程中，我们使用 `CodeLlama-13b-Instruct-hf` 作为基础模型。该模型可以从 [HuggingFace](https://huggingface.co/) 和 [ModelScope](https://modelscope.cn/models) 等平台下载。以 HuggingFace 为例，下载命令如下：
```python
cd Your_model_dir
git lfs install
git clone git@hf.co:codellama/CodeLlama-13b-Instruct-hf
```

## 数据处理

### 数据收集
本教程的案例数据主要以 `Spider` 数据集为例：
- 简介：`Spider` 数据集被公认为业界难度最大的大规模跨域评估榜单。它包含 10,181 条自然语言问题和 5,693 条 SQL 语句，涉及 138 个不同领域的 200 多个数据库。
- 下载：[下载](https://drive.google.com/uc?export=download&id=1TqleXec_OykOYFREKKtschzY29dUcVAQ) 数据集到项目目录，位于 `dbgpt_hub/data/spider`。

### 数据处理
项目采用信息匹配生成方法进行数据准备，即结合表信息的 `SQL + 知识库` 生成方法。这种方法结合数据表信息，有助于更好地理解数据表的结构和关系，从而更好地生成符合需求的 SQL。

项目已将相关处理代码封装在对应脚本中。您可以直接一键运行脚本命令。生成的训练集 `example_text2sql_train.json` 和 `example_text2sql_dev.json` 将在 `dbgpt_hub/data/` 目录中获取。

```python
# 生成训练数据和开发（评估）数据
sh dbgpt_hub/scripts/gen_train_eval_data.sh
```
训练集中有 `8659` 条数据，开发集中有 `1034` 条数据。生成的训练集数据格式如下：
```json
{
  "db_id": "department_management",
  "instruction": "I want you to act as a SQL terminal in front of an example database, you need only to return the sql command to me.Below is an instruction that describes a task, Write a response that appropriately completes the request.\n\"\n##Instruction:\ndepartment_management contains tables such as department, head, management. Table department has columns such as Department_ID, Name, Creation, Ranking, Budget_in_Billions, Num_Employees. Department_ID is the primary key.\nTable head has columns such as head_ID, name, born_state, age. head_ID is the primary key.\nTable management has columns such as department_ID, head_ID, temporary_acting. department_ID is the primary key.\nThe head_ID of management is the foreign key of head_ID of head.\nThe department_ID of management is the foreign key of Department_ID of department.\n\n",
  "input": "###Input:\nHow many heads of the departments are older than 56 ?\n\n###Response:",
  "output": "SELECT count(*) FROM head WHERE age  >  56",
  "history": []
}
```

在 `dbgpt_hub/data/dataset_info.json` 中配置训练数据文件。json 文件中对应键的值默认为 `example_text2sql`。该值是需要传入后续训练脚本 train_sft 的参数 `--dataset` 的值。json 中的 `file_name` 值是训练集的文件名。


### 代码解读
数据处理的核心代码主要在 `dbgpt_hub/data_process/sql_data_process.py` 中。核心处理类是 `ProcessSqlData()`，核心处理函数是 `decode_json_file()`。

`decode_json_file()` 首先将 `Spider` 数据中的表信息处理为字典格式。`key` 和 `value` 分别是 `db_id` 及对应的 `table` 和 `column` 信息，格式如下：
```json
{
  "department_management": department_management contains tables such as department, head, management. Table department has columns such as Department_ID, Name, Creation, Ranking, Budget_in_Billions, Num_Employees. Department_ID is the primary key.\nTable head has columns such as head_ID, name, born_state, age. head_ID is the primary key.\nTable management has columns such as department_ID, head_ID, temporary_acting. department_ID is the primary key.\nThe head_ID of management is the foreign key of head_ID of head.\nThe department_ID of management is the foreign key of Department_ID of department.
}
```
然后将配置文件中 `INSTRUCTION_PROMPT` 的 `{}` 部分填入上述文本，形成最终的指令。`INSTRUCTION_PROMPT` 如下：
```json
INSTRUCTION_PROMPT = "I want you to act as a SQL terminal in front of an example database, you need only to return the sql command to me.Below is an instruction that describes a task, Write a response that appropriately completes the request.\n ##Instruction:\n{}\n"
```

最后，将训练集和验证集中每个 `db_id` 对应的问题和查询处理成模型 SFT 训练所需的格式，即上述数据处理代码执行部分所示的数据格式。


:::info 注意
如果您想自行收集更多数据进行训练，可以根据上述逻辑使用本项目的相关代码进行处理。
:::


## 模型训练
为简单起见，本复现教程以 LoRA 微调为例直接运行，但项目微调不仅支持 `LoRA`，还支持 `QLoRA` 和 [deepspeed](https://github.com/microsoft/DeepSpeed) 加速。训练脚本 `dbgpt_hub/scripts/train_sft.sh` 的详细参数如下：

```json
CUDA_VISIBLE_DEVICES=0 python dbgpt_hub/train/sft_train.py \
    --model_name_or_path Your_download_CodeLlama-13b-Instruct-hf_path \
    --do_train \
    --dataset example_text2sql_train \
    --max_source_length 2048 \
    --max_target_length 512 \
    --finetuning_type lora \
    --lora_target q_proj,v_proj \
    --template llama2 \
    --lora_rank 64 \
    --lora_alpha 32 \
    --output_dir dbgpt_hub/output/adapter/code_llama-13b-2048_epoch8_lora \
    --overwrite_cache \
    --overwrite_output_dir \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 16 \
    --lr_scheduler_type cosine_with_restarts \
    --logging_steps 50 \
    --save_steps 2000 \
    --learning_rate 2e-4 \
    --num_train_epochs 8 \
    --plot_loss \
    --bf16
```

train_sft.sh 中关键参数及含义介绍：
- `model_name_or_path`：使用的 LLM 模型路径。
- `dataset`：训练数据集的配置名称，对应 `dbgpt_hub/data/dataset_info.json` 中的外层键值，如 `example_text2sql`。
- `max_source_length`：输入模型的文本长度。本教程的效果参数为 `2048`，是多次实验分析后的最优长度。
- `max_target_length`：输出模型的 SQL 内容长度，设置为 `512`。
- `template`：项目中针对不同模型微调的 lora 部分设置。对于 Llama2 系列模型，设置为 `llama2`。
- `lora_target`：LoRA 微调时的网络参数变化部分。
- `finetuning_type`：微调类型，可选值为 `[ptuning, lora, freeze, full]` 等。
- `lora_rank`：LoRA 微调中的秩大小。
- `lora_alpha`：LoRA 微调中的缩放因子。
- `output_dir`：SFT 微调时 Peft 模块输出的路径。默认设置在 `dbgpt_hub/output/adapter/` 路径下。
- `per_device_train_batch_size`：每个 GPU 上的训练样本批次。如果计算资源支持，可以设大。默认为 `1`。
- `gradient_accumulation_steps`：梯度更新的累积步数。
- `lr_scheduler_type`：学习率类型。
- `logging_steps`：日志保存的步数间隔。
- `save_steps`：模型保存 ckpt 的步数大小。
- `num_train_epochs`：训练数据的轮数。
- `learning_rate`：学习率，推荐学习率为 `2e-4`。

如果您想基于 `QLoRA` 训练，可以在脚本中添加参数 quantization_bit 表示是否量化。值为 `[4 or 8]` 时启用量化。
如果您想微调不同的 LLM，不同模型对应的关键参数 `lora_target` 和 `template` 可参考项目 `README.md` 中的相关内容进行更改。

## 模型合并


## 模型预测
模型训练完成后，要预测训练好的模型，可以直接运行项目脚本目录中的 `predict_sft.sh`。

预测运行命令：
```python
sh ./dbgpt_hub/scripts/predict_sft.sh
```

在项目目录 `./dbgpt_hub/output/pred/` 中，该文件路径是模型预测结果的默认输出位置（如果不存在，需要创建）。本教程 `predict_sft.sh` 中的详细参数如下：
```python

echo " predict Start time: $(date)"
## predict
CUDA_VISIBLE_DEVICES=0 python dbgpt_hub/predict/predict.py \
    --model_name_or_path Your_download_CodeLlama-13b-Instruct-hf_path \
    --template llama2 \
    --finetuning_type lora \
    --checkpoint_dir Your_last_peft_checkpoint-4000  \
    --predicted_out_filename Your_model_pred.sql

echo "predict End time: $(date)"
```
参数 `--predicted_out_filename` 的值是模型预测的结果文件名，结果可在 `dbgpt_hub/output/pred` 目录中找到。


## 模型评估
评估模型在数据集上的效果，默认在 `Spider` 数据集上进行。运行以下命令：

```python
python dbgpt_hub/eval/evaluation.py --plug_value --input  Your_model_pred.sql
```

大模型生成的结果具有一定随机性，因为它们与 `temperature` 等参数密切相关（可在 `/dbgpt_hub/configs/model_args.py` 的 `GeneratingArguments` 中调整）。默认情况下，我们多次评估的执行准确率为 `0.789` 及以上。我们将部分实验和评估结果放在项目 `docs/eval_llm_result.md` 中，仅供参考。


`DB-GPT-Hub` 基于 `CodeLlama-13b-Instruct-hf` 的 LLM，使用 `LoRA` 在 `Spider` 训练集上微调了权重文件。该权重文件已发布。目前，在 `Spider` 评估集上实现了约 `0.789` 的执行准确率。权重文件 `CodeLlama-13b-sql-lora` 可在 [HuggingFace](https://huggingface.co/eosphoros) 上获取。


## 附录
本文的实验环境基于 `A100（40G）` 显卡服务器，总训练时间约 12 小时。如果您的机器资源不足，可以优先考虑减小参数 `gradient_accumulation_steps` 的值。此外，您可以考虑使用 `QLoRA` 进行微调（在训练脚本 `dbgpt_hub/scripts/train_sft.sh` 中添加 `--quantization_bit 4`）。根据我们的经验，`QLoRA` 在 `8` 个 epoch 时，结果与 `LoRA` 微调结果相差不大。
