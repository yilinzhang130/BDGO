"""Chat streaming endpoint — MiniMax API with tool use + document attachments."""

import json, logging, uuid
from pathlib import Path
import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from db import query, query_one, count
from config import (
    BP_DIR,
    MINIMAX_ANTHROPIC_VERSION,
    MINIMAX_KEY,
    MINIMAX_MODEL as MODEL,
    MINIMAX_URL,
)
from database import transaction
from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Postgres-backed session helpers
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, user_id: str) -> None:
    """Create the session row if it doesn't exist yet."""
    with transaction() as cur:
        cur.execute("SELECT id FROM sessions WHERE id = %s", (session_id,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO sessions (id, user_id, title) VALUES (%s, %s, %s)",
                (session_id, user_id, "New Chat"),
            )


def _load_history(session_id: str) -> list[dict]:
    """Load the last 20 messages for a session from Postgres.

    Messages are stored with role + content.  For assistant messages the
    content column holds a JSON-encoded list of content blocks (text /
    tool_use).  For user messages with tool_results, the content column
    holds the JSON-encoded list.
    """
    with transaction() as cur:
        cur.execute(
            "SELECT role, content, tools_json FROM messages "
            "WHERE session_id = %s ORDER BY created_at DESC LIMIT 20",
            (session_id,),
        )
        rows = cur.fetchall()

    # Rows come back newest-first; reverse to chronological order.
    rows.reverse()

    history: list[dict] = []
    for r in rows:
        content = r["content"]
        # Try parsing JSON content (structured content blocks / tool results)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                history.append({"role": r["role"], "content": parsed})
                continue
        except (json.JSONDecodeError, TypeError):
            pass
        history.append({"role": r["role"], "content": content})
    return history


def _save_message(session_id: str, role: str, content, tools_json: str | None = None,
                  attachments_json: str | None = None) -> None:
    """Persist a single message to Postgres."""
    if isinstance(content, (list, dict)):
        content_str = json.dumps(content, ensure_ascii=False, default=str)
    else:
        content_str = str(content) if content else ""

    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content, tools_json, attachments_json) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (uuid.uuid4().hex[:12], session_id, role, content_str, tools_json, attachments_json),
            )
            cur.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
    except Exception:
        logger.exception("Failed to save message for session %s", session_id)


def _save_entities(session_id: str, entities: list[dict]) -> None:
    """Upsert context entities extracted from tool results."""
    if not entities:
        return
    try:
        with transaction() as cur:
            params = [
                (e.get("id"), session_id, e.get("entity_type", ""),
                 e.get("title", ""), e.get("subtitle"),
                 json.dumps(e.get("fields", []), ensure_ascii=False) if e.get("fields") else None,
                 e.get("href"))
                for e in entities
            ]
            cur.executemany(
                """INSERT INTO context_entities (id, session_id, entity_type, title, subtitle, fields_json, href)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       entity_type = EXCLUDED.entity_type,
                       title = EXCLUDED.title,
                       subtitle = EXCLUDED.subtitle,
                       fields_json = EXCLUDED.fields_json,
                       href = EXCLUDED.href,
                       added_at = NOW()""",
                params,
            )
    except Exception:
        logger.exception("Failed to save entities for session %s", session_id)

