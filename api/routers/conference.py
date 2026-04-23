"""Conference Insight endpoints.

Serves pre-processed conference data (company flash cards + abstract details)
from JSON/CSV files in CONFERENCES_DIR.  No DB write path here — data is
read-only at request time.

Supported sessions (auto-discovered from directory names):
  AACR-2026          — report_data.json  (companies + CT/LB abstracts)
  BIO-Europe-Spring-2026 — limited support
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from config import CONFERENCES_DIR
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Data loading (cached per process lifetime)
# ─────────────────────────────────────────────────────────────

# Human-readable metadata keyed by directory name
_SESSION_META: dict[str, dict] = {
    "AACR-2026": {
        "id": "AACR-2026",
        "name": "AACR 2026",
        "full_name": "AACR Annual Meeting 2026",
        "date": "2026-04",
        "location": "Chicago, IL",
        "type": "oncology",
        "data_format": "report_data",
    },
    "AACR-2025": {
        "id": "AACR-2025",
        "name": "AACR 2025",
        "full_name": "AACR Annual Meeting 2025",
        "date": "2025-04",
        "location": "Chicago, IL",
        "type": "oncology",
        "data_format": "report_data",
    },
}


@lru_cache(maxsize=8)
def _load_report_data(session_id: str) -> dict:
    """Load and cache report_data.json for a session."""
    path = CONFERENCES_DIR / session_id / "report_data.json"
    if not path.exists():
        raise FileNotFoundError(f"report_data.json not found for {session_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_session_data(session_id: str) -> dict:
    """Return {meta, companies} for a session, or raise 404."""
    session_dir = CONFERENCES_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    try:
        raw = _load_report_data(session_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return raw


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _match(value: str | None, q: str) -> bool:
    if not q:
        return True
    return q.lower() in (value or "").lower()


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/sessions")
def list_sessions():
    """List available conference sessions (ordered newest first)."""
    sessions = []
    for dir_path in sorted(CONFERENCES_DIR.iterdir(), reverse=True):
        if not dir_path.is_dir():
            continue
        sid = dir_path.name
        # Only include sessions that have report_data.json
        if not (dir_path / "report_data.json").exists():
            continue
        meta = _SESSION_META.get(
            sid,
            {
                "id": sid,
                "name": sid,
                "full_name": sid,
                "date": "",
                "location": "",
                "type": "conference",
                "data_format": "report_data",
            },
        )
        # Attach live stats
        try:
            raw = _load_report_data(sid)
            meta = {**meta, **raw.get("meta", {})}
        except Exception:
            pass
        sessions.append(meta)
    return {"sessions": sessions}


@router.get("/{session_id}/stats")
def get_stats(session_id: str):
    """Aggregate statistics for a conference session."""
    raw = _get_session_data(session_id)
    companies = raw.get("companies", [])

    type_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    total_ct = 0
    total_lb = 0
    for c in companies:
        t = c.get("客户类型") or "Unknown"
        type_counts[t] = type_counts.get(t, 0) + 1
        ct = c.get("所处国家") or "Unknown"
        country_counts[ct] = country_counts.get(ct, 0) + 1
        total_ct += c.get("CT_count", 0)
        total_lb += c.get("LB_count", 0)

    return {
        **raw.get("meta", {}),
        "total_companies": len(companies),
        "total_ct": total_ct,
        "total_lb": total_lb,
        "by_type": type_counts,
        "by_country": country_counts,
    }


@router.get("/{session_id}/companies")
def list_companies(
    session_id: str,
    q: str = Query("", description="Search company name"),
    company_type: str = Query("", description="Filter by 客户类型"),
    country: str = Query("", description="Filter by 所处国家"),
    ct_only: bool = Query(False, description="Only companies with CT/LB abstracts"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
):
    """Paginated company flash card list for a conference session."""
    raw = _get_session_data(session_id)
    companies = raw.get("companies", [])

    # Filter
    filtered = []
    for c in companies:
        if not _match(c.get("company"), q):
            continue
        if company_type and c.get("客户类型") != company_type:
            continue
        if country and c.get("所处国家") != country:
            continue
        if ct_only and (c.get("CT_count", 0) + c.get("LB_count", 0)) == 0:
            continue
        filtered.append(c)

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    # Return summary cards (omit full abstract bodies to keep response small)
    cards = []
    for c in page_items:
        abstracts = c.get("abstracts", [])
        # Summarise top 3 abstracts for card preview
        top_abstracts = [
            {
                "doi": a.get("doi", ""),
                "title": a.get("title", ""),
                "kind": a.get("kind", ""),
                "targets": a.get("targets", [])[:5],
                "data_points": a.get("data_points", {}),
            }
            for a in abstracts[:3]
        ]
        cards.append(
            {
                "company": c.get("company"),
                "客户类型": c.get("客户类型"),
                "所处国家": c.get("所处国家"),
                "Ticker": c.get("Ticker"),
                "市值/估值": c.get("市值/估值"),
                "CT_count": c.get("CT_count", 0),
                "LB_count": c.get("LB_count", 0),
                "abstract_count": len(abstracts),
                "top_abstracts": top_abstracts,
            }
        )

    # Facet counts for filter dropdowns
    all_types = sorted({c.get("客户类型") or "" for c in filtered if c.get("客户类型")})
    all_countries = sorted({c.get("所处国家") or "" for c in filtered if c.get("所处国家")})

    return {
        "data": cards,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "facets": {
            "types": all_types,
            "countries": all_countries,
        },
    }


@router.get("/{session_id}/companies/{company_name}")
def get_company(session_id: str, company_name: str):
    """Full company detail including all abstracts."""
    raw = _get_session_data(session_id)
    companies = raw.get("companies", [])

    match = next(
        (c for c in companies if (c.get("company") or "").lower() == company_name.lower()),
        None,
    )
    if match is None:
        raise HTTPException(
            status_code=404, detail=f"Company '{company_name}' not found in {session_id}"
        )
    return match


@router.get("/{session_id}/abstracts")
def list_abstracts(
    session_id: str,
    q: str = Query("", description="Search title/target/company"),
    kind: str = Query("", description="CT | LB | regular"),
    company: str = Query("", description="Filter by company name"),
    country: str = Query("", description="Filter by country"),
    company_type: str = Query("", description="Filter by 客户类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
):
    """Flat list of individual abstracts (flattened from all companies), newest hottest first."""
    raw = _get_session_data(session_id)
    companies = raw.get("companies", [])

    # Flatten all abstracts, attaching company metadata
    all_abstracts = []
    q_lower = q.lower()
    for c in companies:
        comp_name = c.get("company") or ""
        comp_type = c.get("客户类型") or ""
        comp_country = c.get("所处国家") or ""

        if company and company.lower() not in comp_name.lower():
            continue
        if country and comp_country != country:
            continue
        if company_type and comp_type != company_type:
            continue

        for ab in c.get("abstracts", []):
            if kind and ab.get("kind") != kind:
                continue
            if q_lower:
                searchable = " ".join(
                    [
                        ab.get("title") or "",
                        " ".join(ab.get("targets") or []),
                        comp_name,
                        ab.get("conclusion") or "",
                    ]
                ).lower()
                if q_lower not in searchable:
                    continue
            all_abstracts.append(
                {
                    **ab,
                    "company": comp_name,
                    "客户类型": comp_type,
                    "所处国家": comp_country,
                    "Ticker": c.get("Ticker"),
                }
            )

    # Sort: CT first, then LB, then regular; within each group by company name
    _KIND_ORDER = {"CT": 0, "LB": 1, "regular": 2}
    all_abstracts.sort(
        key=lambda a: (_KIND_ORDER.get(a.get("kind", "regular"), 2), a.get("company", ""))
    )

    total = len(all_abstracts)
    start = (page - 1) * page_size
    page_items = all_abstracts[start : start + page_size]

    # Facets from the unfiltered (company/country/type) flattened set
    all_companies = sorted({c.get("company") or "" for c in companies if c.get("company")})
    all_countries = sorted({c.get("所处国家") or "" for c in companies if c.get("所处国家")})
    all_types = sorted({c.get("客户类型") or "" for c in companies if c.get("客户类型")})

    return {
        "data": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "facets": {
            "companies": all_companies[:50],  # cap for dropdown
            "countries": all_countries,
            "types": all_types,
        },
    }
