# 交接文档：indicator-calc 指标技能构建 + 两个待修问题（skill 不触发 / 前端刷新丢消息）

> 项目：DB-GPT monorepo，`/v1/chat/react-agent`（半导体测试数据分析，st_embed / 商规EMBED）
> 关联：`HANDOVER_20260811_burnin.md`（burnin/路由/前端折叠）、`memory_duplication_analysis.md`（方案7经验闭环，设计已定稿但暂缓）
> 本会话：构建 indicator-calc 指标口径技能（已完成）→ 用户实测发现两个问题（skill 未触发、前端刷新后丢消息/思考气泡消失）→ **按用户要求停止改动，本文档交接待修项**

---

## 一、本会话已完成（indicator-calc 技能，全部已生效）

### 1. 技能骨架
`skills/indicator-calc/`，已被后端加载（`/api/v1/skills/list` 返回 11 个技能，含 indicator-calc，无 Unknown）：
```
SKILL.md                        # 触发词 + 使用流程（读口径→判断周期→查表/现算+讲算法）
references/（9 份，共 ~800 行）
  指标总览.md                    # 指标清单/落表/时间粒度/列命名
  良率.md                        # _mes_week + 完结良率 _finished_wo（15% 判定逻辑）
  FBB比率.md                     # _fbb_ratio_sn/_wo（_wo 即 FBB 箱线）
  DPPM-BIBB.md                   # _bibb_cnt_cycle / _week_dppm + Wilson-Hilferty 近似
  ECC坏块.md                     # FBB/GBB/HECC 哨兵码 + plane/die/cycle/block 层级
  箱线图.md                      # 落表(ads_fa_fbc wo_cycle) + 周ECC箱线(_ecc_slc/tlc/qlc_wo) + 现算(sn_cycle 多工单/多cycle/多批次)
  温度.md                        # _temp_week（>temp_cof 阈值分布）
  电流.md                        # _current_week（approx_percentile + mean/3σ/6σ，测项过滤按产品线）
  测试工单.md                    # _week_test（排除项目清单、flash 加号拆分）
  Spark转Trino.md                # 【现算必读】SparkSQL→TrinoSQL 转换（见下）
scripts/refresh_calc_docs.py     # Dolphin 拉 SQL→指纹→--check/--apply(LLM 重新提炼)
.doc_fingerprints               # 指纹文件（注意：无 .json 后缀，否则被技能 loader 误当技能=Unknown）
```

### 2. 关键口径要点（写进文档）
- **表里只有日（dws_indicator_d）/周（dws_indicator_w）预计算**；其他周期（月/自定义）按文档算法现算 + **必须向用户讲清算法**
- **权威来源 = DolphinScheduler 建表 SQL**：周报工作流 `174977160382176`（周良率/fbb指标/周dppm/周温度/周电流/to_slc·tlc·qlc_wo/周测试/周已完结工单）、主ETL `171874182595296`（to_dws_indicator_d_fbb/bibb、to_dws_ecc_*、to_dws_bb_block、to_ads_fbc_ecc_*_box）
- **BIBB/现算箱线去重逻辑（2026-08-11 变更）**：改为从 `dim_base_sn_di` 按 `(wo, efuse_id)` 取最新记录（`last_efuse_id_view`），`result_guid IN(...)` 过滤；旧逻辑是 cycle 表内 row_number 取 rn=1
- **箱线族差异**：落表=wo_cycle 累积计数精确分位；周ECC=sn_cycle 直接读不去重；现算=sn_cycle+去重；电流=approx_percentile 近似

### 3. SparkSQL→TrinoSQL（用户强调的关键约束）
Dolphin 建表是 **SparkSQL**，agent `sql_query` 走 **Kyuubi/Trino**。现算必须转换：
- `get_json_object`→`json_extract_scalar`、`to_json(named_struct)`→`json_format(cast(map(...)))`、`date_add(d,n)`→`date_add('day',n,d)`、`weekofyear`→`week`、`cast(int)`→`cast(integer)`、`posexplode`→`unnest with ordinality`
- **Spark UDF 在 Trino 不可用**：`udf_db.chi_square_inv` 用 **Wilson–Hilferty 近似**（`df·(1−2/(9df)+0.253347·√(2/(9df)))³`，df=2f+2，回答必须标"近似"）；`count_ecc_fast`/`group_ecc_by_plane` 等如实说算不了
- 查已预计算表（dws_indicator_d/w、ads_fa_fbc_cycle）不用转，直接 `json_extract_scalar` 取值

