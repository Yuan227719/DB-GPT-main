---
name: indicator-calc
description: 计算与解释半导体测试指标体系（st_embed 商规EMBED 库）的指标口径与算法。当用户询问各类指标时触发，覆盖 良率/工单良率/完结良率、测试工单/测试样品、DPPM/失效DPPM、FBB比率/坏块比率、坏块/BB/bb/FBB/GBB、ECC分布/工单ECC/ECC坏块、ECC箱线图/箱型图/FBC/批次箱线/多cycle箱线、温度、电流、burnin/烧录/老化、日报/周报指标、趋势，以及表里没有的时间周期（如月）指标计算。触发关键词包括 良率/DPPM/FBB/坏块/ECC/温度/电流/burnin/烧录/老化/月/工单/趋势/BB/bb/fbb/gbb/工单良率/完结良率/测试工单/测试样品/ECC分布/工单ECC/箱线图/箱型图/FBC/批次/多cycle/日报/周报/指标/失效。
---

# 半导体测试指标计算（indicator-calc）

本技能用于回答 st_embed 库的指标类问题：**给出清晰、可复现的指标算法**，而不是凭感觉猜测。
指标口径全部沉淀在两张预计算表里，算法权威来源是 DolphinScheduler 建表 SQL（已提炼成 references/ 下各口径文档）。

## 核心流程（必须遵守）

### 第一步：读口径文档（先读文档，再动手查数）
根据用户问的指标，用 `get_skill_resource` 读取对应口径文档：

| 指标 | 文档 |
|---|---|
| 良率 / 工单良率 / MES 良率 | `references/良率.md` |
| 完结良率 / 已完结工单 / finished_wo | `references/良率.md`（第 2 部分） |
| FBB 比率 / 坏块比率 / fbb_ratio | `references/FBB比率.md` |
| DPPM / 失效DPPM | `references/DPPM-BIBB.md` |
| BIBB / 坏块数 / bibb_cnt | `references/DPPM-BIBB.md` |
| ECC 分布 / ECC 坏块 / 工单ECC / FBB/GBB/BB | `references/ECC坏块.md` |
| ECC 箱线图 / 箱型图 / FBC / 周ECC箱线 / 批次箱线 / 多cycle箱线 | `references/箱线图.md` |
| FBB 箱线 / fbb_ratio_wo | `references/FBB比率.md`（周表即 FBB 箱线） |
| 温度 / nand_temp / 温度分布 | `references/温度.md` |
| 电流 / 电流箱线 / 电流分布 / 3sigma | `references/电流.md` |
| 测试工单 / 测试样品 / 本周测试 / week_test | `references/测试工单.md` |
| 不确定用哪个 | `references/指标总览.md`（指标清单 + 落表） |

调用示例：`get_skill_resource({"skill_name": "indicator-calc", "resource_path": "references/良率.md"})`

### 第二步：判断时间周期是否在表里
- **表里只有两种预计算周期**：日（`dws_indicator_d`）、周（`dws_indicator_w`）。其余周期（月、自定义日期段）**没有预计算表**。
- 日/周周期 → 直接 `sql_query` 查对应表（列名在文档里）。
- 非日/周周期（如"本月/上月/某段时间"）→ **按文档里的算法现算**，并**必须向用户讲清楚算法**：
  1. 说清用哪张源表（如 `dws_indicator_d` 按天聚合）
  2. 说清过滤与聚合步骤（去重/求和/分母）
  3. 说清时间窗怎么改（`date_trunc('week', ...)` → `date_trunc('month', ...)` 或 `BETWEEN` 自定义区间）
  4. 执行 SQL 得出结果
  5. 如果表里确实没有该指标的任何预计算，明确告知"该指标未预计算，需按 XX 算法现算"，不要编造。

### 第三步：输出（算法透明）
回答必须包含：**用了哪张表 / 哪些过滤 / 怎么聚合 / 结果**。
尤其是非预计算周期，算法说明是必须项，不能只给数字。

## 硬性规则
1. **禁止乱猜算法**：所有指标口径必须来自 references/ 文档。文档没覆盖的，如实说明"暂无该口径"，并用 `get_glossary_term` 或查 `dws_indicator_d/w` 的列名/描述辅助，不要虚构。
2. **只读**：只用 `sql_query` 只读查询，绝不改表/写库。
3. **时间周期优先级**：用户没指定周期时，默认按问题含义取日或周；指定了表里没有的周期时走"现算 + 讲算法"。
4. **多指标问题**：涉及多个指标时，分别读对应文档，逐一计算。
5. **指标列命名**：`dws_indicator_d`/`dws_indicator_w` 的指标列形如 `{flash_pn}_fbb_ratio_sn`、`{flash_pn}_mes_week`、`{flash_pn}_week_dppm`、`{flash_pn}_bibb_cnt_cycle`，实际查询时先 `SELECT DISTINCT indicator_name FROM dws_indicator_d WHERE indicator_name LIKE ...` 确认存在再查。
6. **【重要】现算必须转 TrinoSQL**：Dolphin/文档里的口径是 **SparkSQL**，但 `sql_query` 查的是 **Kyuubi/Trino**。凡现算，先读 `references/Spark转Trino.md` 做转换（`get_json_object`→`json_extract_scalar`、`to_json(named_struct)`→`json_format(cast(map(...)))`、`date_add(d,n)`→`date_add('day',n,d)`、`weekofyear`→`week`、`cast(int)`→`cast(integer)` 等）。查**已预计算表**（`dws_indicator_d/w`、`ads_fa_fbc_cycle`）不用转，直接 `json_extract_scalar` 取值。
7. **【重要】Spark UDF 在 Trino 不可用**：如 DPPM 的 `udf_db.chi_square_inv`、`count_ecc_fast`、`group_ecc_by_plane` 等。`chi_square_inv` 有 Wilson–Hilferty 正态近似（见 DPPM-BIBB.md，回答必须标"近似"）；其他 UDF 现算遇到就**如实告知用户**"依赖 Spark UDF，Trino 算不了"，不要编造不存在的函数。
