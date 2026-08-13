# ECC 坏块口径（FBB / GBB / HECC / UECC / PSF / ESF）

> 来源：DolphinScheduler `sub_st_embed_ods_to_ads` → `to_dws_ecc_plane` / `to_dws_bb_block` / `to_dws_ecc_die` / `to_dws_ecc_cycle`，及 `周报_WEEK_通用` → `to_slc_wo` 等（2026-08-11）。

## 业务定义
ECC 坏块按 block 的 ECC 值分类。ECC 值落"哨兵码"或超过阈值即判为坏块/高纠错：
- **FBB**（Factory Bad Block，工厂坏块）= block ECC 值 == bibb_map['FBB'] 哨兵码
- **GBB**（Grown Bad Block，增长坏块）= block ECC 值 ∈ {UECC, PSF, ESF, BB_Skip} 哨兵码之一
- **HECC**（High ECC，高纠错）= block ECC 值 > 该 cycle 的 ECC 阈值（target_limit）且不是任何哨兵码
- 其他哨兵：UECC（不可纠错）、PSF（持久写失效）、ESF、BB_Skip（跳块）、RDT、Read_empty、tBERS/tPROG/tR（UFS 专用）

## 哨兵码与阈值（来自 `dim_base_project`）
| 类型 | 普通值 | 4KB 控制器值（is_4kb_controller=1） |
|---|---|---|
| FBB | 224 | 65504 |
| UECC | 225 | 65505 |
| PSF | 226 | 65506 |
| ESF | 239 | 65519 |
| BB_Skip | 223 | 65503 |
| RDT | 240 | 65520 |
| Read_empty | 231 | 65534 |
| tBERS / tPROG / tR | 241 / 242 / 243 | UFS 产品（-9999 不判坏） |

- **target_limit（HECC 阈值）**：按 `subitem_name`（ECC_SLC/TLC/QLC）取 `dim_base_project.slc_threshold/tlc_threshold/qlc_threshold` 的 `cycle{n}` 值（map），缺省用纯数值（slc_pure_num 等），再没有取 999999。
- HECC 判定排除码集合：`(fbb, uecc, psf, esf, bb_skip, rdt, read_empty, 254)`。

## 数据层级（明细 → 各层统计）
| 层 | 明细表 | 统计表 | 粒度 | 用途 |
|---|---|---|---|---|
| plane | `dwd_fa_ecc_plane_di`（ecc_value_plane 逗号串拆开逐 block 分类） | `dws_fa_ecc_plane` | result_guid+cycle+die+plane | FBB 比率源、plane 级坏块 |
| die | —（由 plane 聚合） | `dws_fa_ecc_die` | result_guid+cycle+die | die 级坏块 |
| cycle | —（由 die 聚合） | `dws_fa_ecc_cycle` | result_guid+cycle | cycle 级坏块（BIBB/DPPM 源） |
| block | `dwd_fa_bb_block`（block 明细，每 block 一个 bb_type） | `dws_fa_bb_block` | result_guid+cycle+die+plane+block | block 级坏块位置/类型 |
| 分布 | — | `dws_fa_ecc_cycle_stat` / `dws_fa_ecc_die_stat` | 按 ECC 值分布 | max/min ECC、样本数 |
| 箱线 | — | `ads_fa_fbc_cycle` | wo+cycle+ecc_type | 四分位数/异常值 |

- 各层 `fbb_cnt / gbb_cnt / hecc_cnt / uecc_cnt / psf_cnt / esf_cnt / total_cnt` 列名一致，便于上卷聚合。
- `gbb_cnt = uecc_cnt + psf_cnt + esf_cnt + bb_skip_cnt`（`dws_fa_bb_block` 定义）。
- 所有层过滤 `subitem_name in ('ECC_SLC','ECC_TLC','ECC_QLC')`。

## 直接查表
**plane 级**（ECC 分布 / plane 坏块）：
```sql
SELECT wo, flash_pn, project, cycle_number, die_number, plane_number,
       fbb_cnt, gbb_cnt, hecc_cnt, uecc_cnt, psf_cnt, esf_cnt, total_cnt
FROM st_embed.dws_fa_ecc_plane
WHERE subitem_name IN ('ECC_SLC','ECC_TLC','ECC_QLC')
  AND dt BETWEEN '{开始}' AND '{结束}'
  AND wo = '{wo}'   -- 工单ECC 时限定
```
**block 级**（坏块位置/类型，FBB/GBB 明细）：
```sql
SELECT wo, flash_pn, cycle_number, die_number, plane_number, block_number,
       fbb_cnt, gbb_cnt, hecc_cnt, uecc_cnt, psf_cnt, esf_cnt
FROM st_embed.dws_fa_bb_block
WHERE subitem_name IN ('ECC_SLC','ECC_TLC','ECC_QLC')
  AND dt BETWEEN '{开始}' AND '{结束}'
```
**坏块率**：`坏块率 = (gbb_cnt + fbb_cnt) / total_cnt`（或按业务口径取 fbb+gbb 占全部 block 比例）；坏块分布用 `dws_fa_ecc_cycle_stat`/`dws_fa_ecc_die_stat`。

## 现算（表里没有的周期）
从 `dwd_fa_ecc_plane_di`（plane 明细）按分类逻辑现算，时间窗换成目标周期：
```sql
SELECT project, flash_pn, wo,
       COUNT(CASE WHEN ecc_value = 224 THEN 1 END) AS fbb_cnt,
       COUNT(CASE WHEN ecc_value IN (225,226,239,223) THEN 1 END) AS gbb_cnt,
       COUNT(*) AS total_cnt
FROM st_embed.dwd_fa_ecc_plane_di
WHERE subitem_name IN ('ECC_SLC','ECC_TLC','ECC_QLC')
  AND dt BETWEEN '{开始}' AND '{结束}'
GROUP BY project, flash_pn, wo
```
> 注意：表内 `ecc_value_plane` 是逗号串，直接 COUNT 需先 `posexplode(split(ecc_value_plane, ','))`；上面的简化 SQL 假设已拆行。实际优先用各层统计表（dws_fa_ecc_*）做时间窗替换，更准。

## 注意/陷阱
- **哨兵码分普通/4KB 两套**（224/225 vs 65504/65505），判断前先确认 `is_4kb_controller`。
- **GBB 是 UECC/PSF/ESF/BB_Skip 的并集**，不是独立哨兵。
- **HECC 阈值按 cycle 查 map**（`cycle{n}`），缺失用纯数值，别再猜阈值。
- 温度/电流类（Burnin、nandTj、电流分布）不在本技能第一批口径里，先查 `dwd_power_*` / `dwd_fa_ecc_die_di`（burnin 见路由表，eMMC VDT 口径）。
