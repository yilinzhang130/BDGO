"""Buyer match — given an asset (target / indication / modality / phase),
rank MNC buyers by strategic fit.

Scoring combines three signals from the CRM:
  1. Heritage TA overlap — does this MNC play in this therapeutic area?
  2. Sunk cost concentration — how much capital have they already committed
     to adjacent targets/TAs in historical deals?
  3. Recent deal activity — did they sign a comparable deal in the last 24m?

The tool is deliberately schema-simple so it's cheap to invoke inline during
a chat research flow (no file output, no async job). Output is a ranked list
for the LLM to reason over."""

from __future__ import annotations

import json
import logging

from crm_store import query
from services.crm.resolve import get_mnc_profiles
from services.text import safe_json_loads

logger = logging.getLogger(__name__)


def _ta_overlap(heritage_ta: str, target_ta: str) -> float:
    """Loose overlap: substring or shared token. Returns 0.0 - 1.0."""
    if not heritage_ta or not target_ta:
        return 0.0
    h = heritage_ta.lower()
    t = target_ta.lower()
    if t in h or h in t:
        return 1.0
    h_tokens = {x.strip() for x in h.replace("/", ",").split(",") if x.strip()}
    t_tokens = {x.strip() for x in t.replace("/", ",").split(",") if x.strip()}
    if h_tokens & t_tokens:
        return 0.6
    return 0.0


def _sunk_cost_score(sunk_cost: dict, target_ta: str) -> tuple[float, float]:
    """Return (normalized_score 0-1, absolute_spend_m)."""
    if not sunk_cost or not target_ta:
        return 0.0, 0.0
    tt = target_ta.lower()
    for ta, amount in sunk_cost.items():
        if ta.lower() == tt or tt in ta.lower() or ta.lower() in tt:
            try:
                amt = float(amount)
            except (TypeError, ValueError):
                continue
            # $500M+ is a strong signal; cap normalized score at 1.0.
            return min(amt / 500.0, 1.0), amt
    return 0.0, 0.0


def _recent_deal_score(
    deals_for_company: list[dict], target: str, indication: str
) -> tuple[float, list[dict]]:
    """Score a pre-bucketed list of this MNC's recent deals against the asset."""
    if not deals_for_company:
        return 0.0, []
    matches = []
    for r in deals_for_company:
        tgt = (r.get("靶点") or "").lower()
        ind = (r.get("适应症") or "").lower()
        if (
            target
            and (target.lower() in tgt or tgt in target.lower())
            or indication
            and (indication.lower() in ind or ind in indication.lower())
        ):
            matches.append(r)
    if matches:
        return 1.0, matches[:3]
    return 0.3, []


def _bucket_recent_deals(company_names: list[str]) -> dict[str, list[dict]]:
    """Pull all recent (24m) deals in one query, then bucket by 买方.

    Avoids the N+1 of running a LIKE per MNC against ~thousands of deal rows."""
    try:
        rows = query(
            'SELECT "交易名称","交易时间","交易类型","标的公司","首付款","总金额",'
            '"靶点","适应症","买方","买方英文名" '
            "FROM \"交易\" WHERE \"交易时间\" >= date('now', '-24 months') "
            'ORDER BY "交易时间" DESC',
            (),
        )
    except Exception as e:
        logger.warning("buyer_match: bulk deal query failed: %s", e)
        return {}

    lowered = [(n, n.lower()) for n in company_names if n]
    out: dict[str, list[dict]] = {}
    for d in rows:
        cn = (d.get("买方") or "").lower()
        en = (d.get("买方英文名") or "").lower()
        if not (cn or en):
            continue
        for name, nl in lowered:
            if nl and (nl in cn or nl in en or cn in nl or en in nl):
                out.setdefault(name, []).append(d)
                break
    return out


