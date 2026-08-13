# SparkSQL → TrinoSQL 转换参考（现算必读）

> 背景：DolphinScheduler 建表口径是 **SparkSQL**；agent 的 `sql_query` 查的是 **Kyuubi/Trino**（数据面）。
> 凡"现算"（表里没有的周期/自定义口径），**必须把 SparkSQL 转成 TrinoSQL 再跑**，不能直接抄 Dolphin 的 SQL。

## 高频函数映射（本技能口径里实际用到的）

| SparkSQL | TrinoSQL | 说明 |
|---|---|---|
| `get_json_object(j, '$.k')` | `json_extract_scalar(j, '$.k')` | JSON 取标量；取对象用 `json_extract` |
| `to_json(named_struct('a',x,'b',y))` | `json_format(cast(map(array['a','b'], array[x,y]) as json))` | 构造 JSON；Trino 的 `row` 无字段名，用 `map` |
| `collect_set(x)` | `array_agg(distinct x)` | 去重收集 |
| `collect_list(x)` | `array_agg(x)` | 收集 |
| `filter(arr, v -> cond)` | `filter(arr, v -> cond)` | 均支持 lambda；先 `array_agg` 转数组再 filter |
| `posexplode(arr)` | `unnest(arr) with ordinality as t(x, idx)` | 行展开带序号 |
| `explode(arr)` | `unnest(arr)` | 行展开 |
| `split(str, ',')` | `split(str, ',')` | 均可 |
| `concat_ws(sep, ...)` | `concat_ws(sep, ...)` | 均可 |
| `concat(...)` | `concat(...)` | 均可 |
| `trunc(d, 'week')` / `trunc(d, 'month')` | `date_trunc('week', d)` / `date_trunc('month', d)` | Spark `trunc()` → Trino `date_trunc()` |
| `date_add(d, n)` | `date_add('day', n, d)` | **参数顺序不同**（Trino 多 'day'） |
| `add_months(d, -5)` | `date_add('month', -5, d)` | Trino 无 add_months |
| `weekofyear(d)` | `week(d)` | Trino 返回 ISO 周号 |
| `month(d)` | `month(d)` | 均可 |
| `approx_percentile(col, p)` | `approx_percentile(col, p)` | 均可（p 为 0~1） |
| `md5(...)` | `md5(...)` | 均可 |
| `if(cond, a, b)` | `if(cond, a, b)` | 均可 |
| `coalesce(...)` | `coalesce(...)` | 均可 |
| `cast(x as int)` | `cast(x as integer)` | Trino 用 `integer` |
| `cast(x as double)` | `cast(x as double)` | 均可 |
| `regexp_replace(s, p, r)` | `regexp_replace(s, p, r)` | 均可 |
| `count(case when c then 1 end)` | `count(case when c then 1 end)` 或 `count(*) filter (where c)` | 均可 |
| `stddev_pop(x)` | `stddev_pop(x)` | 均可 |
| `row_number() over(...)` | `row_number() over(...)` | 均可 |
| `date_format(d, 'yyyy')` | `date_format(d, '%Y')` 或 `format_datetime(d, 'yyyy')` | 格式符不同 |

## 本技能口径里的关键转换样例

**① 周标识 `year_week_number`**
```sql
-- Spark:
concat(year(date_add(trunc(dt, 'week'), 3)), '年第', weekofyear(dt), '周')
-- Trino:
concat(cast(year(date_add('day', 3, date_trunc('week', dt))) as varchar),
       '年第', cast(week(dt) as varchar), '周')
```

**② 周时间窗**
```sql
-- Spark:
dt BETWEEN date_trunc('week', '${etl_dt}') AND '${etl_dt}'
-- Trino:
dt BETWEEN date_trunc('week', cast('{日期}' as timestamp)) AND cast('{日期}' as timestamp)
```

**③ 构造 JSON（dimension_json / indicator_value）**
```sql
-- Spark:
to_json(named_struct('q1', q1, 'median', median, 'q3', q3))
-- Trino:
json_format(cast(map(array['q1','median','q3'], array[cast(q1 as varchar), cast(median as varchar), cast(q3 as varchar)]) as json))
```

**④ 读 JSON 字段（查表取值）**
```sql
-- Spark: get_json_object(indicator_value, '$.median')
-- Trino: json_extract_scalar(indicator_value, '$.median')
```

**⑤ 数组展开（plane 级 ECC 拆行）**
```sql
-- Spark: posexplode(split(ecc_value_plane, ','))
-- Trino: CROSS JOIN UNNEST(split(ecc_value_plane, ',')) WITH ORDINALITY AS t(ecc_value, idx)
```

## ⚠️ 不可用 / 需特殊处理的（Spark 专有）
| 函数 | 问题 | 处理 |
|---|---|---|
| `udf_db.chi_square_inv(0.6, 2f+2)`（DPPM 用） | Spark UDF，Trino 无 | 用 **Wilson–Hilferty 正态近似**替代：`df·(1 − 2/(9df) + 0.253347·√(2/(9df)))³`（`df=2f+2`，`0.253347` 是 z_0.6）。具体 SQL 见 `DPPM-BIBB.md`；回答必须标注"近似值" |
| `spark_catalog.udf_db.*`（count_ecc_fast / group_ecc_by_plane 等） | Spark UDF | Trino 不可用，改用标准 SQL 等价或说明算不了 |
| `from_json(json, 'MAP<STRING, INT>')` | Spark 专有 | Trino 用 `cast(json as map(varchar, integer))` |
| `get_json_object`（嵌套） | 语法差异 | 用 `json_extract` / `json_extract_scalar` 链式 |
| `${if(len(...) == 0, ...)}` / `${REPLACE(...)}` | Dolphin 模板语法 | 已去掉（本技能文档里的 SQL 都是静态化后的） |

## 现算铁律
1. 动手写 `sql_query` 前，先想清楚是 Spark 语法还是 Trino 语法；Dolphin 抄来的 SQL **必是 Spark**。
2. 查表（`dws_indicator_d/w`、`ads_fa_fbc_cycle` 等已预计算表）不需要转，直接 `json_extract_scalar` 取值即可。
3. 只有"现算"（从明细表按算法重新聚合）才需要完整转换。
4. 遇到 Spark UDF（chi_square_inv 等）转不了就**如实说明**，不要编一个不存在的函数。
