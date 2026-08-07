# 20 场景测试结果

## 场景1: MES 历史良率 ✅ PASS
- 问题: FL412E 项目 2026-07-27 至 2026-08-02 共生产了几笔工单？良率水平如何？从哪一笔开始偏低？主要 errorcode 是什么？
- 最终结果: 干净结构化答案（12 笔工单、良率 97.9-100%、819/402 errorcode）
- 步骤: 22 步，0 失败
- 修复的代码 bug: (1) 解析器加 DSML 格式转换; (2) 循环结束时 final 提取"最终答案"段
- 质量备注: 14 次 sql_query 探索偏慢（语义层优化点）
- 模型稳定性: 波动（2次早退后成功）

## 场景2: 宽表测项 item/subitem ⚠️ SEMANTIC
- 问题: FL412E 工单有哪些测试项 item 和子项 subitem？
- 结果: 完成（2步），但模型在确认 FL412E 是项目还是工单，未找到测项
- 原因: dim_test_item 在 masterdata_db（跨 schema），不在 st_embed 表清单，agent 查不到
- 语义层需求: 跨 schema 业务字典表（dim_test_item）需加入可查范围/表适用场景建设

## 场景3: UFS 功耗/温度汇总 ⚠️ SEMANTIC
- 问题: UFS 试产段的功耗和温度数据汇总，计算阈值、确认分布，用宽表查询
- 结果: 完成（20步，0失败），但未拿到有效功耗/温度数据，final 停在"现在生成HTML报告"未真正渲染
- 原因: UFS 试产段功耗/温度口径需业务知识；agent 12 次 sql_query 探索慢
- 质量备注: 模型宣布生成HTML但未调用 code_interpreter/html_interpreter 就终止

## 场景4: UFS GBB 位置/类型/数量 ❌ 早退
- 问题: 调取 FL412E 的 GBB 块位置、类型和数量
- 结果: 1步就终止（只看 dwd_fa_bb_block 表结构），未查询实际 GBB 数据
- 原因: 模型过早 terminate（拿到 schema 就停），答案不完整
- 质量备注: 模型早退（仅1步+final是schema思考文本）— 重复出现的模型行为问题

## 场景5: UFS UID 搜寻 ⚠️ SEMANTIC
- 问题: 根据 UID 查找测试订单信息，再找对应的温度或功耗信息
- 结果: 1步（get_table_schema）后，模型第2轮只输出Thought（"用户没给具体UID值"），无Action → agent当terminate结束
- 原因: 问题未指定具体 UID；模型纯思考轮（无Action）被当作terminate
- 语义层需求: 需具体 UID 或让 agent 反问澄清
- 质量备注: "纯思考轮(无Action)→terminate"行为 — 重复出现

## 场景6: ECC by plane（待跑）

## 场景6: ECC by plane ⚠️ SEMANTIC
- 问题: 查看某片样品的 ECC 数据 by plane，GBB/FBB坏块数、ECC最大、分布集中性
- 结果: 11步（7次code_interpreter），遇代码错误（变量名desc/feature）后终止，未完成分析
- 原因: GBB/FBB坏块定义需业务口径；模型遇代码错误就终止未修复
- 语义层需求: 坏块定义（GBB/FBB）业务口径
- 质量备注: 遇代码错误就终止（未自行修复重试）— 重复出现

## 场景7: Error 含义（FWError/VPError）⚠️ SEMANTIC
- 问题: 找某片样品的 FWError 和 VPError，说明主要失效原因
- 结果: 3次 get_glossary_term，未找到 FWError/VPError 含义，模型终止
- 原因: FWError/VPError 语义需知识库/errorcode字典（跨schema embed_db.dim_errorcode_information）；未指定具体样品
- 语义层需求: errorcode 字典接入知识库

## 场景8: 电流分布 ✅ PASS（格式备注）
- 问题: 查看某工单电流在 500-550 范围内的比例
- 结果: 4步，算出答案"工单 SHCS26072090 电流500-550范围比例 5.6%"
- 质量备注: 答案正确，但 final 是原始 Thought 文本（答案嵌在思考里，非干净 terminate result）— 重复出现的模型格式问题

## 场景9: Burin 测试时长 ⚠️ SEMANTIC
- 问题: 查看 91-0DRDT 未完成的样品 Burin 测试时长
- 结果: 2步（get_table_schema+sql_query），查询返回空结果后终止
- 原因: Burin 时长需业务口径（91-0D等子项），且 91-0DRDT 工单/样品可能不存在
- 语义层需求: Burin 时长业务口径（dwd_dut_result_w BurnIn subitem）

