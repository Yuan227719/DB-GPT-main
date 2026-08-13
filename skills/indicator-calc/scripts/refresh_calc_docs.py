#!/usr/bin/env python3
"""指标口径文档刷新脚本（indicator-calc skill）

从 DolphinScheduler 拉取"建报表的 SQL"，与本地口径文档记录的来源指纹比对，
发现 SQL 变更后用 LLM 重新提炼指标口径文档，保证 references/*.md 与真实算法同步。

用法：
    python refresh_calc_docs.py --check   # 只检查变更，报告哪些文档过期（默认）
    python refresh_calc_docs.py --apply   # 对过期的文档用 LLM 重新提炼并写回
    python refresh_calc_docs.py --apply --all   # 强制重新提炼全部文档

连接方式（自动探测，按优先级）：
    1. 环境变量 DOLPHIN_SERVER / DOLPHIN_PROJECT / DOLPHIN_TOKEN
    2. connector_instance 表里的 dolphinscheduler connector（自动发现 + 解密 token，
       需在 DB-GPT 项目根目录下运行）
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

# ───────────────────────── 常量与配置 ─────────────────────────
SKILL_DIR = Path(__file__).resolve().parents[1]          # skills/indicator-calc/
REFERENCES_DIR = SKILL_DIR / "references"
# 注意：不能叫 .json/.yaml/.yml（技能 loader 会把 skills/ 下这些后缀的文件当技能，造成 "Unknown" 技能）。
# 用无后缀文件名存放指纹。
FINGERPRINT_FILE = SKILL_DIR / ".doc_fingerprints"

# Dolphin 默认地址（env 优先）
DOLPHIN_SERVER = os.environ.get("DOLPHIN_SERVER", "https://dp-dolphin.longsys.com/dolphinscheduler")
DOLPHIN_PROJECT = os.environ.get("DOLPHIN_PROJECT", "171521334547168")
DOLPHIN_TOKEN = os.environ.get("DOLPHIN_TOKEN", "")

# 建表工作流 → 任务 → 喂给哪份口径文档
# 每个条目: 文档名 → [(工作流code, 任务名, 备注)]
DOC_SOURCES = {
    "良率.md": [
        ("174977160382176", "周良率 指标-DWS层", "周良率（dws_indicator_w _mes_week）"),
        ("174977160382176", "周已完结工单 指标-DWS层", "完结良率（_finished_wo）"),
    ],
    "FBB比率.md": [
        ("171874182595296", "to_dws_indicator_d_fbb", "日表 fbb_ratio_sn"),
        ("171874182595296", "to_dws_indicator_d_fbb_abnormal", "日表 fbb_ratio_sn_abnormal"),
        ("174977160382176", "fbb 指标-DWS层", "周表 fbb_ratio_wo 分布"),
    ],
    "DPPM-BIBB.md": [
        ("171874182595296", "to_dws_indicator_d_bibb", "日表 bibb_cnt_cycle"),
        ("174977160382176", "周dppm", "周表 week_dppm"),
    ],
    "ECC坏块.md": [
        ("171874182595296", "to_dws_ecc_plane", "plane 级 ECC 分类"),
        ("171874182595296", "to_dws_bb_block", "block 级坏块"),
        ("171874182595296", "to_dws_ecc_die", "die 级聚合"),
        ("171874182595296", "to_dws_ecc_cycle", "cycle 级聚合"),
        ("174977160382176", "to_slc_wo", "周报 ECC 粒度"),
    ],
    "箱线图.md": [
        ("171874182595296", "to_ads_fbc_ecc_cycle_box", "cycle 级箱线 ECC_CYCLE"),
        ("171874182595296", "to_ads_fbc_ecc_wo_box", "WO 级箱线 ECC_WO"),
        ("174977160382176", "to_slc_wo", "周ECC箱线 _ecc_slc_wo"),
        ("174977160382176", "to_tlc_wo", "周ECC箱线 _ecc_tlc_wo"),
        ("174977160382176", "to_qlc_wo", "周ECC箱线 _ecc_qlc_wo"),
    ],
    "温度.md": [
        ("174977160382176", "周温度分布", "周温度分布"),
    ],
    "电流.md": [
        ("174977160382176", "周电流分布-DWS", "周电流箱线/分布"),
    ],
    "测试工单.md": [
        ("174977160382176", "周测试 指标-DWS层", "周测试工单/样品"),
    ],
}

# LLM 配置（Deepseek-V4-Flash，openai 兼容）
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://aicode.longsys.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "d57f6e3761e270cca9c58baeb32b86d04beeead1ee31f430f8dcd8684a590722b946cc95d23a597c5d2b03946baab892")
LLM_MODEL = os.environ.get("LLM_MODEL", "Deepseek-V4-Flash")


# ───────────────────────── Dolphin 连接 ─────────────────────────
def _load_encrypt_key() -> str:
    """从 configs/openai.toml 或 ENCRYPT_KEY 取加密密钥（解密 connector 凭证用）。"""
    env = os.environ.get("ENCRYPT_KEY", "")
    if env:
        return env
    import re

    for cfg_path in ("configs/openai.toml", "configs/connection_config.yaml", "configs/config.toml"):
        if not os.path.exists(cfg_path):
            continue
        text = Path(cfg_path).read_text()
        m = re.search(r"encrypt_key\s*=\s*[\"']([^\"']+)[\"']", text)
        if m:
            return m.group(1)
    return ""


def _load_token() -> str:
    if DOLPHIN_TOKEN:
        return DOLPHIN_TOKEN
    # 从 connector_instance 解密（需在项目根目录运行）
    try:
        import sqlite3
        from dbgpt.agent.resource.connector.credential import CredentialStore

        _key = _load_encrypt_key()
        if _key:
            os.environ.setdefault("ENCRYPT_KEY", _key)

        db_path = "pilot/meta_data/dbgpt.db"
        if not os.path.exists(db_path):
            return ""
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute(
            "SELECT config_json, encrypted_credentials, encryption_salt FROM connector_instance"
            " WHERE connector_type='dolphinscheduler' LIMIT 1"
        )
        row = cur.fetchone()
        db.close()
        if not row or not row[1]:
            return ""
        creds = CredentialStore(system_app=None).decrypt(row[1], row[2])
        return str(creds.get("token", ""))
    except Exception as e:
        print(f"[warn] connector token 解密失败: {e}", file=sys.stderr)
        return ""


def _dolphin_get(path: str) -> dict:
    token = _load_token()
    if not token:
        raise RuntimeError(
            "未找到 Dolphin token：设置环境变量 DOLPHIN_TOKEN，或在项目根目录运行以从 connector 解密"
        )
    url = f"{DOLPHIN_SERVER.rstrip('/')}/projects/{DOLPHIN_PROJECT}{path}"
    req = urllib.request.Request(url, headers={"token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def pull_source_sql() -> dict:
    """拉取 DOC_SOURCES 里所有建表 SQL，返回 {文档名: [sql, ...]}"""
    out: dict = {}
    for doc, items in DOC_SOURCES.items():
        sqls = []
        for wf_code, task_name, _note in items:
            try:
                tasks = _dolphin_get(f"/process-definition/{wf_code}/tasks").get("data") or []
                raw = next(
                    ((t.get("taskParams") or {}).get("sql") or "")
                    for t in tasks if t.get("name") == task_name
                )
                sqls.append(raw)
                print(f"  [ok] {doc} <- {wf_code}/{task_name} ({len(raw)} chars)")
            except StopIteration:
                print(f"  [!!] {doc} <- {wf_code}/{task_name} 未找到", file=sys.stderr)
            except Exception as e:
                print(f"  [!!] {doc} <- {wf_code}/{task_name} 拉取失败: {e}", file=sys.stderr)
        out[doc] = sqls
    return out


def fingerprint(sqls: list) -> str:
    """文档来源指纹 = 所有 SQL 拼接的 sha1。"""
    return hashlib.sha1("\n".join(sqls).encode()).hexdigest()


def load_old_fingerprints() -> dict:
    if FINGERPRINT_FILE.exists():
        return json.loads(FINGERPRINT_FILE.read_text())
    return {}


def save_fingerprints(fp: dict):
    FINGERPRINT_FILE.write_text(json.dumps(fp, ensure_ascii=False, indent=2))


# ───────────────────────── LLM 提炼 ─────────────────────────
def _sep_join(sqls: list) -> str:
    return "\n---\n".join(sqls)


def llm_distill(doc: str, sqls: list) -> str:
    """用 LLM 把建表 SQL 提炼成指标口径文档（markdown）。"""
    prompt = f"""你是半导体测试数据仓库专家。根据下面 DolphinScheduler 的建表 SQL，为指标「{doc.replace('.md','')}」生成一份中文指标口径文档。