def buyer_match(
    target: str = "",
    indication: str = "",
    therapeutic_area: str = "",
    phase: str = "",
    modality: str = "",
    top_n: int = 8,
):
    """Rank MNC画像 rows by fit for a given asset profile."""
    if not (target or indication or therapeutic_area):
        return {"error": "Must provide at least one of: target, indication, therapeutic_area"}

    mncs = get_mnc_profiles()
    names = [m.get("company_name") or "" for m in mncs]
    deals_by_buyer = _bucket_recent_deals(names)

    ta = therapeutic_area or indication
    scored = []
    for m in mncs:
        name = m.get("company_name") or ""
        if not name:
            continue

        sunk = safe_json_loads(m.get("sunk_cost_by_ta"), {})
        theses = safe_json_loads(m.get("bd_pattern_theses"), [])

        ta_score = _ta_overlap(m.get("heritage_ta") or "", ta)
        sunk_score, sunk_amt = _sunk_cost_score(sunk, ta)
        recent_score, recent_deals = _recent_deal_score(
            deals_by_buyer.get(name, []), target, indication
        )

        thesis_bump = 0.0
        if isinstance(theses, list):
            for th in theses:
                text = (
                    json.dumps(th, ensure_ascii=False).lower()
                    if isinstance(th, dict)
                    else str(th).lower()
                )
                if (target and target.lower() in text) or (
                    indication and indication.lower() in text
                ):
                    thesis_bump = 0.15
                    break

        composite = round(
            0.35 * ta_score + 0.30 * sunk_score + 0.25 * recent_score + thesis_bump, 3
        )
        if composite <= 0:
            continue

        scored.append(
            {
                "company": name,
                "company_cn": m.get("company_cn") or "",
                "heritage_ta": m.get("heritage_ta") or "",
                "risk_appetite": m.get("risk_appetite") or "",
                "deal_size_preference": m.get("deal_size_preference") or "",
                "score": composite,
                "signals": {
                    "ta_overlap": round(ta_score, 2),
                    "sunk_cost_match": round(sunk_score, 2),
                    "sunk_cost_absolute_mm": sunk_amt,
                    "recent_deal_activity": round(recent_score, 2),
                    "thesis_mention": thesis_bump > 0,
                },
                "recent_comparable_deals": [
                    {
                        "name": d.get("交易名称"),
                        "time": d.get("交易时间"),
                        "type": d.get("交易类型"),
                        "upfront": d.get("首付款"),
                        "total": d.get("总金额"),
                        "target": d.get("靶点"),
                        "indication": d.get("适应症"),
                    }
                    for d in recent_deals
                ],
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: max(1, min(top_n, 20))]

    return {
        "asset_profile": {
            "target": target,
            "indication": indication,
            "therapeutic_area": ta,
            "phase": phase,
            "modality": modality,
        },
        "candidates": top,
        "total_mnc_scored": len(scored),
        "note": (
            "Scores combine heritage-TA overlap, sunk cost concentration, and 24m deal activity. "
            "Use generate_buyer_profile on the top 2-3 candidates for the full BD brief."
        ),
    }


SCHEMAS = [
    {
        "name": "buyer_match",
        "description": (
            "Rank MNC画像 buyers by strategic fit for a given biotech asset. "
            "Combines heritage-TA overlap, historical sunk cost in the asset's TA, "
            "and recent (24m) comparable deal activity. Use when the user asks "
            "'who would buy this asset?' or 'match buyers for target X'. "
            "Complements generate_buyer_profile which produces the deep BD brief on a single MNC."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Asset target, e.g. 'KRAS G12C', 'Claudin 18.2'.",
                },
                "indication": {
                    "type": "string",
                    "description": "Indication, e.g. 'NSCLC 2L', 'CLL'.",
                },
                "therapeutic_area": {
                    "type": "string",
                    "description": "Therapeutic area, e.g. 'Oncology', 'Immunology'. Defaults to indication if omitted.",
                },
                "phase": {
                    "type": "string",
                    "description": "Clinical phase (optional, affects prioritisation).",
                },
                "modality": {
                    "type": "string",
                    "description": "Modality (optional, e.g. 'ADC', 'small_molecule').",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Max candidates to return (default 8, cap 20).",
                    "default": 8,
                },
            },
        },
    }
]


IMPLS = {
    "buyer_match": buyer_match,
}
