# ST_EMBED 调度血缘报告（DolphinScheduler 抽取）

> 生成：2026-08-10 ｜ 数据源：DolphinScheduler 项目 ST_EMBED（30 个工作流）

## 一、表级血缘（生产链路，目标表 <- 源表）

### ODS(贴源)

- **st_embed.ods_mes_production_report**
  - 构建任务: `to_mes_ods`（SUB_MES调度）
  - 依赖源表: masterdata_db.dim_wo, mes_db.dwd_yield_lot_station

### DIM(维度)

- **mysql_mdm.p_bd_mdm.dim_dqc_temp_resolved_issues**
  - 构建任务: `DQC_工单级数据恢复`（DQC, SUB_DQC_周报）
  - 依赖源表: mysql_mdm.p_bd_mdm.dwd_embed_dqc_state, st_embed.ads_fa_fbc_cycle, st_embed.dim_base_sn_di, st_embed.dwd_dut_result, st_embed.dwd_dut_result_item, st_embed.dwd_dut_result_subitem, st_embed.dwd_dut_result_w, st_embed.dwd_fa_bb_block, st_embed.dwd_fa_ecc_block, st_embed.dwd_fa_ecc_die_di, st_embed.dwd_fa_ecc_plane_di, st_embed.dwd_power_current_di, st_embed.dwd_power_temperature_di, st_embed.dws_fa_ecc_cycle, st_embed.dws_fa_ecc_cycle_stat, st_embed.dws_fa_ecc_die, st_embed.dws_fa_ecc_plane, st_embed.dws_indicator_d, st_embed.dws_indicator_w, st_embed.ods_dut_result_item, st_embed.ods_dut_result_subitem

- **st_embed.dim_base_sn_di**
  - 构建任务: `to_dim_sn`（sub_st_embed_ods_to_ads, SUB_补数数据更新）
  - 依赖源表: st_embed.dwd_dut_result_w, st_embed.dwd_fa_bb_block, st_embed.dwd_fa_ecc_block, st_embed.dwd_fa_ecc_die_di, st_embed.dwd_fa_ecc_plane_di, st_embed.dwd_power_current_di, st_embed.dwd_power_temperature_di, st_embed.dws_fa_ecc_cycle, st_embed.dws_fa_ecc_cycle_stat, st_embed.dws_fa_ecc_die, st_embed.dws_fa_ecc_plane

- **st_embed.dim_dqc_state**
  - 构建任务: `数据问题监控`（SUB_DQC_按月）
  - 依赖源表: st_embed.ads_fa_fbc_cycle, st_embed.dim_base_sn_di, st_embed.dwd_dut_result, st_embed.dwd_dut_result_item, st_embed.dwd_dut_result_subitem, st_embed.dwd_dut_result_w, st_embed.dwd_fa_bb_block, st_embed.dwd_fa_ecc_block, st_embed.dwd_fa_ecc_die_di, st_embed.dwd_fa_ecc_plane_di, st_embed.dwd_power_current_di, st_embed.dwd_power_temperature_di, st_embed.dws_fa_ecc_cycle, st_embed.dws_fa_ecc_cycle_stat, st_embed.dws_fa_ecc_die, st_embed.dws_fa_ecc_plane, st_embed.ods_dut_result, st_embed.ods_dut_result_item, st_embed.ods_dut_result_subitem, temp_today_issues

### DWD(明细)

- **mysql_mdm.p_bd_mdm.dwd_embed_dqc_temp_issues**
  - 构建任务: `工单级别监测`（DQC, SUB_DQC_周报）
  - 依赖源表: dwd_embed_dqc_temp_duplicate_today_issues_view, dwd_embed_dqc_temp_null_fileds_today_issues_view, dwd_embed_dqc_temp_wo_loss_today_issues_view, dwd_embed_dqc_week_temp_today_issues_view, st_embed.ads_fa_fbc_cycle, st_embed.dim_base_project, st_embed.dim_base_sn_di, st_embed.dim_base_wo_di, st_embed.dwd_dut_result, st_embed.dwd_dut_result_item, st_embed.dwd_dut_result_subitem, st_embed.dwd_dut_result_w, st_embed.dwd_fa_bb_block, st_embed.dwd_fa_ecc_block, st_embed.dwd_fa_ecc_die_di, st_embed.dwd_fa_ecc_plane_di, st_embed.dwd_power_current_di, st_embed.dwd_power_temperature_di, st_embed.dws_fa_ecc_cycle, st_embed.dws_fa_ecc_cycle_stat, st_embed.dws_fa_ecc_die, st_embed.dws_fa_ecc_plane, st_embed.dws_indicator_d, st_embed.dws_indicator_w, st_embed.ods_dut_result, st_embed.ods_dut_result_item, st_embed.ods_dut_result_subitem

