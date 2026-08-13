# 方案6A：每表"适用场景"路由提示（草稿 v1）

> 日期：2026-08-10
> 方案来源：`memory_duplication_analysis.md` §9.2 选项 A —— 紧凑清单每张表后加一行路由提示，如 `适用: 良率/坏块比率/批次波动`，让 agent 一眼定位目标表，避免反复 sql_query 探索。
> 输入：30 表 OpenMetadata 描述 + 血缘报告分层（`st_embed_lineage_report.md`）+ 20 场景→表映射（§8.2）。
> 设计原则（用户反馈）：**信息型**，不加"必须/禁止"命令条款。

---

## 一、格式设计

现状每表一行：`- {table}: {长描述}`（占 prompt 43%，13.5k 字符）。

方案6A：在行尾追加一段 **`适用:` 关键词**（继承描述里的【指标】【核心维度】，压缩成"什么问题该查这张表"）：

```
- dws_indicator_w: 【业务定义】...【核心字段】... ｜ 适用: 周良率/坏块比率/批次波动/周报指标
- dwd_power_current_di: 【业务定义】... ｜ 适用: 电流值/电流分布比例/电流规格判定
```

- 追加的 token 极小（每表 ~10-20 字 × 30 表 ≈ 500 字符）
- 不删原描述（完整描述留给需要时 `get_table_schema` 细看，但路由提示让模型**不用通读全表描述就能选表**）
- 后续可做"分层注入"再压体积（热表全描述 + 温表一行 + 冷表省略）——与方案6A正交

---

## 二、30 表路由映射（草稿）

> 映射来源：每表【业务定义/指标/核心维度】→ 反推"用户什么业务问题会来查这张表"。

| # | 表 | 适用场景（路由提示） |
|---|---|---|
| 1 | ods_mes_production_report | MES 原始报表核对（原口径）、MES vs log 缺失比对 |
| 2 | ods_dut_result | 原始测试记录（日志级核对/回溯，已加工见 dwd_dut_result） |
| 3 | ods_dut_result_item | 原始测项（日志级核对，已加工见 dwd_dut_result_item） |
| 4 | ods_dut_result_subitem | 原始子项值（日志级核对，已加工见 dwd_dut_result_subitem） |
| 5 | dim_base_project | 项目配置：颗粒映射/PN/阈值（slc/tlc/qlc、DPPM、温度、电流）/BIBB |
| 6 | dim_base_sn_di | 串号查询：UID→SN、EFUSE ID、行转列维度字段（Port/FlashID/SerialNumber） |
| 7 | dim_base_wo_di | 工单信息：状态/分类/返测单、订单、委外厂商、数量、产品 |
| 8 | dim_dqc_db | DB/zip 文件解析状态 |
| 9 | dim_dqc_state | 数据质量异常（WO_LOSS/DUPLICATE/NULL_FIELD）、处理状态/根因 |
| 10 | dwd_dqc_psn | PSN 跨工单/PN 重复检测 |
| 11 | dwd_dut_result | DUT 测试明细首选（已补全 flash_pn/item_control，note 解析 test_number/machine_id/test_type）：站位/机台/测试类型 |
| 12 | dwd_dut_result_item | 测项明细首选：RDT/ECC/功耗测项执行结果 |
| 13 | dwd_dut_result_subitem | 子项明细首选：子项值/规格上下限 |
| 14 | dwd_dut_result_w | 测项子项展开宽表：指标值（ECC/SleepCurrent/温度/VDT_COUNT）+维度值（软件包/Port）、BurnIn 时长 |
| 15 | dwd_mes_lot | **MES 生产明细首选**（已补全 flash_pn/item_control）：按项目/颗粒维度的良率/投入产出/lot 明细 |
| 16 | dwd_fa_bb_block | block 级坏块明细：GBB 块位置/类型 |
| 17 | dwd_fa_ecc_block | block 级 ECC 值 |
| 18 | dwd_fa_ecc_die_di | die 级 ECC：温度（nand/controller start-end）、VDT |
| 19 | dwd_fa_ecc_plane_di | plane 级 ECC 字符串 |
| 20 | dwd_power_current_di | 电流值/电流分布比例/电流规格判定（500-550 范围等） |
| 21 | dwd_power_temperature_di | nandTj/controller 温度、VDT 计数、burnin 时长 |
| 22 | dws_fa_bb_block | 坏块汇总：减坏块良率损失、FBB/GBB 分布 |
| 23 | dws_fa_ecc_cycle | cycle 级坏块统计 |
| 24 | dws_fa_ecc_cycle_stat | cycle 坏块分布：max/min ECC、样本数 |
| 25 | dws_fa_ecc_die | die 级坏块统计 |
| 26 | dws_fa_ecc_die_stat | die 坏块分布统计 |
| 27 | dws_fa_ecc_plane | plane 级坏块分类：FBB/GBB/HECC 定义、坏块率 |
| 28 | dws_indicator_d | 日粒度指标值（{flash_pn}_fbb_ratio_sn 等） |
| 29 | dws_indicator_w | 周良率/坏块比率/批次波动/周报指标（_fbb_ratio_wo 等） |
| 30 | ads_fa_fbc_cycle | 箱线图分析：FBC/ECC cycle 分布、四分位数/异常值 |

