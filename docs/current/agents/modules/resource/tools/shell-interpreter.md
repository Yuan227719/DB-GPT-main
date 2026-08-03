# shell_interpreter

## 概述

`shell_interpreter` 在沙箱环境中执行 shell / bash 命令。

它适用于命令行工作流，而非数据分析逻辑。

## 参数

```json
{
  "code": "shell command(s)"
}
```

## 功能说明

- 运行 bash / shell 命令
- 强制沙箱隔离
- 对危险模式应用安全检查
- 限制内存和执行时间

## 运行时特性

- 内存限制：**256MB**
- 超时时间：**30s**
- 多次调用之间不保持持久化的 shell 状态

## 使用场景

- 检查文件和目录
- 运行 CLI 工具，如 `ls`、`grep`、`curl`、`git`、`pip`
- 执行 shell 级别的环境任务

## 示例

```json
{
  "code": "ls -la"
}
```

## 注意事项

- Python 分析请改用 `code_interpreter`
- 最终渲染输出请使用 `html_interpreter`
- 如果某个技能明确要求了其他执行路径，请遵循该技能的指令
