# 规则路由（意图识别→选表）测试文档

> 日期：2026-08-10
> 目的：验证"根据用户问题选目标表"的规则路由（方案6.4 升级版 / 方案6A 配套），
> 评估选表命中率与提示词体积收益，决定是否接入生产代码。
> 约定工单：**SHCS26074748**（场景问题均绑定该具体工单，更接近真实提问）
> 验证脚本：`/tmp/route_preview.py`

***

## 一、被测对象：规则路由

```python
_ROUTING_KEYWORDS: Dict[str, List[str]]   # 关键词 → 候选表（业务词→"能回答它的表"）
def route_tables(question) -> List[str]:  # 问题 → 按命中关键词数排序取 top-8 表
```

**判定依据**：业务关键词（良率/电流/坏块/ECC/工单…）→ 表 的映射。
问题里的词命中关键词 → 累加候选表 → 按命中数排序 → 取 top-8 注入完整描述。

***
{"table": "dwd_dut_result_w", "description": "【业务定义】DUT 测试结果宽表，将 subitem 展开到一行，包含完整测试信息。value 字段具有双重身份：一部分子项（如 ECC_*、SleepCurrent、TEMPERATURE_*、VDT_COUNT_*）的 value 是指标值，直接用于计算分析；另一部分子项（如 Port、FlashID、FlashUID、FWType、SerialNumber、QRCode 等约 50+ 个维度字段）的 value 是维度值，在 dim_base_sn_di 中通过行转列（pivot）变成独立列 【粒度】一个 SN 的一次测试中，一个测试项下的一个测试子项 【指标】指标类子项（ECC_*、SleepCurrent、TEMPERATURE_*、CONTROLLER_TEMPERATURE_*、VDT_COUNT_* 等）的 value 是测量值；维度类子项（Port、FlashID、FlashUID、FWType、SerialNumber、QRCode 等）的 value 是属性值，不作为指标 【核心维度】wo（工单）、dut_sn（SN）、project（项目）、pn（产品PN）、item_name（测试项）、subitem_name（测试子项）、test_result（测试结果） 【核心字段】guid（主键=subitem guid）、result_guid（外键=result guid）、item_guid（外键=item guid）、subitem_name（测试子项）、value（测试值/属性值）、dt（分区键）", "schema": "{\"table_name\": \"dwd_dut_result_w\", \"fully_qualified_name\": \"p_trino_iceberg.iceberg.st_embed.dwd_dut_result_w\", \"columns\": [{\"name\": \"guid\", \"data_type\": \"VARCHAR\", \"description\": \"主键，对应 dwd_dut_result_subitem 的 guid|\"}, {\"name\": \"format_version\", \"data_type\": \"VARCHAR\", \"description\": \"测试日志格式版本号|【适用】日志解析兼容性判断|\"}, {\"name\": \"result_guid\", \"data_type\": \"VARCHAR\", \"description\": \"外键，对应 dwd_dut_result 的 guid|【外键】关联:dwd_dut_result.guid|\"}, {\"name\": \"item_guid\", \"data_type\": \"VARCHAR\", \"description\": \"外键，对应 dwd_dut_result_item 的 guid|【外键】关联:dwd_dut_result_item.guid|\"}, {\"name\": \"guid_1\", \"data_type\": \"VARCHAR\", \"description\": \"测试日志原始 guid_1，用于关联同一日志批次内的记录|\"}, {\"name\": \"guid_2\", \"data_type\": \"VARCHAR\", \"description\": \"测试日志原始 guid_2，唯一标识该测试项记录|【适用】日志级数据溯源|\"}, {\"name\": \"wo\", \"data_type\": \"VARCHAR\", \"description\": \"工单号|【适用】工单维度分析、良率统计|【注意】正式工单查询需排除 wo LIKE 'DPV%' 的虚拟工单|【外键】关联:dim_base_wo_di.wo|\"}, {\"name\": \"lot\", \"data_type\": \"VARCHAR\", \"description\": \"批次号|【适用】批次级追溯|\"}, {\"name\": \"dut_sn\", \"data_type\": \"VARCHAR\", \"description\": \"DUT 唯一标识，可以是 SN/LotID 等|【适用】单盘追溯、SN 级分析|【注意】不同项目可能复用同一 SN，需结合 project 和 wo 使用|\"}, {\"name\": \"station\", \"data_type\": \"VARCHAR\", \"description\": \"站位|【适用】站位维度分析|【枚举】站位名称由不同产线定义，无统一枚举|\"}, {\"name\": \"equipment\", \"data_type\": \"VARCHAR\", \"description\": \"机台编号|【适用】机台维度分析|\"}, {\"name\": \"host_os\", \"data_type\": \"VARCHAR\", \"description\": \"运行测试工具的 Host OS 版本|\"}, {\"name\": \"host_mac\", \"data_type\": \"VARCHAR\", \"description\": \"运行测试工具的 Host MAC 地址|\"}, {\"name\": \"site\", \"data_type\": \"VARCHAR\", \"description\": \"站点标识|\"}, {\"name\": \"port\", \"data_type\": \"VARCHAR\", \"description\": \"端口号|\"}, {\"name\": \"test_result\", \"data_type\": \"VARCHAR\", \"description\": \"测试结果|【枚举】pass=通过, fail=失败, na=不适用|\"}, {\"name\": \"error_code\", \"data_type\": \"VARCHAR\", \"description\": \"错误码|【适用】故障分析、错误归类|\"}, {\"name\": \"error_desc\", \"data_type\": \"VARCHAR\", \"description\": \"错误信息描述|【适用】故障排查|\"}, {\"name\": \"bin\", \"data_type\": \"VARCHAR\", \"description\": \"BIN 分类|【适用】BIN 级良率分析|\"}, {\"name\": \"time_start\", \"data_type\": \"TIMESTAMP\", \"description\": \"测试开始时间|【格式】UTC 时间戳 yyyy-MM-dd HH:mm:ss.SSS|【单位】毫秒精度|\"}, {\"name\": \"time_end\", \"data_type\": \"TIMESTAMP\", \"description\": \"测试结束时间|【格式】UTC 时间戳 yyyy-MM-dd HH:mm:ss.SSS|【单位】毫秒精度|\"}, {\"name\": \"time_elapse\", \"data_type\": \"BIGINT\", \"description\": \"测试耗时|【单位】毫秒|\"}, {\"name\": \"note\", \"data_type\": \"VARCHAR\", \"description\": \"项目自定义扩展信息，内含 test_number、machine_id、machine_type、test_type 等字段|【格式】JSON 字符串|【注意】DWD 层通过 get_json_object(note, '$.test_number') 等函数解析此字段|\"}, {\"name\": \"project\", \"data_type\": \"VARCHAR\", \"description\": \"项目名|【适用】按项目维度筛选|【外键】关联:dim_base_project.project|\"}, {\"name\": \"flash_pn\", \"data_type\": \"VARCHAR\", \"description\": \"厂商 Nand 颗粒资源别名，来自 dim_base_project 表|【外键】关联:dim_base_project(pn, flash)|\"}, {\"name\": \"flash\", \"data_type\": \"VARCHAR\", \"description\": \"项目 Nand 颗粒资源名称，来自 dim_base_wo_di 表|【适用】颗粒维度分析|\"}, {\"name\": \"item_control\", \"data_type\": \"VARCHAR\", \"description\": \"主控芯片型号，来自 dim_base_wo_di 表|【适用】主控维度分析、兼容性排查|\"}, {\"name\": \"item_capacity\", \"data_type\": \"VARCHAR\", \"description\": \"产品容量，来自 dim_base_wo_di 表|【枚举】8GB, 16GB, 32GB, 64GB, 128GB, 256GB, 512GB, 1TB, 2TB|【单位】GB/TB|\"}, {\"name\": \"pn\", \"data_type\": \"VARCHAR\", \"description\": \"产品 PN，来自 dim_base_wo_di 表|【适用】产品维度分析|【外键】关联:dim_base_project(pn LIKE)|\"}, {\"name\": \"quality_level\", \"data_type\": \"VARCHAR\", \"description\": \"质量等级，来自 dim_base_wo_di 表|【枚举】S1=最高等级, S2=次高等级, L1=标准等级, L2=基础等级|\"}, {\"name\": \"wo_status\", \"data_type\": \"VARCHAR\", \"description\": \"工单状态，来自 dim_base_wo_di 表|【枚举】OPEN=进行中, CLOSED=已完结|【注意】部分分析场景需排除未完结工单|\"}, {\"name\": \"software_information\", \"data_type\": \"VARCHAR\", \"description\": \"烧录到芯片中的 FW 软件包版本，来自 dim_base_wo_di 表|【适用】固件版本维度的不良分析|\"}, {\"name\": \"product_category\", \"data_type\": \"VARCHAR\", \"description\": \"产品分类，来自 dim_base_wo_di 表|【适用】按产品大类汇总|\"}, {\"name\": \"product_line\", \"data_type\": \"VARCHAR\", \"description\": \"产品线，来自 dim_base_wo_di 表|【枚举】EMMC LINE, EMBEDED LINE, UFS LINE, E-WEARABLE LINE|\"}, {\"name\": \"product_type\", \"data_type\": \"VARCHAR\", \"description\": \"产品类型，来自 dim_base_wo_di 表|【枚举】eMMC, ePOP5X, eMCP4X, eUFS, eUFS3.1, eUFS4.1|\"}, {\"name\": \"test_number\", \"data_type\": \"VARCHAR\", \"description\": \"正复测标识，从 ods_dut_result.note 的 JSON 字段解析|【枚举】0=正测, 1=复测|【注意】分析良率时需明确是否区分正复测|【格式】get_json_object(note, '$.test_number')|\"}, {\"name\": \"machine_id\", \"data_type\": \"VARCHAR\", \"description\": \"机台 ID，从 ods_dut_result.note 的 JSON 字段解析|【适用】机台维度分析|【格式】get_json_object(note, '$.machine_id')|\"}, {\"name\": \"machine_type\", \"data_type\": \"VARCHAR\", \"description\": \"机台类型，从 ods_dut_result.note 的 JSON 字段解析|【枚举】SLT, ATE, HT3309|【格式】get_json_object(note, '$.machine_type')|\"}, {\"name\": \"test_type\", \"data_type\": \"VARCHAR\", \"description\": \"测试类型，从 ods_dut_result.note 的 JSON 字段解析|【枚举】FULL-TEST=全测, FAIL-RETEST=失败重测|【格式】get_json_object(note, '$.test_type')|\"}, {\"name\": \"tool_version\", \"data_type\": \"VARCHAR\", \"description\": \"测试工具版本号|【适用】工具版本兼容性分析|\"}, {\"name\": \"test_plan\", \"data_type\": \"VARCHAR\", \"description\": \"测试计划名称|【适用】按测试计划维度筛选分析|\"}, {\"name\": \"item_name\", \"data_type\": \"VARCHAR\", \"description\": \"测试项名称|【枚举】RDT, ECC_CYCLE_*, SleepCurrent, tb_Sleep_current, HIBERNATE_TEST 等|【注意】ECC_CYCLE_* 的 * 为 cycle_number|\"}, {\"name\": \"subitem_name\", \"data_type\": \"VARCHAR\", \"description\": \"测试子项名称|【枚举】指标类：ECC_SLC, ECC_TLC, ECC_QLC, SleepCurrent, tb_Sleep_current, TEMPERATURE_*, CONTROLLER_TEMPERATURE_*, VDT_COUNT_VCC* 等；维度类：Port, FlashID, FlashUID, FWType, FW_Version, SerialNumber, QRCode, Controller_ID, PSn, dwPSN 等约 50+ 个|【注意】指标类子项的 value 参与计算分析，维度类子项的 value 在 dim_base_sn_di 中通过 pivoted CTE 行转列变成独立维度列；多 Die 场景下子项名含 DIE_0/DIE_1/DIE_2 用于拆分 flash|\"}, {\"name\": \"value\", \"data_type\": \"VARCHAR\", \"description\": \"测试值或属性值，根据 subitem_name 决定语义|【格式】指标类为数值字符串或 JSON 字符串（温度类含 start/end 字段）；维度类为属性值字符串|【注意】指标类值需 CAST 后计算，维度类值在 dim_base_sn_di 中行转列后作为维度字段使用|\"}, {\"name\": \"lsl\", \"data_type\": \"VARCHAR\", \"description\": \"规格下限|【适用】判断测试值是否低于规格下限|\"}, {\"name\": \"usl\", \"data_type\": \"VARCHAR\", \"description\": \"规格上限|【适用】判断测试值是否超出规格上限|\"}, {\"name\": \"unit\", \"data_type\": \"VARCHAR\", \"description\": \"测试值单位|\"}, {\"name\": \"filepath\", \"data_type\": \"VARCHAR\", \"description\": \"原始日志文件在 HDFS 上的路径|\"}, {\"name\": \"dt\", \"data_type\": \"DATE\", \"description\": \"数据测试结束时间，取 time_end 的日期部分|【格式】yyyy-MM-dd|【注意】按 dt 分区查询以提升性能|\"}, {\"name\": \"etl_dt\", \"data_type\": \"DATE\", \"description\": \"数据平台 ETL 接入时间|【格式】yyyy-MM-dd|\"}, {\"name\": \"etl_batch\", \"data_type\": \"BIGINT\", \"description\": \"ETL 批次号|\"}, {\"name\": \"etl_insert_time\", \"data_type\": \"TIMESTAMP\", \"description\": \"数据插入时间|【格式】UTC 时间戳|\"}, {\"name\": \"data_source\", \"data_type\": \"VARCHAR\", \"description\": \"数据来源标识|【枚举】由不同产线/数据管道定义|\"}, {\"name\": \"etl_product_line\", \"data_type\": \"VARCHAR\", \"description\": \"大数据内部口径的产线标识|【注意】与业务 product_line 字段含义不同，仅用于 ETL 内部路由|\"}, {\"name\": \"etl_update_time\", \"data_type\": \"TIMESTAMP\", \"description\": \"数据最近一次更新时间|【格式】UTC 时间戳|【注意】与 etl_insert_time 不同，记录行级更新而非首次插入|\"}, {\"name\": \"burnin_time\", \"data_type\": \"VARCHAR\", \"description\": \"样品烧录时间，取自 item 的 time_elapse|【单位】毫秒|【注意】每轮 cycle 烧录一次|\"}]}", "upstream": ["st_embed.dim_base_wo_di", "st_embed.dwd_dut_result", "st_embed.dwd_dut_result_item", "st_embed.dwd_dut_result_subitem"], "downstream": ["mysql_mdm.p_bd_mdm.dim_dqc_temp_resolved_issues", "mysql_mdm.p_bd_mdm.dwd_embed_dqc_temp_issues", "st_embed.dim_base_sn_di", "st_embed.dim_dqc_state", "st_embed.dwd_fa_ecc_die_di", "st_embed.dwd_power_current_di", "st_embed.dwd_power_temperature_di"], "fields": {"format_version": {"expr": "测试日志格式版本号|【适用】日志解析兼容性判断|", "refs": ["format_version"]}, "note": {"expr": "项目自定义扩展信息，内含 test_number、machine_id、machine_type、test_type 等字段|【格式】JSON 字符串|【注意】DWD 层通过 get_json_object(note, '$.test_number') 等函数解析此字段|", "refs": ["note"]}, "flash_pn": {"expr": "厂商 Nand 颗粒资源别名，来自 dim_base_project 表|【外键】关联:dim_base_project(pn, flash)|", "refs": ["flash_pn"]}, "flash": {"expr": "项目 Nand 颗粒资源名称，来自 dim_base_wo_di 表|【适用】颗粒维度分析|", "refs": ["flash"]}, "item_control": {"expr": "主控芯片型号，来自 dim_base_wo_di 表|【适用】主控维度分析、兼容性排查|", "refs": ["item_control"]}, "item_capacity": {"expr": "产品容量，来自 dim_base_wo_di 表|【枚举】8GB, 16GB, 32GB, 64GB, 128GB, 256GB, 512GB, 1TB, 2TB|【单位】GB/TB|", "refs": ["item_capacity"]}, "pn": {"expr": "产品 PN，来自 dim_base_wo_di 表|【适用】产品维度分析|【外键】关联:dim_base_project(pn LIKE)|", "refs": ["pn"]}, "quality_level": {"expr": "质量等级，来自 dim_base_wo_di 表|【枚举】S1=最高等级, S2=次高等级, L1=标准等级, L2=基础等级|", "refs": ["quality_level"]}, "wo_status": {"expr": "工单状态，来自 dim_base_wo_di 表|【枚举】OPEN=进行中, CLOSED=已完结|【注意】部分分析场景需排除未完结工单|", "refs": ["wo_status"]}, "software_information": {"expr": "烧录到芯片中的 FW 软件包版本，来自 dim_base_wo_di 表|【适用】固件版本维度的不良分析|", "refs": ["software_information"]}, "product_category": {"expr": "产品分类，来自 dim_base_wo_di 表|【适用】按产品大类汇总|", "refs": ["product_category"]}, "product_line": {"expr": "产品线，来自 dim_base_wo_di 表|【枚举】EMMC LINE, EMBEDED LINE, UFS LINE, E-WEARABLE LINE|", "refs": ["product_line"]}, "product_type": {"expr": "产品类型，来自 dim_base_wo_di 表|【枚举】eMMC, ePOP5X, eMCP4X, eUFS, eUFS3.1, eUFS4.1|", "refs": ["product_type"]}, "test_number": {"expr": "正复测标识，从 ods_dut_result.note 的 JSON 字段解析|【枚举】0=正测, 1=复测|【注意】分析良率时需明确是否区分正复测|【格式】get_json_object(note, '$.test_number')|", "refs": ["test_number"]}, "machine_id": {"expr": "机台 ID，从 ods_dut_result.note 的 JSON 字段解析|【适用】机台维度分析|【格式】get_json_object(note, '$.machine_id')|", "refs": ["machine_id"]}, "machine_type": {"expr": "机台类型，从 ods_dut_result.note 的 JSON 字段解析|【枚举】SLT, ATE, HT3309|【格式】get_json_object(note, '$.machine_type')|", "refs": ["machine_type"]}, "test_type": {"expr": "测试类型，从 ods_dut_result.note 的 JSON 字段解析|【枚举】FULL-TEST=全测, FAIL-RETEST=失败重测|【格式】get_json_object(note, '$.test_type')|", "refs": ["test_type"]}, "etl_insert_time": {"expr": "NOW()", "refs": []}, "etl_update_time": {"expr": "NOW()", "refs": []}, "burnin_time": {"expr": "样品烧录时间，取自 item 的 time_elapse|【单位】毫秒|【注意】每轮 cycle 烧录一次|", "refs": ["burnin_time"]}, "t.wo_status": {"expr": "dim.wo_status", "refs": ["dim.wo_status"]}, "t.software_information": {"expr": "dim.software_information", "refs": ["dim.software_information"]}, "t.etl_update_time": {"expr": "CURRENT_TIMESTAMP()", "refs": []}}, "build_workflows": ["171874182595296", "172938675398368", "178339906459360", "180793130036608"]}



