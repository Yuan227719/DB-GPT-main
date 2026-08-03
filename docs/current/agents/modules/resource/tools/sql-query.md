# sql_query

## 概述

`sql_query` 对所选数据库执行只读 SQL 查询。

在进行更深入的分析之前，这是检查结构化数据最快速的方式。

## 参数

```json
{
  "sql": "SELECT statement"
}
```

## 功能说明

- 执行安全的只读 SQL
- 将结果格式化为 markdown 表格输出
- 将大量结果截断为前 50 行

## 使用场景

- 检查 schema 和样本行
- 从结构化数据中回答业务问题
- 在 Python 分析之前获取数据

## 示例

```json
{
  "sql": "SELECT product_category, SUM(revenue) AS total_revenue FROM sales GROUP BY product_category ORDER BY total_revenue DESC"
}
```

## 注意事项

- 只允许读操作
- `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER` 和 `CREATE` 等语句被禁止
- 仅用于数据检索，不可用于数据修改