SYSTEM_PROMPT = """你是 BD Go，生物医药BD智能助手。你可以访问以下只读工具：

**CRM 数据库工具**：
- search_companies / get_company: 搜索/获取公司信息
- search_assets / get_asset: 搜索/获取管线资产
- search_clinical: 搜索临床试验
- search_deals: 搜索BD交易
- search_patents: 搜索专利
- get_buyer_profile: 获取MNC买方画像
- count_by: 按字段统计
- search_global: 跨表模糊搜索

**临床指南数据库工具**（79条指南，611条推荐，379条生物标志物）：
- query_treatment_guidelines: 查询治疗指南推荐（按疾病、治疗线、指南来源）
- query_biomarker: 查询生物标志物（检测方法、阳性阈值、临床意义）
- list_guidelines: 列出可用的临床指南

**报告生成工具**（异步，返回任务ID + 下载链接）：
- generate_buyer_profile: 生成MNC买方画像Word报告
- research_disease: 生成赛道竞争格局调研报告
- analyze_ip: 生成专利景观分析报告
- analyze_target: 生成靶点竞争雷达报告
- analyze_paper: 生成文献分析/综述报告
- generate_guidelines_report: 生成临床指南简报

## 多步研究规划（Dispatch 模式）

当用户提出**复杂研究问题**（不是简单查数据）时，你应该自动规划多步工具调用：

**识别复杂问题的信号**：
- "帮我分析一下XX公司" → 需要 get_company + search_assets + search_deals + get_buyer_profile
- "XX赛道现在怎么样" → 需要 search_assets + search_clinical + query_treatment_guidelines + search_deals
- "XX靶点值不值得追" → 需要 search_assets + search_clinical + query_biomarker + search_deals
- "我要做XX的尽调" → 组合多个工具

**执行策略**：
1. 先判断用户意图属于哪类研究（公司/靶点/赛道/交易/临床/专利/文献）
2. 按逻辑顺序调用多个工具（先基础数据→再深入分析→最后综合判断）
3. 每一轮工具调用后检查是否有信息缺口（Coverage Check）
4. 如有缺口，补充调用（Gap Fill，最多补 2 轮）
5. 综合所有数据给出结构化答案

**研究类型→工具组合参考**：

| 研究类型 | 推荐工具组合 |
|---------|------------|
| 公司分析 | get_company → search_assets → search_deals → get_buyer_profile |
| 靶点评估 | search_assets(target=X) → search_clinical → query_biomarker → search_deals |
| 赛道调研 | search_assets(disease=X) → search_clinical → query_treatment_guidelines → search_deals |
| 交易分析 | search_deals → get_company(buyer) → get_company(seller) → search_assets |
| 临床评估 | search_clinical → search_assets → query_treatment_guidelines |
| 专利评估 | search_patents → search_assets → search_deals |

**如果用户问题简单（单一查询），直接调用一个工具即可，不需要规划。**

## 基本规则

1. 用户问数据时，**必须调用工具**而不是自己编答案
2. 用户问治疗方案/指南/biomarker时，优先用指南工具
3. 复杂研究问题 → 多步工具调用 → 综合分析
4. 如果可以用报告生成工具（generate_*）一步完成，推荐用户使用（更完整）
5. 工具返回后用中文简洁回答，引用具体数据和来源
6. 像资深BD同事一样沟通 — 专业但不啰嗦
7. 数据来源标注（如"来源：NCCN指南"、"来源：资产表"）
"""

# ── Tool definitions ─────────────────────────────────────────

TOOLS = [
    {
        "name": "search_companies",
        "description": "Search companies in CRM by name/country/type/disease. Returns top matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search keyword (matches company name)"},
                "country": {"type": "string", "description": "e.g. USA, China, Japan"},
                "type": {"type": "string", "description": "e.g. Biotech(USA), 海外药企"},
                "disease": {"type": "string", "description": "e.g. Oncology, Immunology"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_company",
        "description": "Get full details of one company by exact name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "search_assets",
        "description": "Search pipeline assets by company, phase, disease, target.",
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "company": {"type": "string"},
                "phase": {"type": "string", "description": "e.g. Phase 1, Phase 2, Phase 3, Commercial"},
                "disease": {"type": "string"},
                "target": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_asset",
        "description": "Get full details of one asset by name and company (composite key).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "company": {"type": "string"},
            },
            "required": ["name", "company"],
        },
    },
    {
        "name": "search_clinical",
        "description": "Search clinical trials by company/asset/phase/indication.",
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "company": {"type": "string"},
                "asset": {"type": "string"},
                "phase": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "search_deals",
        "description": "Search BD deals/transactions by buyer, seller, or deal type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "buyer": {"type": "string"},
                "seller": {"type": "string"},
                "type": {"type": "string", "description": "e.g. M&A, License, Collaboration"},
                "sort_by": {"type": "string", "enum": ["date", "upfront", "total"], "description": "Sort field"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "search_patents",
        "description": "Search patents by company, asset, or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "company": {"type": "string"},
                "status": {"type": "string", "description": "有效 / 已过期"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_buyer_profile",
        "description": "Get MNC buyer profile (DNA summary, BD theses, commercial capabilities) for a company.",
        "input_schema": {
            "type": "object",
            "properties": {"company": {"type": "string"}},
            "required": ["company"],
        },
    },
    {
        "name": "count_by",
        "description": "Count records grouped by a column. Use for aggregation questions like '按阶段统计资产数量'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "enum": ["公司", "资产", "临床", "交易", "IP"]},
                "group_by": {"type": "string", "description": "Column name to group by, e.g. 临床阶段, 疾病领域"},
            },
            "required": ["table", "group_by"],
        },
    },
    {
        "name": "search_global",
        "description": "Fuzzy search across all tables (companies + assets + clinical + deals + patents).",
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["q"],
        },
    },
    # ── Clinical Guidelines tools (from guidelines.db) ──
    {
        "name": "query_treatment_guidelines",
        "description": "Query clinical treatment guidelines by disease. Returns recommended drugs by treatment line with evidence grade. Covers NCCN, CSCO, ESMO, and 20+ guideline sources across 74 diseases.",
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
        "description": "Query biomarker information for a disease — testing methods, positive thresholds, clinical significance. Covers 379 biomarker records from major guidelines.",
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
        "description": "List available clinical guidelines by disease or source. Shows guideline name, source (NCCN/CSCO/ESMO), version, and year. Use this when the user asks 'what guidelines are available for X?'",
        "input_schema": {
            "type": "object",
            "properties": {
                "disease": {"type": "string", "description": "Disease name filter. Omit for all diseases."},
                "source": {"type": "string", "description": "Source filter (NCCN/CSCO/ESMO/etc). Omit for all sources."},
            },
        },
    },
]