要求严格参照现有 st_embed 口径文档的格式，包含以下小节：
1. 业务定义（这个指标是什么、落哪张表、indicator_name 形如什么、indicator_value 是什么 JSON）
2. 算法步骤（源表 → 过滤条件 → 聚合维度 → 指标公式，按步骤编号）
3. 直接查表 SQL（给出可直接运行的 SELECT 示例）
4. 现算算法（表里没有的时间周期如何按算法现算，给 SQL 示例）
5. 注意/陷阱（口径细节：阈值默认值、错误码过滤、去重、特殊 UDF 等）
只输出 markdown 正文，不要输出额外的解释。SQL 如下：
---
{_sep_join(sqls)}"""
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "你是严谨的半导体测试数据仓库口径专家，只输出口径文档正文。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{LLM_API_BASE}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return (data["choices"][0]["message"]["content"] or "").strip()


# ───────────────────────── 主流程 ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查变更（默认）")
    ap.add_argument("--apply", action="store_true", help="对变更文档用 LLM 重新提炼并写回")
    ap.add_argument("--all", action="store_true", help="忽略指纹，强制重新提炼全部")
    args = ap.parse_args()

    print("拉取 Dolphin 建表 SQL ...")
    sources = pull_source_sql()
    new_fp = {doc: fingerprint(sqls) for doc, sqls in sources.items()}
    old_fp = {} if args.all else load_old_fingerprints()

    stale = []
    for doc in DOC_SOURCES:
        if not sources.get(doc):
            print(f"  [!] {doc}: 无来源 SQL，跳过")
            continue
        if new_fp[doc] != old_fp.get(doc):
            stale.append(doc)

    if not stale:
        print("无变更，所有口径文档与 Dolphin 同步。")
        return

    print(f"\n以下文档来源 SQL 已变更（或首次运行）：{stale}")
    if not args.apply:
        print("运行 `refresh_calc_docs.py --apply` 用 LLM 重新提炼这些文档。")
        return

    for doc in stale:
        print(f"\n提炼 {doc} ...")
        try:
            md = llm_distill(doc, sources[doc])
            (REFERENCES_DIR / doc).write_text(md)
            print(f"  [ok] 已写回 {doc}（{len(md)} chars）")
        except Exception as e:
            print(f"  [!!] 提炼 {doc} 失败: {e}", file=sys.stderr)

    save_fingerprints(new_fp)
    print("\n指纹已更新。请人工 review 新生成的文档再启用（口径错误会误导回答）。")


if __name__ == "__main__":
    main()
