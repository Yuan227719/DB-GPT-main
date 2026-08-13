# DPPM / BIBB 口径

> 来源：DolphinScheduler `sub_st_embed_ods_to_ads` → `to_dws_indicator_d_bibb`（日表）与 `周报_WEEK_通用` → `周dppm`（周表）。
> 2026-08-11 更新：日表去重逻辑由"dws_fa_ecc_cycle 内 row_number"改为"基于 dim_base_sn_di 的最新 efuse_id 记录"。

## 业务定义
- **BIBB 坏块数**：单颗 SN 在某个 cycle 下的坏块分类计数（FBB/PSF/ESF/UECC/GBB/HECC/BB_Skip/Read_empty/total）。
- **DPPM（失效 DPPM）**：周级"失效样品百万分率"告警指标，**只保留超阈值异常**（周表存的不是全量 DPPM）。

## 日表 `dws_indicator_d`（`{flash_pn}_bibb_cnt_cycle`）
**算法**：
1. 源：`st_embed.dws_fa_ecc_cycle`（cycle 级坏块统计）LEFT JOIN `dim_base_project`
   - 关联键同 FBB（flash/item_control/flash_pn/software_information/pn）
   - `max_bibb_num` 阈值来自 `dim_base_project`，为空取 `999999999`
2. 过滤：`subitem_name in ('ECC_SLC','ECC_TLC','ECC_QLC')`，`test_number = '0'`，`station in ('MT1','MT1R')`
3. 每 SN 只留最新一次（**2026-08-11 新逻辑**）：先在 `dim_base_sn_di` 里取每个 (wo, efuse_id) 的最新记录
   （`row_number() over(partition by wo, efuse_id order by time_end desc) rn`，取 `rn=1` 的 guid），
   再用 `result_guid in (最新 guid 集合)` 过滤 `dws_fa_ecc_cycle` 数据。
   （旧逻辑：在 `dws_fa_ecc_cycle` 内按 `(flash_pn, wo, efuse_id)` 直接 `row_number() ... rn=1` 取最新，已废弃。）
4. `indicator_value` = JSON `{fbb_cnt, psf_cnt, esf_cnt, uecc_cnt, gbb_cnt, hecc_cnt, bb_skip_cnt, read_empty_cnt, total_cnt}`
5. `dimension_json` = `{cycle_number, max_bibb_num, efuse_id}`

**直接查**：
```sql
SELECT wo, flash_pn, dut_sn, indicator_value,
       get_json_object(dimension_json,'$.max_bibb_num') AS max_bibb_num
FROM st_embed.dws_indicator_d
WHERE indicator_name = '{flash_pn}_bibb_cnt_cycle'
  AND dt BETWEEN '{开始}' AND '{结束}'
```

## 周表 `dws_indicator_w`（`{flash_pn}_week_dppm`）
**算法**：
1. 源：`dws_indicator_d`，`indicator_name like '%_bibb_cnt_cycle'`，`test_result = 'fail'`，
   `error_code != '91'` 且 `error_code != '93'`，周时间窗
2. 失效数：`fails = sum(sn_cnt)`，`sn_cnt = count(distinct dut_sn)`（按 data_source/product_type/wo/station/flash_pn/flash/item_control/pn/software_information/project 分组）
3. 分母：`ss = sum(amount)`（关联 `dim_base_wo_di` 的工单 amount）
4. **DPPM 公式**：`dppm = udf_db.chi_square_inv(0.6, 2*fails+2) / (2*ss) * 1000000`
5. **只保留 `dppm > dppm_threshold` 的记录**（异常告警），阈值默认按 flash_pn：Solidigm N38B=500、SSV7=500、SSV8=400、N38B PSLC=1000、WTS=400、Hynix 3DV7=400、Hynix 3DV7(PGD)=400；有配置取 `dim_base_project.dppm_threshold`
6. `indicator_value` = JSON `{fails, ss, dppm}`；`dimension_json` = `''`