# ── Tool implementations ─────────────────────────────────────

def _tool_search_companies(q="", country="", type="", disease="", limit=10):
    conds, params = [], []
    if q:
        conds.append('"客户名称" LIKE ?')
        params.append(f"%{q}%")
    if country:
        conds.append('"所处国家" = ?')
        params.append(country)
    if type:
        conds.append('"客户类型" = ?')
        params.append(type)
    if disease:
        conds.append('"疾病领域" LIKE ?')
        params.append(f"%{disease}%")
    where = " AND ".join(conds) if conds else "1=1"
    sql = f'SELECT "客户名称","客户类型","所处国家","疾病领域","核心产品的阶段","BD跟进优先级","公司质量评分" FROM "公司" WHERE {where} LIMIT ?'
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def _tool_get_company(name):
    return query_one('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))


def _tool_search_assets(q="", company="", phase="", disease="", target="", limit=10):
    conds, params = [], []
    if q:
        conds.append('("资产名称" LIKE ? OR "资产代号" LIKE ?)')
        params.extend([f"%{q}%", f"%{q}%"])
    if company:
        conds.append('"所属客户" LIKE ?')
        params.append(f"%{company}%")
    if phase:
        conds.append('"临床阶段" = ?')
        params.append(phase)
    if disease:
        conds.append('"疾病领域" LIKE ?')
        params.append(f"%{disease}%")
    if target:
        conds.append('"靶点" LIKE ?')
        params.append(f"%{target}%")
    where = " AND ".join(conds) if conds else "1=1"
    sql = f'SELECT "资产名称","所属客户","临床阶段","疾病领域","适应症","靶点","作用机制(MOA)","Q总分" FROM "资产" WHERE {where} LIMIT ?'
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def _tool_get_asset(name, company):
    return query_one('SELECT * FROM "资产" WHERE "资产名称" = ? AND "所属客户" = ?', (name, company))


def _tool_search_clinical(q="", company="", asset="", phase="", limit=10):
    conds, params = [], []
    if q:
        conds.append('("试验ID" LIKE ? OR "适应症" LIKE ?)')
        params.extend([f"%{q}%", f"%{q}%"])
    if company:
        conds.append('"公司名称" LIKE ?')
        params.append(f"%{company}%")
    if asset:
        conds.append('"资产名称" LIKE ?')
        params.append(f"%{asset}%")
    if phase:
        conds.append('"临床期次" = ?')
        params.append(phase)
    where = " AND ".join(conds) if conds else "1=1"
    sql = f'SELECT "记录ID","试验ID","公司名称","资产名称","适应症","临床期次","主要终点名称","结果判定","数据状态" FROM "临床_v3" WHERE {where} LIMIT ?'
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def _tool_search_deals(q="", buyer="", seller="", type="", sort_by="date", limit=10):
    conds, params = [], []
    if q:
        conds.append('"交易名称" LIKE ?')
        params.append(f"%{q}%")
    if buyer:
        conds.append('"买方公司" LIKE ?')
        params.append(f"%{buyer}%")
    if seller:
        conds.append('"卖方/合作方" LIKE ?')
        params.append(f"%{seller}%")
    if type:
        conds.append('"交易类型" LIKE ?')
        params.append(f"%{type}%")
    where = " AND ".join(conds) if conds else "1=1"
    order_col = {"date": "宣布日期", "upfront": "首付款($M)", "total": "交易总额($M)"}.get(sort_by, "宣布日期")
    sql = f'SELECT "交易名称","交易类型","买方公司","卖方/合作方","资产名称","首付款($M)","交易总额($M)","宣布日期","战略评分" FROM "交易" WHERE {where} ORDER BY "{order_col}" DESC LIMIT ?'
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def _tool_search_patents(q="", company="", status="", limit=10):
    conds, params = [], []
    if q:
        conds.append('"专利号" LIKE ?')
        params.append(f"%{q}%")
    if company:
        conds.append('"关联公司" LIKE ?')
        params.append(f"%{company}%")
    if status:
        conds.append('"状态" = ?')
        params.append(status)
    where = " AND ".join(conds) if conds else "1=1"
    sql = f'SELECT "专利号","专利持有人","关联公司","关联资产","到期日","状态","管辖区" FROM "IP" WHERE {where} LIMIT ?'
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def _tool_get_buyer_profile(company):
    return query_one('SELECT * FROM "MNC画像" WHERE "company_name" = ?', (company,))


def _tool_count_by(table, group_by):
    table_map = {"公司": "公司", "资产": "资产", "临床": "临床_v3", "交易": "交易", "IP": "IP"}
    physical = table_map.get(table, table)
    if table not in table_map:
        return {"error": f"Invalid table: {table}"}
    # Validate column name against actual table columns to prevent SQL injection
    try:
        cols = [r["name"] for r in query(f'PRAGMA table_info("{physical}")')]
    except Exception:
        cols = []
    if group_by not in cols:
        return {"error": f"Invalid column '{group_by}' for table '{table}'"}
    sql = f'SELECT "{group_by}" as value, COUNT(*) as count FROM "{physical}" WHERE "{group_by}" IS NOT NULL AND "{group_by}" != \'\' GROUP BY "{group_by}" ORDER BY count DESC LIMIT 50'
    try:
        return query(sql)
    except Exception as e:
        return {"error": str(e)}


def _tool_search_global(q, limit=5):
    results = {}
    results["companies"] = _tool_search_companies(q=q, limit=limit)
    results["assets"] = _tool_search_assets(q=q, limit=limit)
    results["deals"] = _tool_search_deals(q=q, limit=limit)
    results["clinical"] = _tool_search_clinical(q=q, limit=limit)
    return results


# ── Clinical Guidelines tools (guidelines.db) ───────────────

import os
import sqlite3 as _sqlite3

from config import GUIDELINES_DB_PATH as _GUIDELINES_DB


def _guidelines_query(sql: str, params: tuple = ()) -> list[dict]:
    """Query guidelines.db (separate from CRM). Returns list of dicts."""
    if not os.path.exists(_GUIDELINES_DB):
        return [{"error": "Guidelines database not found"}]
    conn = _sqlite3.connect(f"file:{_GUIDELINES_DB}?mode=ro", uri=True)
    conn.row_factory = _sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _tool_query_treatment_guidelines(disease="", line="", source="", limit=20):
    conds = ['g."疾病" LIKE ?']
    params: list = [f"%{disease}%"]
    if line:
        conds.append('r."治疗线" LIKE ?')
        params.append(f"%{line}%")
    if source:
        conds.append('g."指南来源" LIKE ?')
        params.append(f"%{source}%")
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


def _tool_query_biomarker(disease="", biomarker=""):
    conds = ['"疾病" LIKE ?']
    params: list = [f"%{disease}%"]
    if biomarker:
        conds.append('"标志物" LIKE ?')
        params.append(f"%{biomarker}%")
    where = " AND ".join(conds)
    sql = f'''
        SELECT "疾病", "标志物", "检测方法", "阳性阈值", "临床意义", "指南来源", "最近更新"
        FROM "生物标志物"
        WHERE {where}
        ORDER BY "疾病", "标志物"
        LIMIT 30
    '''
    return _guidelines_query(sql, tuple(params))


def _tool_list_guidelines(disease="", source=""):
    conds: list[str] = []
    params: list = []
    if disease:
        conds.append('"疾病" LIKE ?')
        params.append(f"%{disease}%")
    if source:
        conds.append('"指南来源" LIKE ?')
        params.append(f"%{source}%")
    where = " AND ".join(conds) if conds else "1=1"
    sql = f'''
        SELECT "疾病", "疾病亚型", "指南来源", "版本", "发布年份", "URL"
        FROM "指南"
        WHERE {where}
        ORDER BY "疾病", "指南来源"
        LIMIT 50
    '''
    return _guidelines_query(sql, tuple(params))


TOOL_IMPL = {
    "search_companies": _tool_search_companies,
    "get_company": _tool_get_company,
    "search_assets": _tool_search_assets,
    "get_asset": _tool_get_asset,
    "search_clinical": _tool_search_clinical,
    "search_deals": _tool_search_deals,
    "search_patents": _tool_search_patents,
    "get_buyer_profile": _tool_get_buyer_profile,
    "count_by": _tool_count_by,
    "search_global": _tool_search_global,
    # Guidelines tools
    "query_treatment_guidelines": _tool_query_treatment_guidelines,
    "query_biomarker": _tool_query_biomarker,
    "list_guidelines": _tool_list_guidelines,
}


# ── Auto-register report services as Chat tools ─────────────
# Each registered ReportService becomes a MiniMax tool.
# - async service: tool kicks off a task, returns task_id + a user-facing message
# - sync service: tool runs inline and returns the markdown preview
#
# Adding a new report in services/__init__.py automatically exposes it here.
try:
    from services import REPORT_SERVICES
    from services.report_builder import create_task, execute_task, get_task
    import threading as _threading

    def _make_report_tool(_svc):
        def _impl(**kwargs):
            task_id = create_task(_svc.slug, kwargs)
            if _svc.mode == "sync":
                execute_task(task_id, _svc, kwargs)
                t = get_task(task_id)
                if t["status"] == "completed":
                    result = t.get("result") or {}
                    return {
                        "task_id": task_id,
                        "status": "completed",
                        "markdown_preview": (result.get("markdown") or "")[:3000],
                        "files": result.get("files", []),
                        "message": f"Report generated. Download: {', '.join(f['download_url'] for f in result.get('files', []))}",
                    }
                return {
                    "task_id": task_id,
                    "status": t["status"],
                    "error": t.get("error"),
                }
            # Async: spawn thread, return immediately
            thread = _threading.Thread(
                target=execute_task,
                args=(task_id, _svc, kwargs),
                daemon=True,
            )
            thread.start()
            return {
                "task_id": task_id,
                "status": "queued",
                "estimated_seconds": _svc.estimated_seconds,
                "display_message": (
                    f"已开始 {_svc.display_name}（任务ID: {task_id}）。"
                    f"预计 {_svc.estimated_seconds} 秒完成。"
                    f"可在 Reports 页面查看进度与下载结果。"
                ),
            }
        return _impl

    for _svc in REPORT_SERVICES.values():
        TOOLS.append({
            "name": _svc.chat_tool_name,
            "description": _svc.chat_tool_description,
            "input_schema": _svc.chat_tool_input_schema,
        })
        TOOL_IMPL[_svc.chat_tool_name] = _make_report_tool(_svc)

    logger.info("Registered %d report services as Chat tools", len(REPORT_SERVICES))
except Exception as _e:
    logger.exception("Failed to register report services as Chat tools: %s", _e)


def _execute_tool(name: str, inp: dict) -> str:
    """Execute a tool and return JSON-serialized result (truncated for context)."""
    fn = TOOL_IMPL.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(**(inp or {}))
        s = json.dumps(result, ensure_ascii=False, default=str)
        if len(s) > 8000:
            s = s[:8000] + "\n...[truncated]"
        return s
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(e)})


