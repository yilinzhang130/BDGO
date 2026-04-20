"""Extract structured "context entity" cards from CRM tool results.

When a tool like ``search_companies`` returns rows, we extract the top 3
as cards for the chat's right-hand Context Panel. Cards are scoped to
the session and upserted in ``context_entities`` (see chat_store).

External users automatically see fewer fields because their tool results
are already stripped by field_policy before reaching these extractors —
``row.get("BD跟进优先级")`` returns None, ``_format_field`` returns None,
and the field is dropped from the card.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Lowercase, strip punct/whitespace for dedup keys."""
    if not text:
        return ""
    t = re.sub(r"\s+", "_", str(text).strip().lower())
    t = re.sub(r"[^\w\u4e00-\u9fff_\-]", "", t)
    return t[:80]


def _format_field(label: str, value) -> dict | None:
    if value is None or value == "" or str(value).strip() in ("-", "None", "null"):
        return None
    s = str(value).strip()
    if len(s) > 60:
        s = s[:57] + "..."
    return {"label": label, "value": s}


# ─────────────────────────────────────────────────────────────
# Per-table extractors
# ─────────────────────────────────────────────────────────────

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
        "href": f"/companies/{quote(str(name), safe='')}",
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
        href = f"/assets/{quote(str(company), safe='')}/{quote(str(name), safe='')}"
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
        "href": f"/clinical/{quote(str(record_id), safe='')}",
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
        "href": f"/deals/{quote(str(name), safe='')}",
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
        "href": f"/ip/{quote(str(pid), safe='')}",
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
        "href": f"/buyers/{quote(str(name), safe='')}",
    }


# Tool name → extractor function (only tools that return CRM rows are here;
# aggregate/skill tools like count_by, search_global, generate_* have no
# per-row entity shape so they're skipped).
_EXTRACTORS = {
    "search_companies": _entity_from_company,
    "get_company": _entity_from_company,
    "search_assets": _entity_from_asset,
    "get_asset": _entity_from_asset,
    "search_clinical": _entity_from_clinical,
    "search_deals": _entity_from_deal,
    "search_patents": _entity_from_patent,
    "get_buyer_profile": _entity_from_buyer,
}


def extract_context_entities(tool_name: str, raw_result_str: str) -> list[dict]:
    """Parse a tool's JSON result string and extract structured entities
    for the context panel. Returns at most 3 entities per tool call.
    """
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

    fn = _EXTRACTORS.get(tool_name)
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
