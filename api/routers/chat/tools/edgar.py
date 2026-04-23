"""SEC EDGAR 10-K / 10-Q / 8-K lookup for US-listed pharma.

Thin wrapper around the public data.sec.gov JSON endpoints. No API key
required, but SEC's fair-access policy mandates a descriptive User-Agent.

Two capabilities exposed to chat:
  1. ``edgar_find_filings``: given a company name or ticker, resolve to a CIK
     and return the most recent 10-K / 10-Q / 8-K filings with URLs.
  2. ``edgar_fetch_section``: fetch the raw text of a specific filing and
     return a keyword-filtered excerpt (pipeline / strategy / risk factors).

Intentionally does NOT attempt full RAG / embedding — for deep section
analysis the user can upload the PDF via the existing attachments flow."""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

import httpx

logger = logging.getLogger(__name__)


_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "BD Go Research (bdgo@example.com)"
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
_TIMEOUT = 20.0

# SEC wants ≤ 10 requests/sec. A single-session lock is sufficient here since
# chat tools dispatch is serialised per-turn.
_cik_lock = threading.Lock()
_cik_cache: dict[str, str] | None = None


def _load_cik_table() -> dict[str, str]:
    """Fetch SEC's public ticker → CIK mapping (cached in-process)."""
    global _cik_cache
    if _cik_cache is not None:
        return _cik_cache
    with _cik_lock:
        if _cik_cache is not None:
            return _cik_cache
        try:
            r = httpx.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            table: dict[str, str] = {}
            for entry in data.values():
                ticker = (entry.get("ticker") or "").upper()
                name = (entry.get("title") or "").lower()
                cik = str(entry.get("cik_str") or "").zfill(10)
                if ticker:
                    table[ticker] = cik
                if name:
                    table[name] = cik
            _cik_cache = table
            return table
        except Exception as e:
            logger.warning("SEC CIK table fetch failed: %s", e)
            _cik_cache = {}
            return _cik_cache


def _resolve_cik(query: str) -> tuple[str | None, str | None]:
    """Return (cik_padded, canonical_name) or (None, None)."""
    if not query:
        return None, None
    table = _load_cik_table()
    if not table:
        return None, None
    q = query.strip()
    qu = q.upper()
    ql = q.lower()

    # 1. Exact ticker match
    if qu in table:
        return table[qu], q
    # 2. Exact name match
    if ql in table:
        return table[ql], q
    # 3. Substring name match — pick the shortest (most specific).
    hits = [(name, cik) for name, cik in table.items() if ql in name and not name.isupper()]
    if hits:
        hits.sort(key=lambda x: len(x[0]))
        return hits[0][1], hits[0][0]
    return None, None


def edgar_find_filings(company: str = "", form_type: str = "10-K", limit: int = 5):
    """List recent filings for a US-listed company by name or ticker."""
    if not company:
        return {"error": "company (ticker or name) is required"}
    cik, canonical = _resolve_cik(company)
    if not cik:
        return {
            "error": f"Could not resolve '{company}' to a SEC CIK. "
            "Try the exact ticker (e.g. 'PFE') or official company name."
        }

    try:
        r = httpx.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception as e:
        return {"error": f"SEC submissions fetch failed: {e}"}

    recent = payload.get("filings", {}).get("recent", {}) or {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    wanted = form_type.upper().strip()
    results = []
    for i, f in enumerate(forms):
        if wanted and f.upper() != wanted:
            continue
        accession_no = accns[i] if i < len(accns) else ""
        accession_nd = accession_no.replace("-", "")
        doc = primary_docs[i] if i < len(primary_docs) else ""
        filing_date = dates[i] if i < len(dates) else ""
        results.append(
            {
                "form": f,
                "filing_date": filing_date,
                "accession_number": accession_no,
                "primary_document": doc,
                "html_url": (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nd}/{doc}"
                )
                if doc and accession_nd
                else "",
                "index_url": (
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={cik}&type={wanted}&dateb=&owner=include&count=40"
                ),
            }
        )
        if len(results) >= min(limit, 20):
            break

    return {
        "company": canonical or company,
        "cik": cik,
        "entity_name": payload.get("name"),
        "sic_description": payload.get("sicDescription"),
        "ticker_symbols": payload.get("tickers", []),
        "form_type": wanted,
        "filings": results,
        "count": len(results),
    }