# ── Context entity extraction ────────────────────────────────

import re as _re
from urllib.parse import quote as _quote


def _slugify(text: str) -> str:
    """Lowercase, strip punct/whitespace for dedup keys."""
    if not text:
        return ""
    t = _re.sub(r"\s+", "_", str(text).strip().lower())
    t = _re.sub(r"[^\w\u4e00-\u9fff_\-]", "", t)
    return t[:80]


def _format_field(label: str, value) -> dict | None:
    if value is None or value == "" or str(value).strip() in ("-", "None", "null"):
        return None
    s = str(value).strip()
    if len(s) > 60:
        s = s[:57] + "..."
    return {"label": label, "value": s}


def _entity_from_company(row: dict) -> dict | None:
    name = row.get("客户名称")
    if not name:
        return None
    fields = [
        _format_field("Country", row.get("所处国家")),
        _format_field("Type", row.get("客户类型")),
        _format_field("Stage", row.get("核心产品的阶段")),
        _format_field("Disease", row.get("疾病领域")),
        _format_field("BD Priority", row.get("BD跟进优先级")),
    ]
    fields = [f for f in fields if f]
    subtitle_parts = [row.get("所处国家"), row.get("客户类型")]
    subtitle = " · ".join([p for p in subtitle_parts if p])
    return {
        "type": "context_entity",
        "id": f"company:{_slugify(name)}",
        "entity_type": "company",
        "title": str(name),
        "subtitle": subtitle or None,
        "fields": fields,
        "href": f"/companies/{_quote(str(name), safe='')}",
    }