### 4. 修复：Unknown 技能
`.doc_fingerprints.json` 被技能 loader 当技能（递归扫 `.json/.yaml/.yml`，缺 name → "Unknown"）。改名 `.doc_fingerprints`（无后缀）后消失。

---

## 二、用户实测发现的两个问题（⏳ 未修，本会话停止改动）

### 问题 A：指标问题没有触发 indicator-calc 技能
**现象**：用户问「FL412E 项目工单 SHCS26074748 各工序良率趋势、errorcode 分布、坏块情况，做一份完整 HTML 报告」——含良率/坏块/errorcode，但 skill 没被调用，agent 直接 sql_query 探索表（查了 dim_base_wo_di、ods_mes_production_report）。

**已核实**：
- system prompt 技能清单**包含** indicator-calc（日志确认注入）✓
- 但 LLM 没调 `select_skill`/`get_skill_resource`，直接探索——**技能靠 LLM 自觉选择，不可靠**

**拟修复（待用户确认，未实施）**：加"指标问题**自动预匹配**"——问题命中强指标关键词时代码直接设 `pre_matched_skill=indicator-calc`，强制进技能模式（SKILL.md 核心流程生效）。
⚠️ 权衡：触发词里"工单/趋势/月"太宽泛，建议**只自动匹配强指标词**（良率/DPPM/FBB/坏块/ECC/温度/电流/burnin/烧录/老化/箱线图/测试工单/测试样品/周报/日报），宽泛词不自动匹配。
位置参考：`agentic_data_api.py:2255` `pre_matched_skill` 逻辑、`_mentions_excel`(2286)、`registry.match_skill`。

### 问题 B：前端刷新后丢消息 / 思考气泡消失 / 正在思考卡住
**现象（用户原话）**：
1. 刷新后**思考气泡消失**
2. **"正在思考"状态栏一直卡住不动**
3. **后端跑完后，前端会话消息直接全部消失**（最严重）

**已核实（后端/构建正常）**：
- 后端 `/live` 正常：运行中会话返回 10 个步骤（含 thought/action/todo_meta），running=true ✓（测试会话 `b7c3c74d-bd33-4d4e-864c-0568e1353961`）
- 部署构建最新（buildId `0k3C9_CV3puU4laTi0J5r`，index-391b45bd17cd0f34.js，Aug 11 10:46，源码 10:44）✓
- view payload 确实持久化 `steps`（`agentic_data_api.py:5369` history_payload 含 steps/task_plan/elapsed_seconds）
- 前端代码路径静态读正常：刷新→`loadConversation`(797)→`restoreFromHistory`(2210 解析 payload.steps 重建)→`checkLive`(2488 轮询 /live→renderLiveSteps)

**疑似根因（需下会话验证，未改）**：
- **"消息全消失"**最可能是**竞态**：`checkLive` 轮询到 `running=false`（`index.tsx:2538-2544`）→ 调 `loadConversation` 重载最终历史；若此刻 `run_agent` 的 view 还没落库（`agentic_data_api.py:5382 add_view_message` 在持久化收尾），历史接口返回空 → `setMessages([])`（`index.tsx:2592`）→ **消息全清空**。
  - 即：`_LIVE_AGENT_STEPS.pop(conv_id)`(5388) 与 `add_view_message`(5382) 之间，或 run_agent 持久化完成后 checkLive 重载的时间差，导致读到空历史。
- **"思考气泡消失/正在思考卡住"**：live 步骤的 `thought` 只在 step 完成时写入 history_steps；**正在思考的那一步**流式 thinking 不在 /live 返回里 → 刷新后当前步无思考内容；"正在思考"占位卡住可能因 running 判定/占位清理逻辑。

**复现信息待用户补充**：刷新时任务在跑还是已结束？右/左面板哪个空？

---

## 三、当前运行状态