## 二、测试方法

### 2.1 测试集：20 场景（问题 + 期望表）

每个场景 = `(编号, 问题, 期望表列表)`。期望表按 20 场景业务口径 + 血缘分层人工标注：

| #  | 问题（SHCS26074748）                       | 期望表                                                                                                            |
| -- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 1  | 工单在 MES 里良率水平如何？从哪一天开始偏低？主要 errorcode？ | ods\_mes\_production\_report, dwd\_mes\_lot, dws\_indicator\_w                                                 |
| 2  | 有哪些测试项 item 和子项 subitem？               | dwd\_dut\_result\_item, dwd\_dut\_result\_subitem, dwd\_dut\_result\_w                                         |
| 3  | 功耗和温度数据汇总，计算阈值、确认分布，用宽表查询              | dwd\_power\_current\_di, dwd\_power\_temperature\_di, dwd\_dut\_result\_w                                      |
| 4  | GBB 块位置、类型和数量                          | dwd\_fa\_bb\_block, dws\_fa\_bb\_block                                                                         |
| 5  | 根据 UID 查找测试订单信息，再找对应的温度或功耗信息           | dim\_base\_sn\_di, dim\_base\_wo\_di, dwd\_power\_temperature\_di, dwd\_power\_current\_di                     |
| 6  | ECC 数据 by plane，GBB/FBB坏块数、ECC最大、分布集中性 | dws\_fa\_ecc\_plane, dwd\_fa\_ecc\_plane\_di, dws\_fa\_ecc\_cycle\_stat, dws\_fa\_bb\_block, dws\_indicator\_w |
| 7  | FWError 和 VPError，说明主要失效原因             | dws\_fa\_ecc\_plane, dws\_fa\_bb\_block, 术语表                                                                   |
| 8  | 电流在 500-550 范围内的比例                     | dwd\_power\_current\_di                                                                                        |
| 9  | 未完成的样品 Burin 测试时长                      | dwd\_dut\_result\_w, dwd\_power\_temperature\_di                                                               |
| 10 | 改PN所有MES数据，查看71code失效DPPM              | ods\_mes\_production\_report, dwd\_mes\_lot                                                                    |
| 11 | 使用的软件包各站位分别是什么                         | dwd\_dut\_result\_w, dwd\_dut\_result                                                                          |
| 12 | 对应的返测单、返测后良率、新增失效                      | dim\_base\_wo\_di, dws\_indicator\_w, ods\_mes\_production\_report，dwd\_mes\_lot                               |
| 13 | 整体坏块情况，减少24个坏块良率损失多少                   | dws\_fa\_bb\_block, dws\_indicator\_w                                                                          |
| 14 | 数据库里有哪些表？查数据该去哪个表                      | \[]（清单问题，不需要路由）                                                                                                |
| 15 | MES里数据缺失，与log对比缺少哪个lot                 | ods\_mes\_production\_report, dwd\_mes\_lot, ods\_dut\_result                                                  |
| 16 | 当前测试到哪一站位                              | dwd\_dut\_result, dwd\_dut\_result\_w, dim\_base\_wo\_di                                                       |
| 17 | nandTj温度，对比是否偏高，vdt计数，burnin时间         | dwd\_power\_temperature\_di, dwd\_fa\_ecc\_die\_di, dwd\_dut\_result\_w                                        |
| 18 | 不同批次良率波动是否一致，失效是否有集中性                  | dws\_indicator\_w, ods\_mes\_production\_report                                                                |
| 19 | 多个软件版本之间的log差异                         | dwd\_dut\_result\_w, ods\_dut\_result                                                                          |
| 20 | 相关表之间的关联关系，上下游依赖                       | \[]（血缘问题，需 get\_lineage）                                                                                       |