def _entity_from_asset(row: dict) -> dict | None:
    name = row.get("资产名称") or row.get("资产代号")
    company = row.get("所属客户")
    if not name:
        return None
    fields = [
        _format_field("Company", company),
        _format_field("Phase", row.get("临床阶段")),
        _format_field("Target", row.get("靶点")),
        _format_field("MOA", row.get("作用机制(MOA)")),
        _format_field("Q Score", row.get("Q总分")),
    ]
    fields = [f for f in fields if f]
    subtitle = company or row.get("疾病领域") or ""
    href = None
    if company and name:
        href = f"/assets/{_quote(str(company), safe='')}/{_quote(str(name), safe='')}"
    return {
        "type": "context_entity",
        "id": f"asset:{_slugify(f'{company}_{name}')}",
        "entity_type": "asset",
        "title": str(name),
        "subtitle": subtitle or None,
        "fields": fields,
        "href": href,
    }


def _entity_from_clinical(row: dict) -> dict | None:
    tid = row.get("试验ID") or row.get("记录ID")
    if not tid:
        return None
    fields = [
        _format_field("Company", row.get("公司名称")),
        _format_field("Asset", row.get("资产名称")),
        _format_field("Phase", row.get("临床期次")),
        _format_field("Indication", row.get("适应症")),
        _format_field("Result", row.get("结果判定")),
    ]
    fields = [f for f in fields if f]
    record_id = row.get("记录ID") or tid
    return {
        "type": "context_entity",
        "id": f"clinical:{_slugify(str(record_id))}",
        "entity_type": "clinical",
        "title": str(tid),
        "subtitle": row.get("公司名称") or None,
        "fields": fields,
        "href": f"/clinical/{_quote(str(record_id), safe='')}",
    }


