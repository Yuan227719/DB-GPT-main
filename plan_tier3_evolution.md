# 方案设计稿：第三梯队进化（2026-08-14，纯设计未实施）

> 关联：`HANDOVER_20260814_agent_diagnosis.md`（证据与一二梯队 diff）
> 状态：设计稿，实施需用户确认。改 `dbgpt-core` 的 claude_skill 时注意这是共享包，
> 需跑 `make test` 相关单测（packages/dbgpt-core/tests 下如有 claude_skill 测试）。

---

## 一、trigger_keywords：触发词沉淀进 SKILL.md frontmatter

### 动机
第一梯队把触发词写死在 `agentic_data_api.py` 的 `_INDICATOR_TRIGGERS_*`。以后每加一个技能
都要改代码，且 `registry.match_skill` 的中文失效问题（证据 1）仍未修复。把触发词放进
SKILL.md frontmatter，一处修改同时解决两个问题。

### 关键事实（已核实 claude_skill/__init__.py）
1. `SkillMetadata` **已有 `triggers: Set[str]` 字段**（第 23 行），但解析器两处路径
   （YAML 路径 140-195、fallback 路径 196-248）**都从未填充它** —— 现成字段闲置。
2. YAML 路径已有 `to_list()` 助手（169-176），支持 `triggers: [a, b]` 与 `triggers: a,b` 两种写法。
3. `registry.match_skill` 调 `skill.matches(user_input)`（第 414 行）——修 `matches` 一处，
   match_skill 全线受益。

### 方案（3 处小改）
**① claude_skill/__init__.py 解析器（2 个路径各 +2 行）**
```python
# YAML 路径（约 178-181 行后）
_triggers = to_list(parsed.get("triggers"))
...
metadata = SkillMetadata(..., triggers={t for t in _triggers if t})
# fallback 路径同样处理（metadata_dict.get("triggers", "") 逗号切分）
```

**② FileBasedSkill.matches()（260-302 行）优先查 triggers，再走旧英文正则**
```python
def matches(self, user_input: str) -> bool:
    ui = (user_input or "").lower()
    for trig in self.metadata.triggers:
        t = str(trig).lower()
        if t.isascii():
            # 纯 ASCII 触发词（DPPM/FBB/burnin）→ 词边界匹配，避免撞型号名
            if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", ui):
                return True
        elif t in ui:  # 中文触发词 → 子串匹配（"本月良率趋势"命中"良率"）
            return True
    ...  # 原有 description 英文正则逻辑保留（英文技能兼容）
```
> 约定：**触发词是否为词边界匹配由 token 是否纯 ASCII 自动决定**，不需要复杂 schema。

**③ SKILL.md frontmatter 加 triggers（示例：indicator-calc）**
```yaml
---
name: indicator-calc
description: （保持一句话即可，300 字触发词长描述可从 description 移除，省 prompt）
triggers: [良率, 完结良率, 坏块比率, 箱线图, 箱型图, 周报, 日报, 失效, DPPM, FBB, FBC, burnin]
---
```
（直查词 坏块/ECC/温度/电流/烧录/老化/测试工单/测试样品 不进清单——由路由层负责，用户已确认）

**④ agentic_data_api.py 预匹配改通用扫描**（替换第一梯队 diff 中的 `_mentions_indicator`）
```python
if not pre_matched_skill and not file_path:
    matched = None
    for s in registry.list_skills():
        if s.metadata.triggers and s.matches(user_input):
            if matched is None or len(max(s.metadata.triggers, key=len)) > len(
                max(matched.metadata.triggers, key=len)
            ):
                matched = s  # 多个技能命中时取触发词更长的（更具体）
    if matched:
        pre_matched_skill = matched
        react_state["matched"] = matched
        react_state["skill_prompt"] = matched.get_prompt()
        logger.info(f"Auto pre-matched skill from triggers: {matched.metadata.name}")
```
> 收益：以后加技能只改 SKILL.md；match_skill 中文失效一并修复；Excel 等技能
> 若也写 triggers 可同样自动预匹配（文件上传场景仍需跳过规则）。