- **st_embed.dwd_dut_result**
  - 构建任务: `to_dwd_level_1`（sub_st_embed_ods_to_ads, SUB_数仓软件包更新）
  - 依赖源表: st_embed.dim_base_project, st_embed.dim_base_wo_di, st_embed.ods_dut_result

- **st_embed.dwd_dut_result_item**
  - 构建任务: `to_dwd_level_2`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.ods_dut_result, st_embed.ods_dut_result_item

- **st_embed.dwd_dut_result_subitem**
  - 构建任务: `to_dwd_level_3`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.ods_dut_result, st_embed.ods_dut_result_item, st_embed.ods_dut_result_subitem

- **st_embed.dwd_dut_result_w**
  - 构建任务: `to_dwd_wide`（sub_st_embed_ods_to_ads, SUB_数仓软件包更新）
  - 依赖源表: st_embed.dim_base_wo_di, st_embed.dwd_dut_result, st_embed.dwd_dut_result_item, st_embed.dwd_dut_result_subitem

- **st_embed.dwd_fa_ecc_block**
  - 构建任务: `to_dwd_ecc_block`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dwd_fa_ecc_plane_di

- **st_embed.dwd_fa_ecc_die_di**
  - 构建任务: `to_dwd_ecc_die_tj_4kb`（sub_st_embed_ods_to_ads, SUB_数仓软件包更新）
  - 依赖源表: st_embed.dim_base_project, st_embed.dim_base_sn_di, st_embed.dim_base_wo_di, st_embed.dwd_dut_result_w

- **st_embed.dwd_fa_ecc_plane_di**
  - 构建任务: `to_dwd_ecc_plane`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dwd_fa_ecc_die_di

- **st_embed.dwd_mes_lot**
  - 构建任务: `to_mes_dwd`（SUB_MES调度）
  - 依赖源表: st_embed.dim_base_project, st_embed.dim_base_wo_di, st_embed.ods_mes_production_report

- **st_embed.dwd_power_current_di**
  - 构建任务: `to_dwd_current_emmc`（sub_st_embed_ods_to_ads, SUB_数仓软件包更新）
  - 依赖源表: st_embed.dim_base_sn_di, st_embed.dim_base_wo_di, st_embed.dwd_dut_result_w

- **st_embed.dwd_power_temperature_di**
  - 构建任务: `to_dwd_temperature`（sub_st_embed_ods_to_ads, SUB_数仓软件包更新）
  - 依赖源表: st_embed.dim_base_sn_di, st_embed.dim_base_wo_di, st_embed.dwd_dut_result_w

### DWS(汇总)

- **st_embed.dws_fa_bb_block**
  - 构建任务: `to_dws_bb_block`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260806102705097）
  - 依赖源表: st_embed.dwd_fa_bb_block, st_embed.dwd_fa_ecc_die_di

- **st_embed.dws_fa_ecc_cycle**
  - 构建任务: `to_dws_ecc_cycle`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dws_fa_ecc_die

- **st_embed.dws_fa_ecc_cycle_stat**
  - 构建任务: `to_dws_ecc_cycle_stat_sn_cycle`（sub_st_embed_ods_to_ads, SUB_数仓软件包更新）
  - 依赖源表: st_embed.dim_base_wo_di, st_embed.dwd_fa_ecc_block, st_embed.dwd_fa_ecc_die_di

- **st_embed.dws_fa_ecc_die**
  - 构建任务: `to_dws_ecc_die`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dws_fa_ecc_plane

- **st_embed.dws_fa_ecc_die_stat**
  - 构建任务: `to_dws_ecc_die_stats`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dwd_fa_ecc_die_di

- **st_embed.dws_fa_ecc_plane**
  - 构建任务: `to_dws_ecc_plane`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dim_base_project, st_embed.dwd_fa_ecc_plane_di

- **st_embed.dws_indicator_d**
  - 构建任务: `to_dws_indicator_d_fbb`（sub_st_embed_ods_to_ads, test_周报_DAY_通用_import_20260601151157340）
  - 依赖源表: st_embed.dim_base_project, st_embed.dwd_power_current_di, st_embed.dws_fa_ecc_cycle, st_embed.dws_fa_ecc_plane