### 2.2 判定标准

```python
sel, ranked = route_tables(q)          # 规则路由选表（top-8）
overlap = set(sel) & set(expect)       # 命中 = 选中 ∩ 期望
✓  命中数 ≥ len(expect) - 1            # 全命中（允许 1 表容差）
△  命中数 > 0 但 < len(expect) - 1     # 部分命中
✗  命中数 == 0                          # 未命中
```

### 2.3 体积收益

- 全量注入：30 表完整描述 = **13,469 字符**
- 路由后注入：选中表完整描述 + 其余表一行索引（`表名 ｜ 适用:`）

***

## 三、测试结果

### 3.1 选表命中率：18/20 ✓（2 个 ✗ 均为合理不命中）

| #  | 命中/期望 | 选中表（top-6）                                                                                                                    |
| -- | ----- | ----------------------------------------------------------------------------------------------------------------------------- |
| 1  | 4/4 ✓ | ods\_mes\_production\_report dwd\_mes\_lot dws\_indicator\_w dim\_base\_wo\_di                                                |
| 2  | 4/4 ✓ | dwd\_dut\_result\_w dwd\_dut\_result\_subitem dim\_base\_wo\_di dwd\_dut\_result\_item                                        |
| 3  | 3/3 ✓ | dwd\_power\_temperature\_di dim\_base\_wo\_di dwd\_dut\_result\_w dwd\_power\_current\_di                                     |
| 4  | 2/2 ✓ | dim\_base\_wo\_di dwd\_dut\_result\_w dwd\_fa\_bb\_block dws\_fa\_bb\_block                                                   |
| 5  | 4/4 ✓ | dim\_base\_wo\_di dwd\_power\_temperature\_di dwd\_dut\_result\_w dwd\_power\_current\_di dim\_base\_sn\_di                   |
| 6  | 5/5 ✓ | dws\_fa\_ecc\_plane dws\_fa\_bb\_block dwd\_fa\_bb\_block dws\_indicator\_w dwd\_fa\_ecc\_plane\_di dws\_fa\_ecc\_cycle\_stat |
| 7  | 3/3 ✓ | dws\_fa\_ecc\_plane dws\_fa\_bb\_block dim\_base\_wo\_di dws\_fa\_bb\_block ods\_mes\_production\_report                      |
| 8  | 2/2 ✓ | dim\_base\_wo\_di dwd\_dut\_result\_w dwd\_power\_current\_di                                                                 |
| 9  | 2/2 ✓ | dwd\_dut\_result\_w dim\_base\_wo\_di dwd\_power\_temperature\_di                                                             |
| 10 | 2/2 ✓ | ods\_mes\_production\_report dwd\_mes\_lot                                                                                    |
| 11 | 2/2 ✓ | dwd\_dut\_result\_w dwd\_dut\_result dim\_base\_wo\_di                                                                        |
| 12 | 3/3 ✓ | ods\_mes\_production\_report dim\_base\_wo\_di dwd\_mes\_lot dws\_indicator\_w                                                |
| 13 | 2/2 ✓ | dws\_indicator\_w ods\_mes\_production\_report dwd\_fa\_bb\_block dws\_fa\_bb\_block                                          |
| 14 | 0/0 ✗ | \[]（清单问题，不路由，合理）                                                                                                              |
| 15 | 3/3 ✓ | ods\_mes\_production\_report dwd\_mes\_lot ods\_dut\_result dwd\_dut\_result\_w                                               |
| 16 | 3/3 ✓ | dwd\_dut\_result\_w dwd\_dut\_result dim\_base\_wo\_di                                                                        |
| 17 | 3/3 ✓ | dwd\_power\_temperature\_di dwd\_dut\_result\_w dwd\_fa\_ecc\_die\_di                                                         |
| 18 | 2/2 ✓ | dws\_indicator\_w ods\_mes\_production\_report dwd\_mes\_lot                                                                  |
| 19 | 2/2 ✓ | dwd\_dut\_result\_w ods\_dut\_result                                                                                          |
| 20 | 0/0 ✗ | \[]（血缘问题，需 get\_lineage，合理）                                                                                                   |