def _entity_from_deal(row: dict) -> dict | None:
    name = row.get("交易名称")
    if not name:
        return None
    fields = [
        _format_field("Type", row.get("交易类型")),
        _format_field("Buyer", row.get("买方公司")),
        _format_field("Seller", row.get("卖方/合作方")),
        _format_field("Upfront", row.get("首付款($M)") and f"${row.get('首付款($M)')}M"),
        _format_field("Total", row.get("交易总额($M)") and f"${row.get('交易总额($M)')}M"),
        _format_field("Date", row.get("宣布日期")),
    ]
    fields = [f for f in fields if f]
    return {
        "type": "context_entity",
        "id": f"deal:{_slugify(str(name))}",
        "entity_type": "deal",
        "title": str(name),
        "subtitle": row.get("交易类型") or None,
        "fields": fields,
        "href": f"/deals/{_quote(str(name), safe='')}",
    }


def _entity_from_patent(row: dict) -> dict | None:
    pid = row.get("专利号")
    if not pid:
        return None
    fields = [
        _format_field("Holder", row.get("专利持有人")),
        _format_field("Company", row.get("关联公司")),
        _format_field("Asset", row.get("关联资产")),
        _format_field("Expiry", row.get("到期日")),
        _format_field("Status", row.get("状态")),
        _format_field("Region", row.get("管辖区")),
    ]
    fields = [f for f in fields if f]
    return {
        "type": "context_entity",
        "id": f"patent:{_slugify(str(pid))}",
        "entity_type": "patent",
        "title": str(pid),
        "subtitle": row.get("专利持有人") or None,
        "fields": fields,
        "href": f"/ip/{_quote(str(pid), safe='')}",
    }