---

## 三、与血缘报告的分层对应（可验证路由提示合理性）

| 层 | 表 | 路由提示关键词 |
|---|---|---|
| ODS | ods_mes_production_report / ods_dut_result(_item/_subitem) | 原始 MES/日志数据 |
| DIM | dim_base_project/sn_di/wo_di、dim_dqc_*、dwd_dqc_psn | 项目/SN/工单/质量状态 维度 |
| DWD | dwd_dut_result(_w/_item/_subitem)、dwd_fa_*、dwd_power_*、dwd_mes_lot | 明细：测试/坏块/ECC/电流/温度 |
| DWS | dws_fa_*、dws_indicator_d/w | 汇总：坏块统计/指标 |
| ADS | ads_fa_fbc_cycle | 应用：箱线图 |

血缘链路（上游→下游）印证：`ods_dut_result → dwd_dut_result_w → dwd_power_current_di/temperature → dws_indicator_d → dws_indicator_w`。指标问题最终落在 **dws_indicator_w/d**，明细问题落在 DWD 层，与路由提示一致。

**DWD 优先于 ODS（用户 2026-08-10 确认，推广到全部同源 ODS 表）**：DWD 层表是 ODS 清洗加工后、已关联 dim 补全了 flash_pn/item_control 等字段，信息更完整。查生产/测试明细一律首选 DWD 层（`dwd_mes_lot`、`dwd_dut_result*`），ODS 层仅用于日志级原始核对/回溯。ODS 路由提示标注"已加工见 dwd_*"引导。

---

## 四、实施位置

`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/agentic_data_api.py`
`_build_compact_catalog()`（约 line 482）：

```python
# 新增：表 → 适用场景 路由提示（方案6A，信息型）
_TABLE_ROUTING_HINTS = {
    "ods_mes_production_report": "MES 良率/投入量/错误码分布、MES vs log 比对",
    ...
}

# 行尾追加
hint = _TABLE_ROUTING_HINTS.get(name)
lines.append(f"- {name}: {desc} ｜ 适用: {hint}" if hint else f"- {name}: {desc}")
```

---

## 五、待确认

1. **映射是否准确**：每表路由提示是否与业务口径一致（尤其 DWD/DWS 易混淆的表）
2. **格式**：`｜ 适用: ...` 放行尾是否合适？还是改用独立一行 `- 适用: ...`（更醒目但多 30 行）？
3. **是否顺带做分层注入**（热表全描述 + 温表一行 + 冷表省略），把 13.5k 压到 ~8k？