- **后端运行中**：PID 需新会话确认（本次 `ps aux | grep "dbgpt start webserver"`），配置 `configs/openai.toml`，端口 5670
- **技能已加载**：`/api/v1/skills/list` = 11 个技能，indicator-calc 在列
- **代码改动**（未提交）：`skills/indicator-calc/**`（新建）、`web/pages/index.tsx`（Aug 11 10:44，本会话未动）、`agentic_data_api.py`（本会话未动，技能注入是既有机制）
- **指纹**：`.doc_fingerprints` 已初始化，`--check` 报"无变更"
- **Dolphin token**：从 connector_instance 解密（`_load_encrypt_key` 自动读 configs/openai.toml 的 encrypt_key）

---

## 四、如何重启 / 测试

### 技能加载验证
```bash
cd /home/taoyuan/projects/DB-GPT-main
curl -sk http://127.0.0.1:5670/api/v1/skills/list | grep indicator-calc   # 应命中
.venv/bin/python - <<'PY'   # 本地加载验证
import sys; sys.path.insert(0,"packages/dbgpt-core/src")
from dbgpt.configs.model_config import SKILLS_DIR
from dbgpt.agent.skill.loader import SkillLoader
print([s.metadata.name for s in SkillLoader().load_skills_from_directory(SKILLS_DIR, recursive=True)])
PY
```

### 口径文档刷新（Dolphin 改了 SQL 后）
```bash
cd /home/taoyuan/projects/DB-GPT-main
.venv/bin/python skills/indicator-calc/scripts/refresh_calc_docs.py --check  # 看哪些过期
.venv/bin/python skills/indicator-calc/scripts/refresh_calc_docs.py --apply  # LLM 重新提炼（人工 review 后再启用）
```

### 指标问答实测
```bash
# 发指标问题（如"上周 FBB 比率分布""某工单 DPPM"），看 agent 是否：
#   1) 读 indicator-calc 口径文档（get_skill_resource）
#   2) 现算时正确转 Trino、讲清算法
# 注意：当前已知 skill 可能不被自动触发（问题 A）
```

---

## 五、关键文件索引

| 文件 | 作用 |
|---|---|
| `skills/indicator-calc/SKILL.md` | 触发词 + 使用流程 + 硬规则（含 Spark→Trino、UDF 限制） |
| `skills/indicator-calc/references/*.md` | 9 份口径文档（见第一节） |
| `skills/indicator-calc/scripts/refresh_calc_docs.py` | Dolphin 拉 SQL→指纹→--check/--apply 刷新 |
| `skills/indicator-calc/.doc_fingerprints` | 指纹（无 .json 后缀，防被当技能） |
| `agentic_data_api.py:2255` | `pre_matched_skill` 技能预匹配（问题 A 修复点） |
| `agentic_data_api.py:5369-5388` | view payload 持久化 + `_LIVE_AGENT_STEPS.pop`（问题 B 竞态点） |
| `agentic_data_api.py:6166` | `/v1/chat/dialogue/live` 端点（已验证正常） |
| `web/pages/index.tsx:2488/2538/2592` | checkLive 轮询 / running=false 重载 / 空历史清消息（问题 B 疑似根因） |
| `web/pages/index.tsx:2210` | restoreFromHistory（解析 payload.steps 重建） |

---

## 六、给新会话的下一步建议

1. **优先修问题 B（前端丢消息，最严重）**：验证竞态假设——`checkLive` 在 running=false 时 `loadConversation` 重载，若 view 未落库会读到空历史 `setMessages([])`。修复方向：重载前先确认 view 已落库（或重试/延迟），或 loadConversation 空历史时不盲目清空已有消息。
2. **修问题 A（skill 不触发）**：加"强指标词自动预匹配 indicator-calc"（见第二节方案，待用户确认匹配词范围）。
3. **问题 B 的思考气泡**：live 步骤不含"正在思考"那一步的流式 thinking；若要刷新后也显示实时思考，需把 thinking_chunk 增量也写进 history_steps 当前步。
4. **既有待办**：方案 7 经验闭环（攒10/人工确认/flow，设计已定稿暂缓，见 `project_memory_duplication_todo.md`）。
