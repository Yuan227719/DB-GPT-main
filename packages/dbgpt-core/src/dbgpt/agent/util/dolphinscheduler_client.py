"""DolphinScheduler 只读客户端 + 表/字段血缘解析。

从 DolphinScheduler 工作流定义（ETL SQL）解析表间血缘与字段级血缘，
支持"版本驱动增量刷新"：每次调用先拉一次全量工作流版本表（廉价），
对比缓存的版本指纹，只有版本变化的工作流才重拉 SQL 重解析，其余用缓存。

血缘来源是真实 ETL SQL（MERGE INTO 目标表 + USING 源表），不依赖
OpenMetadata（其血缘可能未构建）。

用法（agent 工具层）：
    cfg = _load_dolphinscheduler_config()          # 从 connector 解密凭证
    client = DolphinSchedulerClient(cfg)
    await client.ensure_fresh()                     # 版本对比 + 增量刷新
    info = await client.get_table_lineage("st_embed.dws_indicator_d")
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DolphinSchedulerConfig:
    enabled: bool = False
    server_uri: str = ""          # 如 https://dp-dolphin.longsys.com/dolphinscheduler
    project_code: str = ""        # 如 171521334547168
    token: str = ""
    header_name: str = "token"    # DS 3.x 用 token header 鉴权
    # 预构建好的 HTTP 头（优先于 token）
    headers: Optional[Dict[str, str]] = None


# 进程级缓存：{versions: {wf_code: version}, lineage: {table: {...}}}
_LINEAGE_CACHE: Dict[str, Any] = {"versions": {}, "lineage": {}}

# 忽略非生产/测试变体工作流的构建记录（血缘仍会包含，但标记非生产）
_TEST_KEYS = ("test", "import_", "临时", "TEST")


class DolphinSchedulerClient:
    def __init__(self, config: DolphinSchedulerConfig):
        self.config = config
        self._is_enabled = config.enabled and bool(config.server_uri)

    # ───────────────────────── HTTP ─────────────────────────
    def _build_headers(self) -> Dict[str, str]:
        if self.config.headers:
            return self.config.headers
        headers = {"Accept": "application/json"}
        if self.config.token:
            headers[self.config.header_name] = self.config.token
        return headers

    async def _get(self, path: str) -> Dict:
        import httpx

        url = self.config.server_uri.rstrip("/") + path
        headers = self._build_headers()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.json()

    # ───────────────────── 工作流信息 ─────────────────────
    async def get_workflow_versions(self) -> Dict[str, int]:
        """拉取项目下全部工作流的 {code: version}（一次分页请求，~0.2s）。"""
        if not self._is_enabled:
            return {}
        out: Dict[str, int] = {}
        try:
            r = await self._get(
                f"/projects/{self.config.project_code}/process-definition?pageNo=1&pageSize=100"
            )
            for w in (r.get("data") or {}).get("totalList") or []:
                code = str(w.get("code") or "")
                ver = w.get("version")
                if code and ver is not None:
                    out[code] = int(ver)
        except Exception as e:
            logger.warning(f"DolphinScheduler get_workflow_versions failed: {e}")
        return out

    async def get_workflow_tasks(self, wf_code: str) -> List[Dict]:
        """拉取某工作流全部任务定义（含 SQL）。"""
        if not self._is_enabled:
            return []
        try:
            r = await self._get(
                f"/projects/{self.config.project_code}/process-definition/{wf_code}/tasks"
            )
            return r.get("data") or []
        except Exception as e:
            logger.warning(f"DolphinScheduler get_workflow_tasks({wf_code}) failed: {e}")
            return []

    # ───────────────────── 血缘解析（sqlglot） ─────────────────────
    @staticmethod
    def _table_full(t) -> str:
        return ".".join(p for p in (t.catalog or "", t.db or "", t.name) if p)

    @staticmethod
    def _ref_cols(node) -> List[str]:
        cols = set()
        for c in (node.find_all(__import__("sqlglot").exp.Column) if node is not None else []):
            cols.add(".".join(str(p) for p in c.parts))
        return sorted(cols)

    @staticmethod
    def _expr_sql(node, limit: int = 150) -> str:
        if node is None:
            return ""
        s = node.sql()
        return s if len(s) <= limit else s[:limit] + "…"

    def _parse_task(self, task: Dict) -> Optional[Dict]:
        """解析单个 SQL 任务 → {target, sources, fields}。非 SQL 返回 None。"""
        if task.get("taskType") != "SQL":
            return None
        sql = (task.get("taskParams") or {}).get("sql") or ""
        if not sql.strip():
            return None
        try:
            from sqlglot import parse_one, exp

            ast = parse_one(sql, read="spark")
        except Exception:
            return None
        merge = ast.find(exp.Merge) if ast else None
        ctes = {c.alias for c in ast.find_all(exp.CTE)} if ast else set()
        target = None
        proj = None
        ins = None
        if merge is not None:
            target = self._table_full(merge.this)
            src = merge.args.get("using")
            if isinstance(src, __import__("sqlglot").exp.Subquery):
                proj = src.this
            elif isinstance(src, __import__("sqlglot").exp.Select):
                proj = src
        else:
            ins = ast.find(exp.Insert) if ast else None
            ct = ast.find(exp.Create) if ast else None
            if ins is not None:
                target = self._table_full(ins.this)
                proj = ins.expression if isinstance(ins.expression, exp.Select) else None
            elif ct is not None and ct.this is not None:
                target = ".".join(p for p in (ct.this.db or "", ct.this.name) if p)
                proj = ct.expression if isinstance(ct.expression, exp.Select) else None
        if not target:
            return None
        sources = sorted(
            set(
                self._table_full(x)
                for x in (ast.find_all(exp.Table) if ast else [])
                if self._table_full(x) and self._table_full(x) not in ctes and self._table_full(x) != target
            )
        )
        fields: Dict[str, Dict] = {}
        if merge is not None:
            if proj is not None and isinstance(proj, exp.Select):
                for p in proj.expressions:
                    name = p.alias_or_name
                    if not name:
                        continue
                    fields[name] = {
                        "expr": self._expr_sql(p.this if hasattr(p, "this") and p.this else p),
                        "refs": self._ref_cols(p),
                    }
            for when in merge.args.get("whens") or []:
                then = when.args.get("then")
                if isinstance(then, exp.Update):
                    for si in then.expressions:
                        left = (
                            ".".join(str(x) for x in si.this.parts)
                            if isinstance(si.this, exp.Column)
                            else si.this.sql()
                        )
                        fields[left] = {
                            "expr": self._expr_sql(si.expression),
                            "refs": self._ref_cols(si.expression),
                        }
                elif isinstance(then, exp.Insert) and then.expressions:
                    cols = [c.sql() for c in then.expressions]
                    val = then.expression
                    if isinstance(val, exp.Values):
                        vals = val.expressions
                        for i, c in enumerate(cols):
                            if i < len(vals):
                                fields[c] = {
                                    "expr": self._expr_sql(vals[i]),
                                    "refs": self._ref_cols(vals[i]),
                                }
        elif ins is not None and proj is not None:
            cols = [c.sql() for c in (ins.expressions or [])]
            ps = proj.expressions
            if len(cols) == len(ps):
                for c, p in zip(cols, ps):
                    fields[c] = {
                        "expr": self._expr_sql(p.this if hasattr(p, "this") and p.this else p),
                        "refs": self._ref_cols(p),
                    }
        return {"target": target, "sources": sources, "fields": fields}

    # ───────────────────── 增量刷新 ─────────────────────
    async def ensure_fresh(self, force: bool = False) -> None:
        """版本驱动增量刷新血缘缓存。

        拉取当前版本表 → 与缓存对比 → 只重拉版本变化的（首次/force 全量）。
        """
        if not self._is_enabled:
            return
        versions = await self.get_workflow_versions()
        if not versions:
            return  # 拉取失败，保留旧缓存
        cache = _LINEAGE_CACHE
        old_versions = cache.get("versions") or {}

        if force or not cache.get("lineage"):
            # 首次 / 强制：全量拉取解析
            changed = list(versions.keys())
        else:
            changed = [wf for wf, v in versions.items() if old_versions.get(wf) != v]

        if not changed:
            return  # 无变化，直接用缓存

        logger.info(
            f"DolphinScheduler lineage refresh: {len(changed)} workflows changed "
            f"(total {len(versions)})"
        )
        lineage = cache.get("lineage") or {}
        for wf_code in changed:
            tasks = await self.get_workflow_tasks(wf_code)
            # 先移除该工作流上次构建的表（避免旧表残留）
            wf_key = f"__wf_{wf_code}"
            for t, d in list(lineage.items()):
                if wf_key in (d.get("_build_wfs") or []):
                    if len(d["_build_wfs"]) == 1:
                        lineage.pop(t, None)
                    else:
                        d["_build_wfs"].remove(wf_key)
            for task in tasks:
                res = self._parse_task(task)
                if not res:
                    continue
                t = res["target"]
                d = lineage.setdefault(
                    t,
                    {"sources": set(), "fields": {}, "task": task.get("name", ""), "_build_wfs": set()},
                )
                d["sources"].update(res["sources"])
                d["_build_wfs"].add(wf_key)
                for col, info in res["fields"].items():
                    d["fields"].setdefault(col, info)
        # 序列化化缓存（set 转 list）
        cache["lineage"] = {
            t: {
                "sources": sorted(d["sources"]),
                "fields": {k: {"expr": v["expr"], "refs": v["refs"]} for k, v in d["fields"].items()},
                "task": d["task"],
                "_build_wfs": sorted(d["_build_wfs"]),
            }
            for t, d in lineage.items()
        }
        cache["versions"] = versions

    # ───────────────────── 查询 ─────────────────────
    async def get_table_lineage(self, table: str) -> Dict:
        """返回某表的上游/下游/字段级血缘。未找到返回空结构。

        表名兼容裸名与带 schema 前缀：精确未命中时按"以 table 结尾"模糊匹配
        （如 dim_base_wo_di → st_embed.dim_base_wo_di），下游匹配也基于解析后的
        完整表名，保证 upstream/downstream 一致。
        """
        await self.ensure_fresh()
        cache = _LINEAGE_CACHE.get("lineage") or {}
        entry = cache.get(table) or {}
        resolved = table
        if not entry:
            for k in cache:
                if k == table or k.endswith("." + table) or k.endswith(table):
                    resolved = k
                    entry = cache[k] or {}
                    break
        if not entry:
            return {"table": table, "upstream": [], "downstream": [], "fields": {}, "build_workflows": [], "found": False}
        # 直接上游
        upstream = entry.get("sources") or []
        # 下游：哪些表把本表当源（基于解析后的完整表名匹配）
        downstream = sorted(
            t for t, d in cache.items() if resolved in (d.get("sources") or [])
        )
        build_wfs = [w.replace("__wf_", "") for w in (entry.get("_build_wfs") or [])]
        return {
            "table": resolved,
            "upstream": upstream,
            "downstream": downstream,
            "fields": entry.get("fields") or {},
            "build_workflows": build_wfs,
            "found": True,
        }
