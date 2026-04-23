"""CRM search + lookup tools. Field-visibility enforcement happens
centrally in ``tools.registry._strip_tool_result`` after each function
returns."""

from __future__ import annotations

import logging

from auth_db import transaction
from crm_store import LIKE_ESCAPE, like_contains, query, query_one
from services.helpers.resolve import fuzzy_company_names, resolve_company, resolve_mnc

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# Companies
# ═════════════════════════════════════════════════════════════════


def search_companies(q="", country="", type="", disease="", limit=10):
    conds, params = [], []
    if q:
        conds.append(
            f'("客户名称" LIKE ? {LIKE_ESCAPE} OR "英文名" LIKE ? {LIKE_ESCAPE} OR "中文名" LIKE ? {LIKE_ESCAPE})'
        )
        params.extend([like_contains(q)] * 3)
    if country:
        conds.append('"所处国家" = ?')
        params.append(country)
    if type:
        conds.append('"客户类型" = ?')
        params.append(type)
    if disease:
        conds.append(f'"疾病领域" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(disease))
    where = " AND ".join(conds) if conds else "1=1"
    sql = (
        'SELECT "客户名称","客户类型","所处国家","疾病领域","核心产品的阶段",'
        '"BD跟进优先级","公司质量评分" '
        f'FROM "公司" WHERE {where} LIMIT ?'
    )
    params.append(min(limit, 30))
    rows = query(sql, tuple(params))

    # Fuzzy fallback: if name query returned nothing, try crm_match
    if not rows and q and not (country or type or disease):
        fuzzy_names = fuzzy_company_names(q, n=limit)
        if fuzzy_names:
            placeholders = ",".join("?" * len(fuzzy_names))
            rows = query(
                f'SELECT "客户名称","客户类型","所处国家","疾病领域","核心产品的阶段",'
                f'"BD跟进优先级","公司质量评分" '
                f'FROM "公司" WHERE "客户名称" IN ({placeholders})',
                tuple(fuzzy_names),
            )
            for r in rows:
                r["_fuzzy_match"] = True

    return rows


def get_company(name):
    result = resolve_company(name)
    if result.row:
        if result.fuzzy:
            result.row["_matched_as"] = result.canonical
        return result.row
    hint = (
        f"你是否是指：{', '.join(result.suggestions[:3])}？"
        if result.suggestions
        else "请检查公司名称拼写。"
    )
    return {"_not_found": True, "message": f"未找到公司 '{name}'。{hint}"}


# ═════════════════════════════════════════════════════════════════
# Assets
# ═════════════════════════════════════════════════════════════════


def search_assets(q="", company="", phase="", disease="", target="", limit=10):
    conds, params = [], []
    if q:
        conds.append(f'("资产名称" LIKE ? {LIKE_ESCAPE} OR "资产代号" LIKE ? {LIKE_ESCAPE})')
        params.extend([like_contains(q), like_contains(q)])
    if company:
        conds.append(f'"所属客户" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(company))
    if phase:
        conds.append('"临床阶段" = ?')
        params.append(phase)
    if disease:
        conds.append(f'"疾病领域" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(disease))
    if target:
        conds.append(f'"靶点" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(target))
    where = " AND ".join(conds) if conds else "1=1"
    sql = (
        'SELECT "资产名称","所属客户","临床阶段","疾病领域","适应症","靶点",'
        '"作用机制(MOA)","Q总分" '
        f'FROM "资产" WHERE {where} LIMIT ?'
    )
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def get_asset(name, company):
    return query_one(
        'SELECT * FROM "资产" WHERE "资产名称" = ? AND "所属客户" = ?',
        (name, company),
    )


# ═════════════════════════════════════════════════════════════════
# Clinical trials
# ═════════════════════════════════════════════════════════════════


def search_clinical(q="", company="", asset="", phase="", limit=10):
    conds, params = [], []
    if q:
        conds.append(f'("试验ID" LIKE ? {LIKE_ESCAPE} OR "适应症" LIKE ? {LIKE_ESCAPE})')
        params.extend([like_contains(q), like_contains(q)])
    if company:
        conds.append(f'"公司名称" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(company))
    if asset:
        conds.append(f'"资产名称" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(asset))
    if phase:
        conds.append('"临床期次" = ?')
        params.append(phase)
    where = " AND ".join(conds) if conds else "1=1"
    sql = (
        'SELECT "记录ID","试验ID","公司名称","资产名称","适应症","临床期次",'
        '"主要终点名称","结果判定","数据状态" '
        f'FROM "临床" WHERE {where} LIMIT ?'
    )
    params.append(min(limit, 30))
    return query(sql, tuple(params))


# ═════════════════════════════════════════════════════════════════
# Deals
# ═════════════════════════════════════════════════════════════════


def search_deals(q="", buyer="", seller="", type="", sort_by="date", limit=10):
    conds, params = [], []
    if q:
        conds.append(f'"交易名称" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(q))
    if buyer:
        conds.append(f'"买方公司" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(buyer))
    if seller:
        conds.append(f'"卖方/合作方" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(seller))
    if type:
        conds.append(f'"交易类型" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(type))
    where = " AND ".join(conds) if conds else "1=1"
    order_col = {"date": "宣布日期", "upfront": "首付款($M)", "total": "交易总额($M)"}.get(
        sort_by, "宣布日期"
    )
    sql = (
        'SELECT "交易名称","交易类型","买方公司","卖方/合作方","资产名称",'
        '"首付款($M)","交易总额($M)","宣布日期","战略评分" '
        f'FROM "交易" WHERE {where} ORDER BY "{order_col}" DESC LIMIT ?'
    )
    params.append(min(limit, 30))
    return query(sql, tuple(params))


# ═════════════════════════════════════════════════════════════════
# Patents
# ═════════════════════════════════════════════════════════════════


def search_patents(q="", company="", status="", limit=10):
    conds, params = [], []
    if q:
        conds.append(f'"专利号" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(q))
    if company:
        conds.append(f'"关联公司" LIKE ? {LIKE_ESCAPE}')
        params.append(like_contains(company))
    if status:
        conds.append('"状态" = ?')
        params.append(status)
    where = " AND ".join(conds) if conds else "1=1"
    sql = (
        'SELECT "专利号","专利持有人","关联公司","关联资产","到期日","状态","管辖区" '
        f'FROM "IP" WHERE {where} LIMIT ?'
    )
    params.append(min(limit, 30))
    return query(sql, tuple(params))


# ═════════════════════════════════════════════════════════════════
# Buyer profiles
# ═════════════════════════════════════════════════════════════════


def get_buyer_profile(company):
    result = resolve_mnc(company)
    if result.row:
        if result.fuzzy:
            result.row["_matched_as"] = result.canonical
        return result.row
    hint = (
        f"已收录的 MNC 包括：{', '.join(result.suggestions[:5])}"
        if result.suggestions
        else "该公司暂无买方画像数据。"
    )
    return {"_not_found": True, "message": f"未找到 '{company}' 的买方画像。{hint}"}


# ═════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════
# Conference Insight
# ═════════════════════════════════════════════════════════════════


def _conference_companies(session_id: str) -> list[dict]:
    """Load company list for a session (cached)."""
    from routers.conference import _load_report_data

    try:
        raw = _load_report_data(session_id)
        return raw.get("companies", [])
    except Exception:
        return []


def search_conference(
    session: str = "AACR-2026",
    q: str = "",
    company_type: str = "",
    country: str = "",
    limit: int = 10,
) -> list[dict]:
    """Search companies participating in a conference session."""
    companies = _conference_companies(session)
    results = []
    q_lower = q.lower()
    for c in companies:
        if q_lower and q_lower not in (c.get("company") or "").lower():
            continue
        if company_type and c.get("客户类型") != company_type:
            continue
        if country and c.get("所处国家") != country:
            continue
        abstracts = c.get("abstracts", [])
        results.append(
            {
                "company": c.get("company"),
                "客户类型": c.get("客户类型"),
                "所处国家": c.get("所处国家"),
                "CT_count": c.get("CT_count", 0),
                "LB_count": c.get("LB_count", 0),
                "abstract_count": len(abstracts),
                "top_titles": [a.get("title", "") for a in abstracts[:3]],
                "targets": list({t for a in abstracts for t in (a.get("targets") or [])}),
            }
        )
        if len(results) >= min(limit, 20):
            break
    return results


def get_conference_company(company: str, session: str = "AACR-2026") -> dict | None:
    """Get full detail (all abstracts + data points) for one conference company."""
    companies = _conference_companies(session)
    match = next(
        (c for c in companies if (c.get("company") or "").lower() == company.lower()),
        None,
    )
    return match or {"error": f"Company '{company}' not found in {session}"}


# ═════════════════════════════════════════════════════════════════
# Aggregate
# ═════════════════════════════════════════════════════════════════

_COUNT_BY_TABLES = {"公司", "资产", "临床", "交易", "IP"}


def count_by(table, group_by):
    # NOTE: column validation uses SQLite's PRAGMA which returns empty on
    # Postgres — tracked as a separate bug. Behavior unchanged from pre-refactor.
    if table not in _COUNT_BY_TABLES:
        return {"error": f"Invalid table: {table}"}
    try:
        cols = [r["name"] for r in query(f'PRAGMA table_info("{table}")')]
    except Exception:
        cols = []
    if group_by not in cols:
        return {"error": f"Invalid column '{group_by}' for table '{table}'"}
    sql = (
        f'SELECT "{group_by}" as value, COUNT(*) as count '
        f'FROM "{table}" WHERE "{group_by}" IS NOT NULL AND "{group_by}" != \'\' '
        f'GROUP BY "{group_by}" ORDER BY count DESC LIMIT 50'
    )
    try:
        return query(sql)
    except Exception as e:
        return {"error": str(e)}


# ═════════════════════════════════════════════════════════════════
# Global fuzzy search
# ═════════════════════════════════════════════════════════════════


def search_global(q, limit=5):
    return {
        "companies": search_companies(q=q, limit=limit),
        "assets": search_assets(q=q, limit=limit),
        "deals": search_deals(q=q, limit=limit),
        "clinical": search_clinical(q=q, limit=limit),
    }


# ═════════════════════════════════════════════════════════════════
# Watchlist (write)
# ═════════════════════════════════════════════════════════════════


def add_to_watchlist(entity_type: str, entity_key: str, notes: str = "", _user_id: str = ""):
    """Add entity to the current user's watchlist (Postgres)."""
    if not _user_id:
        return {"success": False, "error": "用户未登录，无法添加关注"}
    try:
        with transaction() as cur:
            cur.execute(
                """INSERT INTO user_watchlists (entity_type, entity_key, user_id, notes)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id, entity_type, entity_key)
                   DO UPDATE SET notes = COALESCE(NULLIF(EXCLUDED.notes, ''),
                                                   user_watchlists.notes)
                   RETURNING id""",
                (entity_type, entity_key, _user_id, notes or None),
            )
            row = cur.fetchone()
        return {
            "success": True,
            "id": row["id"],
            "entity_type": entity_type,
            "entity_key": entity_key,
            "message": f"✅ 已将 **{entity_key}** 添加到关注列表！你可以在 [关注列表](/watchlist) 页面查看。",
        }
    except Exception as e:
        logger.exception("add_to_watchlist failed")
        return {"success": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════
# Schemas (passed to the LLM as "tools" in the API body)
# ═════════════════════════════════════════════════════════════════

SCHEMAS = [
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
                "phase": {
                    "type": "string",
                    "description": "e.g. Phase 1, Phase 2, Phase 3, Commercial",
                },
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
                "sort_by": {
                    "type": "string",
                    "enum": ["date", "upfront", "total"],
                    "description": "Sort field",
                },
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
                "group_by": {
                    "type": "string",
                    "description": "Column name to group by, e.g. 临床阶段, 疾病领域",
                },
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
    {
        "name": "search_conference",
        "description": "Search companies participating in a specific conference (AACR, BIO, ESMO etc.). Returns CT/LB abstract counts, targets, and key data points. Use when user asks about conference presence, which companies presented at AACR, who had CT abstracts, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session": {
                    "type": "string",
                    "description": "Conference session ID, e.g. 'AACR-2026'",
                    "default": "AACR-2026",
                },
                "q": {"type": "string", "description": "Search by company name"},
                "company_type": {
                    "type": "string",
                    "description": "e.g. Biotech, Pharma, MNC, Biotech(CN)",
                },
                "country": {"type": "string", "description": "e.g. 中国, 美国, 日本"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_conference_company",
        "description": "Get full conference details for one company — all abstracts, clinical data points (ORR, DOR, N), targets, and conclusions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name (English)"},
                "session": {"type": "string", "default": "AACR-2026"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "add_to_watchlist",
        "description": "Add a company or asset to the current user's watchlist. Use this when the user says '加关注', '加入关注', '收藏', or any similar intent. entity_type must be 'company' or 'asset'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["company", "asset", "disease", "target", "incubator"],
                    "description": "Type of entity",
                },
                "entity_key": {
                    "type": "string",
                    "description": "The name/key of the entity, e.g. the company name or asset name",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes about why this is being watched",
                },
            },
            "required": ["entity_type", "entity_key"],
        },
    },
]


# name → implementation function
IMPLS = {
    "search_companies": search_companies,
    "get_company": get_company,
    "search_assets": search_assets,
    "get_asset": get_asset,
    "search_clinical": search_clinical,
    "search_deals": search_deals,
    "search_patents": search_patents,
    "get_buyer_profile": get_buyer_profile,
    "count_by": count_by,
    "search_global": search_global,
    "add_to_watchlist": add_to_watchlist,
    "search_conference": search_conference,
    "get_conference_company": get_conference_company,
}

# ── Tool-registry metadata ────────────────────────────────────────────────
# Consumed by tools/__init__.py to configure registry.py without any
# hardcoding in those shared files.

# Single-table CRM tools: map tool name → CRM table for field-visibility
# stripping (external users cannot see internal BD/scoring columns).
TABLE_MAP: dict[str, str] = {
    "search_companies": "公司",
    "get_company": "公司",
    "search_assets": "资产",
    "get_asset": "资产",
    "search_clinical": "临床",
    "search_deals": "交易",
}

# add_to_watchlist writes to Postgres and needs the caller's user id.
NEEDS_USER_ID: set[str] = {"add_to_watchlist"}

# search_global returns {companies, assets, deals, clinical} — each sub-list
# needs its own table's field policy applied.
MULTI_TABLE_MAP: dict[str, list[tuple[str, str]]] = {
    "search_global": [
        ("companies", "公司"),
        ("assets", "资产"),
        ("deals", "交易"),
        ("clinical", "临床"),
    ],
}
