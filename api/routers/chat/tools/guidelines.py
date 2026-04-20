"""Clinical guidelines tools — read-only SQLite queries against
``guidelines.db`` (separate from the CRM database)."""

from __future__ import annotations

import logging
import sqlite3
import threading

from config import GUIDELINES_DB_PATH
from crm_store import LIKE_ESCAPE, like_contains

logger = logging.getLogger(__name__)

# Open once, share across tool calls. SQLite in read-only URI mode supports
# concurrent reads safely; use a lock around cursor use to keep sqlite3's
# per-connection state consistent under asyncio.to_thread dispatch.
_conn: sqlite3.Connection | None = None
_conn_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection | None:
    global _conn
    if _conn is not None:
        return _conn
    try:
        c = sqlite3.connect(
            f"file:{GUIDELINES_DB_PATH}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        c.row_factory = sqlite3.Row
        _conn = c
        return _conn
    except sqlite3.OperationalError:
        logger.warning("Guidelines database not available at %s", GUIDELINES_DB_PATH)
        return None


def _guidelines_query(sql: str, params: tuple = ()) -> list[dict]:
    conn = _get_conn()
    if conn is None:
        return [{"error": "Guidelines database not found"}]
    with _conn_lock:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_treatment_guidelines(disease="", line="", source="", limit=20):
    conds = [f'g."疾病" LIKE ? {LIKE_ESCAPE}']
    params: list = [like_contains(disease)]
    if line:
        conds.append(f'r."治疗线" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(line))
    if source:
        conds.append(f'g."指南来源" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(source))
    where = " AND ".join(conds)
    sql = f'''
        SELECT g."疾病", g."疾病亚型", g."指南来源", g."版本", g."发布年份",
               r."治疗线", r."推荐等级", r."证据级别", r."药物", r."药物类型",
               r."给药方案", r."适应条件", r."适应人群", r."疗效概述", r."不良反应", r."备注"
        FROM "推荐" r
        JOIN "指南" g ON r."指南ID" = g."记录ID"
        WHERE {where}
        ORDER BY g."疾病", r."治疗线", r."推荐等级"
        LIMIT ?
    '''
    params.append(min(limit, 50))
    return _guidelines_query(sql, tuple(params))


def query_biomarker(disease="", biomarker=""):
    conds = [f'"疾病" LIKE ? {LIKE_ESCAPE}']
    params: list = [like_contains(disease)]
    if biomarker:
        conds.append(f'"标志物" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(biomarker))
    where = " AND ".join(conds)
    sql = f'''
        SELECT "疾病", "标志物", "检测方法", "阳性阈值", "临床意义", "指南来源", "最近更新"
        FROM "生物标志物"
        WHERE {where}
        ORDER BY "疾病", "标志物"
        LIMIT 30
    '''
    return _guidelines_query(sql, tuple(params))


def list_guidelines(disease="", source=""):
    conds: list[str] = []
    params: list = []
    if disease:
        conds.append(f'"疾病" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(disease))
    if source:
        conds.append(f'"指南来源" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(source))
    where = " AND ".join(conds) if conds else "1=1"
    sql = f'''
        SELECT "疾病", "疾病亚型", "指南来源", "版本", "发布年份", "URL"
        FROM "指南"
        WHERE {where}
        ORDER BY "疾病", "指南来源"
        LIMIT 50
    '''
    return _guidelines_query(sql, tuple(params))


# ─────────────────────────────────────────────────────────────
# Schemas + implementation map
# ─────────────────────────────────────────────────────────────

SCHEMAS = [
    {
        "name": "query_treatment_guidelines",
        "description": (
            "Query clinical treatment guidelines by disease. Returns recommended "
            "drugs by treatment line with evidence grade. Covers NCCN, CSCO, ESMO, "
            "and 20+ guideline sources across 74 diseases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "disease": {"type": "string", "description": "Disease name in Chinese or English, e.g. '非小细胞肺癌', 'NSCLC', 'breast cancer', '乳腺癌'"},
                "line": {"type": "string", "description": "Treatment line filter, e.g. '一线', '二线', '三线'. Omit for all lines."},
                "source": {"type": "string", "description": "Guideline source filter, e.g. 'NCCN', 'CSCO', 'ESMO'. Omit for all sources."},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["disease"],
        },
    },
    {
        "name": "query_biomarker",
        "description": (
            "Query biomarker information for a disease — testing methods, positive "
            "thresholds, clinical significance. Covers 379 biomarker records from "
            "major guidelines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "disease": {"type": "string", "description": "Disease name, e.g. '非小细胞肺癌', 'breast cancer'"},
                "biomarker": {"type": "string", "description": "Optional: specific biomarker name, e.g. 'PD-L1', 'EGFR', 'HER2'. Omit for all biomarkers."},
            },
            "required": ["disease"],
        },
    },
    {
        "name": "list_guidelines",
        "description": (
            "List available clinical guidelines by disease or source. Shows guideline "
            "name, source (NCCN/CSCO/ESMO), version, and year. Use this when the user "
            "asks 'what guidelines are available for X?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "disease": {"type": "string", "description": "Disease name filter. Omit for all diseases."},
                "source": {"type": "string", "description": "Source filter (NCCN/CSCO/ESMO/etc). Omit for all sources."},
            },
        },
    },
]


IMPLS = {
    "query_treatment_guidelines": query_treatment_guidelines,
    "query_biomarker": query_biomarker,
    "list_guidelines": list_guidelines,
}