def _entity_from_buyer(row: dict) -> dict | None:
    name = row.get("company_name")
    if not name:
        return None
    fields = [
        _format_field("Focus TA", row.get("focus_therapeutic_areas")),
        _format_field("Recent Deals", row.get("recent_deal_count")),
        _format_field("Strategy", row.get("bd_strategy")),
    ]
    fields = [f for f in fields if f]
    return {
        "type": "context_entity",
        "id": f"buyer:{_slugify(str(name))}",
        "entity_type": "buyer",
        "title": str(name),
        "subtitle": "MNC Buyer Profile",
        "fields": fields,
        "href": f"/buyers/{_quote(str(name), safe='')}",
    }


def _extract_context_entities(tool_name: str, raw_result_str: str) -> list[dict]:
    """Parse a tool's JSON result string and extract structured entities for the context panel."""
    if tool_name in ("count_by", "search_global"):
        return []
    try:
        data = json.loads(raw_result_str)
    except (json.JSONDecodeError, TypeError):
        return []

    # Single-row tools return a dict; search_* tools return a list
    rows: list[dict] = []
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        rows = [data]

    if not rows:
        return []

    # Cap at top-3 entities per tool call
    rows = rows[:3]

    extractors = {
        "search_companies": _entity_from_company,
        "get_company": _entity_from_company,
        "search_assets": _entity_from_asset,
        "get_asset": _entity_from_asset,
        "search_clinical": _entity_from_clinical,
        "search_deals": _entity_from_deal,
        "search_patents": _entity_from_patent,
        "get_buyer_profile": _entity_from_buyer,
    }

    fn = extractors.get(tool_name)
    if not fn:
        return []

    entities: list[dict] = []
    for r in rows:
        try:
            e = fn(r)
            if e:
                entities.append(e)
        except Exception as ex:
            logger.warning("Failed to extract entity from %s: %s", tool_name, ex)
    return entities


# ── Attachment text extraction ───────────────────────────────

def _extract_text(filename: str) -> str:
    """Extract text from PDF/PPTX/DOCX files in BP_DIR. Returns empty string on failure."""
    filepath = BP_DIR / Path(filename).name
    if not filepath.exists():
        return ""
    ext = filepath.suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            return "\n".join(page.extract_text() or "" for page in reader.pages)[:20000]
        elif ext in (".pptx", ".ppt"):
            from pptx import Presentation
            prs = Presentation(str(filepath))
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        parts.append(shape.text)
            return "\n".join(parts)[:20000]
        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(str(filepath))
            return "\n".join(p.text for p in doc.paragraphs)[:20000]
    except Exception as e:
        logger.warning("Failed to extract %s: %s", filename, e)
        return ""
    return ""


# ── Chat streaming ───────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    file_ids: list[str] = []
    # user_id is injected by the endpoint, not sent by the client
    user_id: str | None = None


async def _call_minimax_stream(client: httpx.AsyncClient, messages: list, tool_results_buffer: list):
    """Single call to MiniMax; yields SSE events and collects tool_use blocks."""
    body = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "max_tokens": 4096,
        "stream": True,
        "tools": TOOLS,
    }
    headers = {
        "x-api-key": MINIMAX_KEY,
        "Content-Type": "application/json",
        "anthropic-version": MINIMAX_ANTHROPIC_VERSION,
    }

    collected_content = []
    current_tool_use = None
    current_text = ""
    stop_reason = None

    async with client.stream("POST", MINIMAX_URL, json=body, headers=headers) as resp:
        if resp.status_code != 200:
            err = await resp.aread()
            yield ("error", f"API {resp.status_code}: {err.decode()[:300]}")
            return

        buffer = ""
        async for raw_chunk in resp.aiter_bytes():
            buffer += raw_chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                et = data.get("type", "")

                if et == "content_block_start":
                    block = data.get("content_block", {})
                    if block.get("type") == "tool_use":
                        current_tool_use = {
                            "id": block.get("id"),
                            "name": block.get("name"),
                            "input_json": "",
                        }
                        yield ("tool_call_start", {"name": block.get("name")})
                    elif block.get("type") == "text":
                        current_text = ""

                elif et == "content_block_delta":
                    delta = data.get("delta", {})
                    dt = delta.get("type", "")
                    if dt == "text_delta":
                        text = delta.get("text", "")
                        current_text += text
                        yield ("chunk", text)
                    elif dt == "input_json_delta" and current_tool_use is not None:
                        current_tool_use["input_json"] += delta.get("partial_json", "")

                elif et == "content_block_stop":
                    if current_tool_use is not None:
                        try:
                            inp = json.loads(current_tool_use["input_json"] or "{}")
                        except json.JSONDecodeError:
                            inp = {}
                        collected_content.append({
                            "type": "tool_use",
                            "id": current_tool_use["id"],
                            "name": current_tool_use["name"],
                            "input": inp,
                        })
                        tool_results_buffer.append(current_tool_use)
                        current_tool_use = None
                    elif current_text:
                        collected_content.append({"type": "text", "text": current_text})
                        current_text = ""

                elif et == "message_delta":
                    stop_reason = data.get("delta", {}).get("stop_reason")

                elif et == "message_stop":
                    break

    yield ("_end", {"stop_reason": stop_reason, "content": collected_content})