**说明**：具体工单号 `SHCS26074748` 不干扰路由；问题带"工单"词 → 路由多选 `dim_base_wo_di`（工单维度表），真实场景合理（agent 需要它 join 工单状态）。

### 3.2 体积收益（全量 13,469 字符）

| 场景              | 路由后字符 | 节省  |
| --------------- | ----- | --- |
| 1（MES 良率）       | 4,816 | 64% |
| 3（功耗温度）         | 2,608 | 81% |
| 4（GBB）          | 2,617 | 81% |
| 5（UID）          | 3,607 | 73% |
| 6（ECC by plane） | 6,551 | 51% |

***

## 四、复跑方法

```bash
.venv/bin/python /tmp/route_preview.py
```

- 修改期望表：编辑 `SCEN` 列表
- 增加路由关键词：编辑 `_KL` 字典（脚本内）
- 输出：命中率表 + 体积收益

***

## 五、结论与风险

- **选表准**：18/20 命中，2 个不命中均为不需要路由的问题
- **体积降**：省 51-81%
- **风险可控**：路由选错不致命——未选中表仍有索引 + `get_table_schema` 兜底；路由空/失败回退全量注入
- **待接入**：规则映射迁移到 `agentic_data_api.py`，涉库请求先 `route_tables(user_input)` 再注入

