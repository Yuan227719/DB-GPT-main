# load_skill

## 概述

`load_skill` 通过技能名称和文件路径加载技能的内容，通常是从 `SKILL.md` 中加载指令。

当 Agent 应遵循封装好的工作流而不是临时编排整个执行过程时，请使用此工具。

## 参数

```json
{
  "skill_name": "skill name",
  "file_path": "skill file path"
}
```

## 功能说明

- 从注册中心解析技能
- 读取技能指令或提示词模板
- 将加载的工作流内容返回给 Agent

## 使用场景

- 任务与可复用的技能匹配
- 技能中包含精心设计的业务逻辑
- 工作流应在执行开始前进行标准化

## 示例

```json
{
  "skill_name": "financial-report-analyzer",
  "file_path": "skills/financial-report-analyzer/SKILL.md"
}
```

## 注意事项

- `load_skill` 仅加载指令，并不执行工作流本身
- 加载完成后，Agent 应遵循技能所要求的工具和步骤