async def _stream_chat(req: ChatRequest):
    """Main chat handler: tool-use loop with streaming."""
    session_id = req.session_id
    user_id = req.user_id

    # Ensure session exists in Postgres (auto-create if needed)
    if user_id:
        _ensure_session(session_id, user_id)

    # Load history from Postgres instead of in-memory dict
    history = _load_history(session_id)

    user_text = req.message
    attachments_json = None
    if req.file_ids:
        attachment_parts = []
        for fid in req.file_ids:
            extracted = _extract_text(fid)
            if extracted:
                attachment_parts.append(f"\n\n[附件内容: {fid}]\n{extracted}")
        if attachment_parts:
            user_text = req.message + "".join(attachment_parts)
        attachments_json = json.dumps(req.file_ids)

    history.append({"role": "user", "content": user_text})
    if len(history) > 20:
        history[:] = history[-20:]

    # Persist the user message
    _save_message(session_id, "user", user_text, attachments_json=attachments_json)

    # Collect entities across all tool-call rounds for persistence
    all_entities: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            for _iteration in range(8):  # Up to 8 tool-call rounds for complex research
                tool_results_buffer = []
                final_content = None
                final_stop_reason = None

                async for event_type, payload in _call_minimax_stream(client, history, tool_results_buffer):
                    if event_type == "chunk":
                        yield f"data: {json.dumps({'type': 'chunk', 'content': payload})}\n\n"
                    elif event_type == "tool_call_start":
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': payload['name']})}\n\n"
                    elif event_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'message': payload})}\n\n"
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return
                    elif event_type == "_end":
                        final_content = payload["content"]
                        final_stop_reason = payload["stop_reason"]

                if final_content is None:
                    break

                history.append({"role": "assistant", "content": final_content})

                if final_stop_reason == "tool_use" and tool_results_buffer:
                    tool_results_msg = []
                    tool_events = []
                    for tu in tool_results_buffer:
                        try:
                            inp = json.loads(tu["input_json"] or "{}")
                        except json.JSONDecodeError:
                            inp = {}
                        result_str = _execute_tool(tu["name"], inp)
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': tu['name']})}\n\n"

                        # Collect tool event for persistence
                        tool_events.append({
                            "name": tu["name"],
                            "input": inp,
                            "result_preview": result_str[:500],
                        })

                        # Emit context_entity events for each extracted entity
                        for entity in _extract_context_entities(tu["name"], result_str):
                            yield f"data: {json.dumps(entity, ensure_ascii=False)}\n\n"
                            all_entities.append(entity)

                        tool_results_msg.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result_str,
                        })

                    # Persist the assistant message (with tool calls) and tool results
                    tools_json = json.dumps(tool_events, ensure_ascii=False, default=str)
                    _save_message(session_id, "assistant", final_content, tools_json=tools_json)
                    _save_message(session_id, "user", tool_results_msg)

                    history.append({"role": "user", "content": tool_results_msg})
                    continue
                else:
                    # Final assistant text (no more tool calls) — persist it
                    _save_message(session_id, "assistant", final_content)
                    break

        # Persist all extracted context entities
        _save_entities(session_id, all_entities)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except httpx.TimeoutException:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Request timed out'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        logger.exception("Chat error")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:500]})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("")
async def chat_stream(req: ChatRequest, user: dict = Depends(get_current_user)):
    req.user_id = user["id"]
    return StreamingResponse(
        _stream_chat(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