- **st_embed.dws_indicator_w**
  - 构建任务: `fbb 指标-DWS层`（周报_WEEK_通用）
  - 依赖源表: st_embed.dim_base_project, st_embed.dim_base_wo_di, st_embed.dwd_dut_result, st_embed.dwd_fa_ecc_block, st_embed.dwd_mes_lot, st_embed.dwd_power_current_di, st_embed.dwd_power_temperature_di, st_embed.dws_indicator_d

### ADS(应用)

- **st_embed.ads_fa_fbc_cycle**
  - 构建任务: `to_ads_fbc_ecc_cycle_box`（sub_st_embed_ods_to_ads, sub_st_embed_ods_to_ads_工单补数_import_20260709143506592）
  - 依赖源表: st_embed.dws_fa_ecc_cycle_stat

## 二、关键指标表字段血缘

### st_embed.dws_indicator_d

源表: st_embed.dim_base_project, st_embed.dwd_power_current_di, st_embed.dws_fa_ecc_cycle, st_embed.dws_fa_ecc_plane

| 目标列 | 来源表达式 | 引用列 |
|---|---|---|
| bin | `bin` | bin |
| data_source | `data_source` | data_source |
| dimension_json | `JSON_FORMAT(STRUCT(die_number AS die_number, cycle_number AS cycle_number, plane_number AS plane_num` | a.flash_pn, cycle_number, die_number, efuse_id, fbb_ratio, plane_number |
| dt | `dt` | dt |
| dut_sn | `dut_sn` | dut_sn |
| error_code | `error_code` | error_code |
| etl_batch | `etl_batch` | etl_batch |
| etl_dt | `etl_dt` | etl_dt |
| etl_insert_time | `NOW()` |  |
| etl_product_line | `etl_product_line` | etl_product_line |
| flash | `flash` | a.flash |
| flash_pn | `flash_pn` | a.flash_pn |
| guid | `MD5(CONCAT_WS('_', COALESCE(guid, ''), COALESCE(CONCAT(a.flash_pn, '_fbb_ratio_sn'), '')))` | a.flash_pn, guid |
| indicator_name | `CONCAT(a.flash_pn, '_fbb_ratio_sn')` | a.flash_pn |
| indicator_value | `fbb_cnt / NULLIF((TRY_CAST(block_size AS INT)), 0)` | block_size, fbb_cnt |
| item_control | `item_control` | a.item_control |
| lot | `lot` | lot |
| pn | `pn` | a.pn |
| product_type | `product_type` | product_type |
| project | `project` | a.project |
| result_guid | `result_guid` | result_guid |
| software_information | `software_information` | a.software_information |
| station | `station` | station |
| test_number | `test_number` | test_number |
| test_result | `test_result` | test_result |
| time_end | `time_end` | time_end |
| time_start | `time_start` | time_start |
| wo | `wo` | wo |
| year_week_number | `CONCAT(YEAR(CAST(TS_OR_DS_ADD(DATE_TRUNC('WEEK', dt), 3, DAY) AS DATE)), '年第', WEEK_OF_YEAR(CAST(dt ` | dt |

### st_embed.dws_indicator_w

源表: st_embed.dim_base_project, st_embed.dim_base_wo_di, st_embed.dwd_dut_result, st_embed.dwd_fa_ecc_block, st_embed.dwd_mes_lot, st_embed.dwd_power_current_di, st_embed.dwd_power_temperature_di, st_embed.dws_indicator_d

| 目标列 | 来源表达式 | 引用列 |
|---|---|---|
| data_source | `data_source` | data_source |
| dimension_json | `JSON_FORMAT(STRUCT(fbb_ratio AS fbb_ratio))` | fbb_ratio |
| etl_batch | `TRY_CAST('${etl_batch}' AS BIGINT)` |  |
| etl_dt | `CAST('${etl_dt}' AS DATE)` |  |
| etl_insert_time | `NOW()` |  |
| flash | `flash` | flash |
| flash_pn | `flash_pn` | flash_pn |
| guid | `MD5(CONCAT_WS('_', COALESCE(wo, ''), '', '', COALESCE(project, ''), COALESCE(flash_pn, ''), COALESCE` | fbb_ratio, flash_pn, pn, project, software_information, wo |
| indicator_name | `CONCAT(flash_pn, '_fbb_ratio_wo')` | flash_pn |
| indicator_value | `JSON_FORMAT(STRUCT(q1 AS q1, median AS median, q3 AS q3, upper AS upper, lower AS lower, outliers AS` | lower, median, outliers, q1, q3, upper |
| item_control | `item_control` | item_control |
| pn | `pn` | pn |
| product_type | `product_type` | product_type |
| project | `project` | project |
| software_information | `software_information` | software_information |
| station | `''` |  |
| t.dimension_json | `s.dimension_json` | s.dimension_json |
| t.etl_batch | `s.etl_batch` | s.etl_batch |
| t.etl_dt | `s.etl_dt` | s.etl_dt |
| t.etl_insert_time | `NOW()` |  |
| t.indicator_value | `s.indicator_value` | s.indicator_value |
| wo | `wo` | wo |
| year_week_number | `year_week_number` | year_week_number |