def edgar_fetch_section(filing_url: str = "", keywords: str = "", max_excerpt_chars: int = 4000):
    """Fetch a filing's primary HTML/text and return keyword-filtered excerpts.

    Not a full RAG — just grep-like windowing to pull the most relevant
    paragraphs around the requested keywords (e.g. 'pipeline', 'strategy',
    'risk factors', 'tivdak')."""
    if not filing_url:
        return {"error": "filing_url is required"}
    try:
        r = httpx.get(filing_url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        return {"error": f"Filing fetch failed: {e}"}

    # 10-K exhibits can be tens of MB; refuse rather than OOM the worker.
    if len(r.text) > 25_000_000:
        return {
            "error": f"Filing too large ({len(r.text) // 1_000_000} MB). Try a specific exhibit URL or upload the PDF."
        }

    text = re.sub(r"<[^>]+>", " ", r.text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text)

    if not keywords:
        return {
            "filing_url": filing_url,
            "total_chars": len(text),
            "head": text[:max_excerpt_chars],
            "note": "No keywords provided — returning document head only.",
        }

    kws = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    excerpts: list[dict[str, Any]] = []
    lower = text.lower()
    window = 500
    for kw in kws:
        pos = 0
        hits = 0
        while True:
            idx = lower.find(kw, pos)
            if idx < 0 or hits >= 3:
                break
            start = max(0, idx - window)
            end = min(len(text), idx + window)
            excerpts.append(
                {
                    "keyword": kw,
                    "snippet": text[start:end].strip(),
                }
            )
            pos = end
            hits += 1

    # Cap total returned text so we stay inside LLM context.
    total = 0
    capped: list[dict[str, Any]] = []
    for e in excerpts:
        snippet = e["snippet"]
        if total + len(snippet) > max_excerpt_chars:
            snippet = snippet[: max(0, max_excerpt_chars - total)]
            if snippet:
                capped.append({"keyword": e["keyword"], "snippet": snippet})
            break
        capped.append(e)
        total += len(snippet)

    return {
        "filing_url": filing_url,
        "total_chars": len(text),
        "keywords": kws,
        "excerpts": capped,
        "excerpt_count": len(capped),
    }


SCHEMAS = [
    {
        "name": "edgar_find_filings",
        "description": (
            "Find a US-listed pharma company's recent SEC filings (10-K annual, "
            "10-Q quarterly, 8-K current reports). Returns filing dates and direct "
            "document URLs. Use when the user asks for a company's annual report, "
            "pipeline disclosure, risk factors, or any public SEC filing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company ticker (e.g. 'PFE', 'BMY') or full name (e.g. 'Pfizer Inc', 'Vertex Pharmaceuticals').",
                },
                "form_type": {
                    "type": "string",
                    "description": "SEC form type, default '10-K'. Common: 10-K, 10-Q, 8-K, S-1, 20-F.",
                    "default": "10-K",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max filings to return (default 5, cap 20).",
                    "default": 5,
                },
            },
            "required": ["company"],
        },
    },
    {
        "name": "edgar_fetch_section",
        "description": (
            "Fetch a specific SEC filing by URL and return text excerpts around "
            "given keywords. Use after edgar_find_filings to pull pipeline / "
            "strategy / risk-factor language from a 10-K. For full-document "
            "analysis, suggest the user upload the PDF via the attachments flow."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filing_url": {
                    "type": "string",
                    "description": "The html_url from edgar_find_filings output.",
                },
                "keywords": {
                    "type": "string",
                    "description": "Comma-separated keywords, e.g. 'pipeline, tivdak, strategic priorities'. Omit for document head only.",
                },
                "max_excerpt_chars": {
                    "type": "integer",
                    "description": "Cap on total excerpt length (default 4000).",
                    "default": 4000,
                },
            },
            "required": ["filing_url"],
        },
    },
]


IMPLS = {
    "edgar_find_filings": edgar_find_filings,
    "edgar_fetch_section": edgar_fetch_section,
}