### 验证
- 单测：`FileBasedSkill.matches` 中文子串/英文边界/无 triggers 回退三组用例。
- 集成：`.venv/bin/python /tmp/route_skill_regression.py` 的 Part 2（7 题技能匹配）应全部翻转 PASS。

---

## 二、经验闭环 MVP：采集层设计（方案 7 第一步）

### 目标
落 `(问题, 路由表, 实际用表, SQL, 结果)` 记录，让 `_ROUTING_KEYWORDS` 靠数据迭代，
不再靠猜。**只做采集层，沉淀/应用层下一步再设计。**

### 数据模型（JSONL 追加，进程内 buffered flush）
文件：`/home/taoyuan/.dbgpt/workspace/route_feedback.jsonl`
```json
{
  "ts": "2026-08-14T17:00:00+08:00",
  "conv_id": "e2e0_1786694935",
  "question": "FL412E 工单各工序良率趋势...",
  "routed_tables": ["ods_mes_production_report", "dwd_mes_lot", ...],
  "skill_matched": null,
  "sqls": [
    {"sql": "SELECT ...", "tables": ["dim_base_wo_di"], "rows": 0, "err": null}
  ],
  "final_ok": true,
  "elapsed_s": 570
}
```

### 挂点（全部在 agentic_data_api.py 现有闭包里，无新依赖）
| 挂点 | 位置 | 记录 |
|---|---|---|
| 路由结果 | route_tables 调用后（2206）| routed_tables、skill_matched（预匹配名）|
| 每次 SQL | sql_query 工具（观察区）| sql、FROM 表名、行数/错误 |
| 会话结束 | terminate / 最终 view 落库处 | final_ok、elapsed_s |

### 聚合脚本（每周跑一次，设计稿）
```bash
.venv/bin/python /tmp/route_feedback_report.py
# 输出：每个路由词 → 命中问题数 / 实际查询表分布 / 从未被查的候选表
#       （例："工单" 路由 dim_base_wo_di 的问题里，实际只有 5% 查了它 → 建议删除）
```
> 实施注意：JSONL 只增不减；问题文本存原样（含工单号/PN，分析时脱敏再落报告）。

---

## 三、模型繁忙错误体验（handover 10.1 的设计落点）

### 现状问题
模型 429（"User concurrency limit reached"）或网关超时时，用户看到的是
"输出格式不正确/重试中" 之类的误导信息（handover 已列）。

### 设计
1. `llm_client.py` 错误路径：识别 `429` / `concurrency limit` / `timeout` / `connect`，
   抛带错误码的异常（如 `LLMServiceBusyError`，code="llm_busy"）。
2. `agentic_data_api.py`：捕获该异常 → SSE 推送一条 notice 事件
   （`{"type": "notice", "level": "error", "text": "模型服务繁忙（排队中），请稍候重试或错峰使用"}`）
   → 前端 notice 条展示，**不显示"格式不正确"**。
3. 前端 index.tsx：新增 notice 事件渲染（若尚无通用 notice 通道，复用现有错误条）。

> 与思考循环失控（证据 9）联动：thinking 超长截断时也应走同一 notice 通道提示
> "检测到模型思考循环，已自动重试"。

---

## 四、实施顺序建议
1. 第一梯队（路由+预匹配）→ 验证 → 第二梯队（工具瘦身）→ 验证
2. 第三梯队一（trigger_keywords）**与第一梯队技能预匹配存在替代关系**：
   - 若按第一梯队先上（写死词表），第三梯队一作为重构在验证后跟进；
   - 若用户愿意直接改 dbgpt-core，**跳过第一梯队的 _mentions_indicator，直接上第三梯队一**（更干净）。
3. 经验闭环采集层可在任一时点独立上（纯增量，不影响现有行为）。