### st_embed.ads_fa_fbc_cycle

源表: st_embed.dws_fa_ecc_cycle_stat

| 目标列 | 来源表达式 | 引用列 |
|---|---|---|
| box_type | `box_type` | box_type |
| count_total | `count_total` | count_total |
| cycle_number | `cycle_number` | cycle_number |
| ecc_type | `ecc_type` | ecc_type |
| etl_insert_time | `NOW()` |  |
| etl_update_time | `NOW()` |  |
| flash_pn | `flash_pn` | flash_pn |
| guid | `MD5(CONCAT_WS('_', COALESCE(wo, ''), COALESCE(cycle_number, ''), COALESCE(ecc_type, ''), COALESCE(bo` | box_type, cycle_number, ecc_type, flash_pn, wo |
| latest_dt | `latest_dt` | latest_dt |
| latest_etl_dt | `latest_etl_dt` | latest_etl_dt |
| lower | `lower` | lower |
| median | `median` | median |
| outliers | `outliers` | outliers |
| project | `project` | project |
| q1 | `q1` | q1 |
| q3 | `q3` | q3 |
| t.count_total | `s.count_total` | s.count_total |
| t.latest_dt | `s.latest_dt` | s.latest_dt |
| t.latest_etl_dt | `s.latest_etl_dt` | s.latest_etl_dt |
| t.lower | `s.lower` | s.lower |
| t.median | `s.median` | s.median |
| t.outliers | `s.outliers` | s.outliers |
| t.q1 | `s.q1` | s.q1 |
| t.q3 | `s.q3` | s.q3 |
| t.upper | `s.upper` | s.upper |
| t.wo_status | `s.wo_status` | s.wo_status |
| upper | `upper` | upper |
| wo | `wo` | wo |
| wo_status | `wo_status` | wo_status |

### st_embed.dws_fa_ecc_plane

源表: st_embed.dim_base_project, st_embed.dwd_fa_ecc_plane_di

