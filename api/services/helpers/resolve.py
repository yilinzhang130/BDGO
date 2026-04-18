"""Fuzzy company/entity name resolution for API use.

Wraps crm_match.find_existing_company() — the same 6-pass fuzzy logic used
during data ingest — and makes it available to chat tools, report services,
and REST routers.

Cache: full company and MNC画像 name lists are loaded once and refreshed
every 5 minutes to avoid per-request DB hits.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from difflib import SequenceMatcher
from typing import NamedTuple

# crm_match lives in the workspace scripts directory
_scripts = os.path.expanduser("~/.openclaw/workspace/scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from crm_match import find_existing_company, normalize_name  # noqa: E402

_CACHE_TTL = 300.0  # 5 minutes

_company_cache: list[dict] = []
_company_ts: float = 0.0
_mnc_cache: list[dict] = []
_mnc_ts: float = 0.0
_lock = threading.Lock()


def _get_company_names() -> list[dict]:
    global _company_cache, _company_ts
    now = time.monotonic()
    if now - _company_ts < _CACHE_TTL and _company_cache:
        return _company_cache
    with _lock:
        if now - _company_ts < _CACHE_TTL and _company_cache:
            return _company_cache
        from db import query
        _company_cache = query('SELECT "客户名称","英文名","中文名" FROM "公司"', ())
        _company_ts = now
    return _company_cache


def _get_mnc_names() -> list[dict]:
    """Return MNC画像 rows adapted to the shape find_existing_company expects."""
    global _mnc_cache, _mnc_ts
    now = time.monotonic()
    if now - _mnc_ts < _CACHE_TTL and _mnc_cache:
        return _mnc_cache
    with _lock:
        if now - _mnc_ts < _CACHE_TTL and _mnc_cache:
            return _mnc_cache
        from db import query
        rows = query('SELECT "company_name","company_cn" FROM "MNC画像"', ())
        # Adapt to 公司 shape so find_existing_company works
        _mnc_cache = [
            {"客户名称": r.get("company_name", ""), "中文名": r.get("company_cn", "")}
            for r in rows
        ]
        _mnc_ts = now
    return _mnc_cache


def _suggest(name: str, rows: list[dict], n: int = 5) -> list[str]:
    """Return the top N names most similar to `name` via normalized SequenceMatcher."""
    name_norm = normalize_name(name)
    scored: list[tuple[float, str]] = []
    for r in rows:
        primary = r.get("客户名称", "") or ""
        for val in (primary, r.get("英文名", "") or "", r.get("中文名", "") or ""):
            if not val:
                continue
            score = SequenceMatcher(None, name_norm, normalize_name(val)).ratio()
            scored.append((score, primary))
    seen: set[str] = set()
    result = []
    for score, cn in sorted(scored, reverse=True):
        if cn and cn not in seen and score > 0.25:
            seen.add(cn)
            result.append(cn)
            if len(result) >= n:
                break
    return result


# ── Public API ────────────────────────────────────────────────────────────────

class ResolveResult(NamedTuple):
    row: dict | None
    canonical: str | None     # actual name in CRM (may differ from input)
    fuzzy: bool               # True if a fuzzy match was used
    suggestions: list[str]    # top alternatives when not found


def resolve_company(name: str) -> ResolveResult:
    """Resolve a company name to a 公司 row using exact → LIKE → crm_match fuzzy."""
    from db import query, query_one

    # 1. Exact
    row = query_one('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))
    if row:
        return ResolveResult(row, name, False, [])

    # 2. Substring LIKE across all name columns
    rows = query(
        'SELECT * FROM "公司" WHERE "客户名称" LIKE ? OR "英文名" LIKE ? OR "中文名" LIKE ? LIMIT 1',
        (f"%{name}%",) * 3,
    )
    if rows:
        r = rows[0]
        return ResolveResult(r, r.get("客户名称"), True, [])

    # 3. crm_match 6-pass fuzzy
    all_rows = _get_company_names()
    matched = find_existing_company(name, all_rows)
    if matched:
        canonical = matched.get("客户名称", name)
        row = query_one('SELECT * FROM "公司" WHERE "客户名称" = ?', (canonical,))
        return ResolveResult(row, canonical, True, [])

    return ResolveResult(None, None, False, _suggest(name, all_rows))


def resolve_mnc(name: str) -> ResolveResult:
    """Resolve a company name to an MNC画像 row using exact → LIKE → crm_match fuzzy."""
    from db import query, query_one

    # 1. Exact
    row = query_one('SELECT * FROM "MNC画像" WHERE "company_name" = ?', (name,))
    if row:
        return ResolveResult(row, name, False, [])

    # 2. LIKE on both name columns
    rows = query(
        'SELECT * FROM "MNC画像" WHERE "company_name" LIKE ? OR "company_cn" LIKE ? LIMIT 1',
        (f"%{name}%", f"%{name}%"),
    )
    if rows:
        r = rows[0]
        return ResolveResult(r, r.get("company_name"), True, [])

    # 3. crm_match fuzzy against MNC name list
    mnc_rows = _get_mnc_names()
    matched = find_existing_company(name, mnc_rows)
    if matched:
        canonical = matched.get("客户名称", name)
        row = query_one('SELECT * FROM "MNC画像" WHERE "company_name" = ?', (canonical,))
        return ResolveResult(row, canonical, True, [])

    suggestions = [r.get("客户名称", "") for r in mnc_rows if r.get("客户名称")]
    return ResolveResult(None, None, False, _suggest(name, mnc_rows, n=8))


def fuzzy_company_names(name: str, n: int = 5) -> list[str]:
    """Return top N company names from 公司 table that best match `name`."""
    return _suggest(name, _get_company_names(), n)


def invalidate_cache() -> None:
    """Force cache refresh on next access (call after CRM writes)."""
    global _company_ts, _mnc_ts
    with _lock:
        _company_ts = 0.0
        _mnc_ts = 0.0
