# FBB 比率口径

> 来源：DolphinScheduler `sub_st_embed_ods_to_ads` → `to_dws_indicator_d_fbb`（日表）与 `周报_WEEK_通用` → `fbb 指标-DWS层`（周表）（2026-08-11）。

## 业务定义
FBB 比率 = plane 级"工厂坏块（Factory Bad Block）"数量 / plane 块数，反映整片坏块密度。
- 日表：每 plane 一个样本（SN 粒度），`indicator_value = fbb_cnt / block_size`
- 周表：对本周所有 plane 样本做分布统计（q1/median/q3/上界/下界/异常值）

## 日表 `dws_indicator_d`（`{flash_pn}_fbb_ratio_sn`）
**算法**：
1. 源：`st_embed.dws_fa_ecc_plane`（plane 级 ECC 分类计数）LEFT JOIN `st_embed.dim_base_project`
   - 关联键：`flash`、`item_control like concat('%',b.item_control,'%')`、`flash_pn`、`software_information`、`pn like concat('%',b.pn,'%')`
2. 过滤：`subitem_name in ('ECC_SLC','ECC_TLC','ECC_QLC')`
3. 每 plane：`indicator_value = fbb_cnt / block_size`（block_size 取 int）
4. `dimension_json` 记录 `{die_number, cycle_number, plane_number, fbb_ratio, efuse_id}`
   - `fbb_ratio` 来自 `dim_base_project`（该 flash_pn 的坏块比率阈值）；为空时用默认值：Solidigm N38B=0.07、SSV7=0.1、SSV8=0.11、N38B PSLC=0.5、WTS=0.05、Hynix 3DV7=0.045、Hynix 3DV7(PGD)=0.045
5. `year_week_number` 按 `date_add(trunc(dt,'week'),3)` 归周

**直接查**：
```sql
SELECT year_week_number, wo, flash_pn, project, indicator_value,
       get_json_object(dimension_json,'$.fbb_ratio') AS fbb_ratio
FROM st_embed.dws_indicator_d
WHERE indicator_name = '{flash_pn}_fbb_ratio_sn'
  AND dt BETWEEN '{开始}' AND '{结束}'
```
**异常标记** `{flash_pn}_fbb_ratio_sn_abnormal`：日表里 `indicator_value >= fbb_ratio`（阈值）的 plane 记为异常（flag=1），用于 FBB 异常工单排查。

## 周表 `dws_indicator_w`（`{flash_pn}_fbb_ratio_wo`）——即 **FBB 箱线**
**算法**（对本周 `%_fbb_ratio_sn` 样本按维度分组）：
1. 源：`dws_indicator_d`，`indicator_name like '%_fbb_ratio_sn'`，`dt BETWEEN date_trunc('week','${etl_dt}') AND '${etl_dt}'`
2. 分组维度：`year_week_number, data_source, project, product_type, wo, flash, flash_pn, fbb_ratio, item_control, software_information, pn`
3. 统计：`q1/median/q3 = approx_percentile(fbb, 0.25/0.5/0.75)`，`iqr = q3-q1`，`upper = q3+1.5*iqr`，`lower = q1-1.5*iqr`
4. 异常值：`outliers = filter(collect_set(fbb), v -> v > upper or v < lower)`
5. 非异常极值：`max_fbb/min_fbb` 限定在 `[lower, upper]` 内
6. `indicator_value` 存 JSON `{q1, median, q3, upper, lower, outliers}`；`dimension_json` 存 `{fbb_ratio}`

**直接查**：
```sql
SELECT year_week_number, wo, flash_pn, project, indicator_value
FROM st_embed.dws_indicator_w
WHERE indicator_name = '{flash_pn}_fbb_ratio_wo'
  AND year_week_number = '{周}'
```
`indicator_value` 用 `get_json_object(indicator_value,'$.median')` 等取分位数。

## 现算（表里没有的周期，如"月"）
按日表算法把时间窗改成目标周期（`date_trunc('month',...)` 或自定义 `BETWEEN`），从 `dws_fa_ecc_plane` × `dim_base_project` 现算：
```sql
SELECT project, flash_pn, wo,
       SUM(fbb_cnt)/SUM(block_size) AS fbb_ratio_avg
FROM st_embed.dws_fa_ecc_plane
WHERE subitem_name IN ('ECC_SLC','ECC_TLC','ECC_QLC')
  AND dt BETWEEN '{开始}' AND '{结束}'
GROUP BY project, flash_pn, wo
```

## 注意/陷阱
- **FBB 是坏块比率阈值/默认值按 flash_pn 分**，别用错默认值（见日表第 4 步）。
- **周表 `_fbb_ratio_wo` 就是 FBB 箱线**：q1/median/q3/upper/lower/outliers 即箱线须线和离群点；画 FBB 箱线直接查它（分位数用 `approx_percentile`）。
- 周表是**分布统计**（分位数/异常值），不是简单平均，输出"中位数/上界/下界/异常工单"而非单个均值。
- `fbb_ratio_sn` 是 plane 级样本，一个 SN 有多个 plane；统计异常工单时注意去重口径（按 wo/flash_pn 聚合）。