**直接查**：
```sql
SELECT year_week_number, wo, flash_pn, project, station, indicator_value
FROM st_embed.dws_indicator_w
WHERE indicator_name = '{flash_pn}_week_dppm'
  AND year_week_number = '{周}'
```
`indicator_value` 用 `get_json_object(indicator_value,'$.fails')` / `'$.ss'` / `'$.dppm'`。

## 现算（表里没有的周期）
把周时间窗换成目标周期，从 `dws_indicator_d`（bibb_cnt_cycle + fail + 过滤 error_code）现算：
```sql
SELECT wo, flash_pn, project,
       COUNT(DISTINCT dut_sn) AS fails,
       MAX(b.amount) AS ss,
       (udf_db.chi_square_inv(0.6, 2*COUNT(DISTINCT dut_sn)+2) / (2*MAX(b.amount))) * 1000000 AS dppm
FROM st_embed.dws_indicator_d a
LEFT JOIN st_embed.dim_base_wo_di b ON a.wo = b.wo
WHERE indicator_name LIKE '%_bibb_cnt_cycle'
  AND test_result = 'fail' AND error_code != '91' AND error_code != '93'
  AND dt BETWEEN '{开始}' AND '{结束}'
GROUP BY wo, flash_pn, project
```
> **⚠️ Trino 转换**：这是 SparkSQL。`udf_db.chi_square_inv` 是 **Spark UDF，Trino 里没有**。
> 现算时 `fails/ss` 部分可直接转（`COUNT(DISTINCT dut_sn)`、`MAX(amount)`），但 **DPPM 的卡方精确值需近似**。

### `udf_db.chi_square_inv` 是什么
`chi_square_inv(0.6, 2*fails+2)` = 自由度 `k=2*fails+2` 的卡方分布，在累积概率 **0.6** 处的**逆累积分布分位数**（`ChiSquaredDistribution.inverseCumulativeProbability(0.6)`）。本质是失效率的卡方置信上界（60% 置信）折算成 DPPM。

### Trino 近似：Wilson–Hilferty 正态近似（`k` 较大时误差很小）
```
χ²_p(k) ≈ k · (1 − 2/(9k) + z_p·√(2/(9k)))³
```
- `k = 2*fails + 2`，`p = 0.6`，标准正态 60% 分位 `z_0.6 = 0.253347`（常数，可直接硬编码）
```sql
-- 现算 DPPM（Trino，近似）：
WITH base AS (
    SELECT wo, flash_pn, project,
           COUNT(DISTINCT dut_sn) AS fails,
           MAX(b.amount) AS ss
    FROM st_embed.dws_indicator_d a
    LEFT JOIN st_embed.dim_base_wo_di b ON a.wo = b.wo
    WHERE indicator_name LIKE '%_bibb_cnt_cycle'
      AND test_result = 'fail' AND error_code != '91' AND error_code != '93'
      AND dt BETWEEN '{开始}' AND '{结束}'
    GROUP BY wo, flash_pn, project
)
SELECT wo, flash_pn, project, fails, ss,
       (df * power(1 - 2.0/(9.0*df) + 0.253347 * sqrt(2.0/(9.0*df)), 3) / (2.0*ss)) * 1000000 AS dppm_approx
FROM (SELECT *, 2.0*fails + 2 AS df FROM base)
```
> 近似值是**近似**，与精确卡方分位数有小偏差；**回答时必须标注"该值为 Wilson–Hilferty 近似"**。若用户要精确值，需在 Spark 环境跑或查周表已有 `_week_dppm`（只存超阈值异常）。

## 注意/陷阱
- **周表 DPPM 只存超阈值异常**，查"某周 DPPM"得到的是超阈值的工单，不是全量；要全量按"现算"逻辑。
- **error_code ≠ 91/93 是硬过滤**（91/93 为特定错误码，排除）；`test_result='fail'` 才计入失效。
- `fails` 是**去重 SN 数**，不是坏块数。
- DPPM 阈值按 flash_pn 不同，别用统一阈值。
