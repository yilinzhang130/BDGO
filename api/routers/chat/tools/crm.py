"""CRM search + lookup tools (companies, assets, clinical, deals, patents,
buyer profiles, aggregation, global search, watchlist write).

Each tool is a plain function that returns a JSON-serialisable dict or
list. Field-visibility enforcement happens centrally in
``tools.registry._strip_tool_result`` after the function returns.

Schemas and implementations are colocated — no need to hunt in two places
when adding a parameter.
"""

from __future__ import annotations

import logging

from database import transaction
from db import query, query_one

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# Companies
# ═════════════════════════════════════════════════════════════════

def search_companies(q="", country="", type="", disease="", limit=10):
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
    sql = (
        'SELECT "客户名称","客户类型","所处国家","疾病领域","核心产品的阶段",'
        '"BD跟进优先级","公司质量评分" '
        f'FROM "公司" WHERE {where} LIMIT ?'
    )
    params.append(min(limit, 30))
    return query(sql, tuple(params))


def get_company(name):
    return query_one('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))


# ═════════════════════════════════════════════════════════════════
# Assets
# ═════════════════════════════════════════════════════════════════

def search_assets(q="", company="", phase="", disease="", target="", limit=10):
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
        conds.append('"专利号" LIKE ?')
        params.append(f"%{q}%")
    if company:
        conds.append('"关联公司" LIKE ?')
        params.append(f"%{company}%")
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
    return query_one('SELECT * FROM "MNC画像" WHERE "company_name" = ?', (company,))


# ═════════════════════════════════════════════════════════════════
# Aggregate
# ═════════════════════════════════════════════════════════════════

def count_by(table, group_by):
    # NOTE: column validation currently uses SQLite's `PRAGMA table_info`
    # which returns empty on Postgres — that's a separate bug tracked
    # elsewhere. Leaving behavior identical to pre-refactor.
    table_map = {"公司": "公司", "资产": "资产", "临床": "临床", "交易": "交易", "IP": "IP"}
    physical = table_map.get(table, table)
    if table not in table_map:
        return {"error": f"Invalid table: {table}"}
    try:
        cols = [r["name"] for r in query(f'PRAGMA table_info("{physical}")')]
    except Exception:
        cols = []
    if group_by not in cols:
        return {"error": f"Invalid column '{group_by}' for table '{table}'"}
    sql = (
        f'SELECT "{group_by}" as value, COUNT(*) as count '
        f'FROM "{physical}" WHERE "{group_by}" IS NOT NULL AND "{group_by}" != \'\' '
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
    {
        "name": "add_to_watchlist",
        "description": "Add a company or asset to the current user's watchlist. Use this when the user says '加关注', '加入关注', '收藏', or any similar intent. entity_type must be 'company' or 'asset'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["company", "asset", "disease", "target", "incubator"], "description": "Type of entity"},
                "entity_key": {"type": "string", "description": "The name/key of the entity, e.g. the company name or asset name"},
                "notes": {"type": "string", "description": "Optional notes about why this is being watched"},
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
}