## 场景10: 71code 失效 DPPM ⚠️ SEMANTIC
- 问题: 拉取历史改PN所有MES数据，查看71code失效DPPM
- 结果: 8步，遇SQL错误（CTE别名）后终止，未算出DPPM
- 原因: DPPM 需跨schema errorcode字典；模型遇SQL错误就终止未修复
- 语义层需求: errorcode字典跨schema接入
- 质量备注: 遇SQL错误就终止 — 重复出现的模型行为

## 场景11: 软件包 per 站位 ✅ PASS
- 问题: 查看某笔工单使用的软件包各站位分别是什么
- 结果: 7步，查到工单 LCG26074428 软件包 EMC9N82_128G_V2.7.3 各站位分布，final 干净
- 质量备注: 5次sql_query探索

## 场景12: 工单测试前后数据（返测）⚠️ SEMANTIC
- 问题: 查看该工单对应的返测单、返测后良率、新增失效
- 结果: 0步，模型反问"请提供具体工单号（wo）"（问题欠指定，模型行为合理）
- 原因: 未指定具体工单；返测业务逻辑（dim_base_wo_di wo_status）不在任何地方
- 语义层需求: 返测单业务逻辑

## 场景13: 坏块分布/减24块 ⚠️ SEMANTIC
- 问题: 统计一个资源整体坏块情况，如果减少24个坏块，良率会损失多少
- 结果: 13步，分析了工单 LCS26060992 整体坏块（有实质输出），但"减24块良率损失"预测未完整
- 原因: 减24块良率损失预测需业务推导（dws_fa_bb_block），语义层
- 质量备注: 11次sql_query探索

## 场景14: 新表去哪个表找 ✅ PASS
- 问题: 增加了新的表，查数据该去哪个表
- 结果: 1步，识别出 ads_fa_fbc_cycle 新表及其用途（表目录带描述生效）

## 场景15: MES 与 log 比对缺失 lot ✅ PASS（部分）
- 问题: MES里数据缺失，与log对比缺少哪个lot
- 结果: 8步，比较了 MES(lot=C26P...) vs log(dwd_dut_result lot=A5...) 格式差异，有实质分析
- 质量备注: 5次sql_query探索

## 场景16: 测试进展（站位）⚠️ SEMANTIC
- 问题: 这笔工单当前测试到哪一站位
- 结果: 0步，模型反问"请提供工单号（wo）"（欠指定，合理）

## 场景17: 温度分布（nandTj/vdt/burnin）⚠️ SEMANTIC
- 问题: 查某片样品的nandTj温度，对比是否偏高，vdt计数，burnin时间
- 结果: 1步，模型需具体样品标识（SN/WO/项目）后终止
- 原因: 未指定具体样品；nandTj/vdt/burnin 业务口径需知识

## 场景18: 批次差异 ❌ 早退
- 问题: 不同批次良率波动是否一致，失效是否有集中性
- 结果: 1步，遇"表不存在"错误后终止
- 原因: 模型先猜错表名，未完成批次分析

## 场景19: 版本差异 ❌ 早退
- 问题: 多个软件版本之间的log差异
- 结果: 1步，final是思考文本（模型只推理未查询）
- 原因: 问题较含糊（用户原注"没太明白"）；模型早退

## 场景20: 表关联/上下游 ⚠️ PARTIAL
- 问题: 询问表之间的关联关系，上下游依赖
- 结果: 11步，使用了 get_entity_lineage（MCP工具生效）分析血缘，但 HTML 报告未完成（"第一部分已写入"后终止）
- 语义层需求: 血缘分析可用，但报告生成被中断

---
# 汇总
- ✅ PASS: 1, 8, 11, 14, 15 (5个)
- ⚠️ SEMANTIC: 2, 3, 5, 6, 7, 9, 10, 12, 13, 16, 17 (11个)
- ❌ FAIL(早退): 4, 18, 19 (3个)
- ⚠️ PARTIAL: 20 (1个)
- 修复的代码bug: DSML格式转换、final提取"最终答案"段
- 重复模型质量问题: ①过早终止 ②答案嵌在Thought非clean terminate ③遇SQL/代码错误就终止 ④探索慢(10+ sql_query)
