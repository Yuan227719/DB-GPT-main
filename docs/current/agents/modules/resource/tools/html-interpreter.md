# html_interpreter

## 概述

`html_interpreter` 将 HTML 渲染为交互式网页报告。

它是用于网页、HTML 报告、仪表盘以及基于技能的报表交付的最终呈现工具。

## 参数

### 直接 HTML 模式

```json
{
  "html": "<html>...</html>",
  "title": "Report"
}
```

### 模板模式

```json
{
  "template_path": "skill/templates/report_template.html",
  "data": {
    "KEY": "value"
  }
}
```

### 文件模式

```json
{
  "file_path": "/absolute/path/to/file.html",
  "title": "Report"
}
```

## 功能说明

- 直接渲染完整的 HTML
- 支持模板占位符替换
- 可以将生成的数据和图片合并到报告中
- 可以从现有的 HTML 文件中渲染

## 使用场景

- 最终 HTML 报告生成
- 交互式网页交付
- 基于技能的模板化报告输出

## 示例

```json
{
  "template_path": "financial-report-analyzer/templates/report_template.html",
  "data": {
    "REPORT_TITLE": "Q2 Financial Review",
    "EXEC_SUMMARY": "Revenue increased while gross margin remained stable."
  }
}
```

## 注意事项

- 这应该是 HTML 风格输出的最终渲染步骤
- 不要仅依赖 `code_interpreter` 来完成最终的 HTML 交付
- 模板模式在基于技能的报表工作流中特别有用
