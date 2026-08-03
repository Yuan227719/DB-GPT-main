# code_interpreter

## 概述

`code_interpreter` 执行任意 Python 代码，并返回标准输出/标准错误以及生成的产物。

它是数据分析、计算、数据框操作和图表生成的主要工具。

## 参数

```json
{
  "code": "python code string"
}
```

## 功能说明

- 在子进程中运行 Python 代码
- 提供常用的分析包，如 `pandas` 和 `numpy`
- 捕获文本输出和生成的图片
- 保留生成的图片引用，供后续 HTML 渲染使用

## 使用场景

- CSV / Excel / 数据框分析
- 指标计算
- 图表生成
- 基于 Python 的预处理和转换

## 示例

```python
import pandas as pd

df = pd.read_csv(FILE_PATH)
print(df.head())
print(df.describe())
```

## 注意事项

- 每次调用相互独立
- 变量不会在多次调用之间持久化
- 始终在同一个调用内加载所需的数据
- 如果希望结果出现在工具输出中，请使用 `print()`
- 不要将其作为最终的 HTML 交付步骤