| 目标列 | 来源表达式 | 引用列 |
|---|---|---|
| bb_skip_cnt | `bb_skip_cnt` | bb_skip_cnt |
| berrorcode | `berrorcode` | berrorcode |
| bin | `bin` | bin |
| block_size | `block_size` | block_size |
| controller_temp_end | `controller_temp_end` | controller_temp_end |
| controller_temp_start | `controller_temp_start` | controller_temp_start |
| cycle_number | `cycle_number` | cycle_number |
| data_source | `data_source` | data_source |
| die_number | `die_number` | die_number |
| dt | `dt` | dt |
| dut_sn | `dut_sn` | dut_sn |
| ecc_value | `a.ecc_value_plane` | a.ecc_value_plane |
| efuse_id | `efuse_id` | efuse_id |
| error_code | `error_code` | error_code |
| esf_cnt | `esf_cnt` | esf_cnt |
| etl_batch | `etl_batch` | etl_batch |
| etl_dt | `etl_dt` | etl_dt |
| etl_insert_time | `NOW()` |  |
| etl_product_line | `etl_product_line` | etl_product_line |
| etl_update_time | `NOW()` |  |
| fbb_cnt | `fbb_cnt` | fbb_cnt |
| flash | `flash` | flash |
| flash_pn | `flash_pn` | flash_pn |
| flash_uid | `flash_uid` | flash_uid |
| fwerror | `fwerror` | fwerror |
| fwerrorcaller | `fwerrorcaller` | fwerrorcaller |
| gbb_cnt | `gbb_cnt` | gbb_cnt |
| guid | `guid` | a.guid |
| hecc_cnt | `hecc_slc_cnt + hecc_tlc_cnt + hecc_qlc_cnt` | hecc_qlc_cnt, hecc_slc_cnt, hecc_tlc_cnt |
| host_mac | `host_mac` | host_mac |
| host_os | `host_os` | host_os |
| item_control | `item_control` | item_control |
| lot | `lot` | lot |
| lsl | `lsl` | lsl |
| machine_id | `machine_id` | machine_id |
| machine_type | `machine_type` | machine_type |
| nand_temp_end | `nand_temp_end` | nand_temp_end |
| nand_temp_start | `nand_temp_start` | nand_temp_start |
| note | `note` | note |
| num_planes | `num_planes` | num_planes |
| plane_number | `plane_number` | plane_number |
| pn | `pn` | pn |
| port | `port` | port |
| product_type | `product_type` | product_type |
| project | `project` | project |
| psf_cnt | `psf_cnt` | psf_cnt |
| quality_level | `quality_level` | quality_level |
| rdt_cnt | `rdt_cnt` | rdt_cnt |
| rdterror | `rdterror` | rdterror |
| read_empty_cnt | `read_empty_cnt` | read_empty_cnt |
| result_guid | `result_guid` | result_guid |
| software_information | `software_information` | software_information |
| station | `station` | station |
| subitem_name | `subitem_name` | subitem_name |
| tbers_cnt | `tbers_cnt` | tbers_cnt |
| test_number | `test_number` | test_number |
| test_result | `test_result` | test_result |
| time_end | `time_end` | time_end |
| time_start | `time_start` | time_start |
| total_cnt | `fbb_cnt + esf_cnt + psf_cnt + uecc_cnt + hecc_slc_cnt + hecc_tlc_cnt + hecc_qlc_cnt + bb_skip_cnt + ` | bb_skip_cnt, esf_cnt, fbb_cnt, hecc_qlc_cnt, hecc_slc_cnt, hecc_tlc_cnt |
| tprog_cnt | `tprog_cnt` | tprog_cnt |
| tr_cnt | `tr_cnt` | tr_cnt |
| uecc_cnt | `uecc_cnt` | uecc_cnt |
| unit | `unit` | unit |
| usl | `usl` | usl |
| vperror | `vperror` | vperror |
| wo | `wo` | wo |

### st_embed.dws_fa_bb_block

源表: st_embed.dwd_fa_bb_block, st_embed.dwd_fa_ecc_die_di

| 目标列 | 来源表达式 | 引用列 |
|---|---|---|
| bb_skip_cnt | `bb_skip_cnt_block` | bb_skip_cnt_block |
| berrorcode | `berrorcode` | berrorcode |
| bin | `bin` | bin |
| block_number | `block_number` | block_number |
| controller_temp_end | `controller_temp_end` | controller_temp_end |
| controller_temp_start | `controller_temp_start` | controller_temp_start |
| cycle_number | `cycle_number` | cycle_number |
| data_source | `data_source` | data_source |
| die_number | `die_number` | die_number |
| dt | `dt` | dt |
| dut_sn | `dut_sn` | dut_sn |
| efuse_id | `efuse_id` | efuse_id |
| error_code | `error_code` | error_code |
| esf_cnt | `esf_cnt_block` | esf_cnt_block |
| etl_batch | `etl_batch` | etl_batch |
| etl_dt | `etl_dt` | etl_dt |
| etl_insert_time | `NOW()` |  |
| etl_product_line | `etl_product_line` | etl_product_line |
| etl_update_time | `NOW()` |  |
| fbb_cnt | `fbb_cnt_block` | fbb_cnt_block |
| flash | `flash` | flash |
| flash_pn | `flash_pn` | flash_pn |
| flash_uid | `flash_uid` | flash_uid |
| fwerror | `fwerror` | fwerror |
| fwerrorcaller | `fwerrorcaller` | fwerrorcaller |
| gbb_cnt | `uecc_cnt_block + psf_cnt_block + esf_cnt_block + bb_skip_cnt_block` | bb_skip_cnt_block, esf_cnt_block, psf_cnt_block, uecc_cnt_block |
| guid | `MD5(CONCAT_WS('_', COALESCE(result_guid, ''), COALESCE(cycle_number, ''), COALESCE(die_number, ''), ` | block_number, cycle_number, die_number, plane_number, result_guid |
| hecc_cnt | `hecc_cnt_block` | hecc_cnt_block |
| host_mac | `host_mac` | host_mac |
| host_os | `host_os` | host_os |
| item_control | `item_control` | item_control |
| lot | `lot` | lot |
| lsl | `lsl` | lsl |
| machine_id | `machine_id` | machine_id |
| machine_type | `machine_type` | machine_type |
| nand_temp_end | `nand_temp_end` | nand_temp_end |
| nand_temp_start | `nand_temp_start` | nand_temp_start |
| note | `note` | note |
| plane_number | `plane_number` | plane_number |
| pn | `pn` | pn |
| port | `port` | port |
| product_type | `product_type` | product_type |
| project | `project` | project |
| psf_cnt | `psf_cnt_block` | psf_cnt_block |
| quality_level | `quality_level` | quality_level |
| rdt_cnt | `rdt_cnt_block` | rdt_cnt_block |
| rdterror | `rdterror` | rdterror |
| read_empty_cnt | `read_empty_cnt_block` | read_empty_cnt_block |
| result_guid | `result_guid` | result_guid |
| software_information | `software_information` | software_information |
| station | `station` | station |
| subitem_name | `subitem_name` | subitem_name |
| tbers_cnt | `tbers_cnt_block` | tbers_cnt_block |
| test_number | `test_number` | test_number |
| test_result | `test_result` | test_result |
| time_end | `time_end` | time_end |
| time_start | `time_start` | time_start |
| total_cnt | `fbb_cnt_block + hecc_cnt_block + uecc_cnt_block + psf_cnt_block + esf_cnt_block + bb_skip_cnt_block ` | bb_skip_cnt_block, esf_cnt_block, fbb_cnt_block, hecc_cnt_block, psf_cnt_block, read_empty_cnt_block |
| tprog_cnt | `tprog_cnt_block` | tprog_cnt_block |
| tr_cnt | `tr_cnt_block` | tr_cnt_block |
| uecc_cnt | `uecc_cnt_block` | uecc_cnt_block |
| unit | `unit` | unit |
| usl | `usl` | usl |
| vperror | `vperror` | vperror |
| wo | `wo` | wo |

### st_embed.dwd_power_current_di

源表: st_embed.dim_base_sn_di, st_embed.dim_base_wo_di, st_embed.dwd_dut_result_w

| 目标列 | 来源表达式 | 引用列 |
|---|---|---|
| berrorcode | `berrorcode` | berrorcode |
| bin | `bin` | bin |
| current_value | `current_value` | current_value |
| data_source | `data_source` | data_source |
| dt | `dt` | dt |
| dut_sn | `dut_sn` | dut_sn |
| efuse_id | `efuse_id` | efuse_id |
| error_code | `error_code` | error_code |
| etl_batch | `etl_batch` | etl_batch |
| etl_dt | `etl_dt` | etl_dt |
| etl_insert_time | `NOW()` |  |
| etl_product_line | `etl_product_line` | etl_product_line |
| etl_update_time | `NOW()` |  |
| flash | `flash` | flash |
| flash_pn | `flash_pn` | flash_pn |
| flash_uid | `flash_uid` | flash_uid |
| fwerror | `fwerror` | fwerror |
| fwerrorcaller | `fwerrorcaller` | fwerrorcaller |
| guid | `MD5(CONCAT_WS('-', COALESCE(source_guid, ''), COALESCE(item_name, ''), COALESCE(subitem_name, '')))` | item_name, source_guid, subitem_name |
| host_mac | `host_mac` | host_mac |
| host_os | `host_os` | host_os |
| item_control | `item_control` | item_control |
| item_name | `item_name` | item_name |
| lot | `lot` | lot |
| machine_id | `machine_id` | machine_id |
| machine_type | `machine_type` | machine_type |
| pn | `pn` | pn |
| port | `port` | port |
| product_type | `product_type` | product_type |
| project | `project` | project |
| quality_level | `quality_level` | quality_level |
| rdterror | `rdterror` | rdterror |
| software_information | `software_information` | software_information |
| source_guid | `source_guid` | source_guid |
| station | `station` | station |
| subitem_name | `subitem_name` | subitem_name |
| t.etl_update_time | `CURRENT_TIMESTAMP()` |  |
| t.software_information | `dim.software_information` | dim.software_information |
| test_number | `test_number` | test_number |
| test_result | `test_result` | test_result |
| time_end | `time_end` | time_end |
| time_start | `time_start` | time_start |
| unit | `unit` | unit |
| vperror | `vperror` | vperror |
| wo | `wo` | wo |
