"""
PubMed E-utilities client.

Extracted from scripts/pubmed_batch_enrich.py and generalised for paper-analyst.
NCBI E-utilities are free, no API key required. Rate limited to 3 req/s.
Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

from __future__ import annotations

import atexit
import logging
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
SEARCH_URL = f"{EUTILS_BASE}/esearch.fcgi"
SUMMARY_URL = f"{EUTILS_BASE}/esummary.fcgi"
FETCH_URL = f"{EUTILS_BASE}/efetch.fcgi"

RATE_LIMIT_SECONDS = 0.4  # 3 req/s with margin
DEFAULT_TIMEOUT = 15.0

# Shared client — avoids per-call TCP+TLS handshake to eutils.ncbi.nlm.nih.gov.
# keepalive is modest (NCBI enforces 3 req/s; a single connection is usually enough).
# Timeouts are set per-request because efetch needs 2× the search timeout.
_http_client = httpx.Client(
    limits=httpx.Limits(max_keepalive_connections=3, max_connections=5),
)
atexit.register(_http_client.close)


def _sleep_rate_limit() -> None:
    time.sleep(RATE_LIMIT_SECONDS)


def search_articles(
    query: str,
    max_results: int = 20,
    sort: str = "relevance",
    years_back: int | None = None,
) -> list[str]:
    """Search PubMed, return list of PMIDs.

    Args:
        query: search query (PubMed syntax supported, e.g. `"KRAS G12D" AND cancer`)
        max_results: max PMIDs to return
        sort: "relevance" | "pub_date" | "most_cited"
        years_back: if set, restricts to `YYYY:YYYY[dp]` publication date range
    """
    full_query = query
    if years_back and years_back > 0:
        from datetime import datetime

        this_year = datetime.now().year
        full_query = f'({query}) AND ("{this_year - years_back}"[dp] : "{this_year}"[dp])'

    try:
        resp = _http_client.get(
            SEARCH_URL,
            params={
                "db": "pubmed",
                "term": full_query,
                "retmax": max_results,
                "retmode": "json",
                "sort": sort,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        return list(pmids)
    except Exception as e:
        logger.warning("PubMed search error for '%s': %s", query, e)
        return []
    finally:
        _sleep_rate_limit()


def get_article_metadata(pmids: list[str]) -> list[dict]:
    """Fetch title + journal + pubdate + DOI + abstract for each PMID.

    Returns list of dicts: {pmid, title, journal, pubdate, year, doi, authors, abstract}
    """
    if not pmids:
        return []

    results: list[dict] = []

    # Batch via esummary for metadata (one call for many PMIDs)
    summary_map: dict[str, dict] = {}
    try:
        resp = _http_client.get(
            SUMMARY_URL,
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("result", {})
        for pmid in pmids:
            if pmid in data:
                summary_map[pmid] = data[pmid]
    except Exception as e:
        logger.warning("PubMed esummary batch error: %s", e)
    finally:
        _sleep_rate_limit()

    # Batch efetch for abstracts (plain text, all PMIDs in one shot)
    abstracts_text = ""
    try:
        resp = _http_client.get(
            FETCH_URL,
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "rettype": "abstract",
                "retmode": "text",
            },
            timeout=DEFAULT_TIMEOUT * 2,
        )
        resp.raise_for_status()
        abstracts_text = resp.text
    except Exception as e:
        logger.warning("PubMed efetch abstract error: %s", e)
    finally:
        _sleep_rate_limit()

    # Split the bulk text — PubMed separates records by blank lines + PMID marker
    # Simple approach: look for "PMID: <pmid>" markers
    per_pmid_abs: dict[str, str] = {pmid: "" for pmid in pmids}
    if abstracts_text:
        # Split on "PMID: <digits>" which appears at end of each record
        chunks = re.split(r"\n\n(?=\d+\.\s+)", abstracts_text.strip())
        for chunk in chunks:
            m = re.search(r"PMID:\s*(\d+)", chunk)
            if m:
                pmid = m.group(1)
                if pmid in per_pmid_abs:
                    per_pmid_abs[pmid] = chunk.strip()

    for pmid in pmids:
        summary = summary_map.get(pmid, {})
        title = summary.get("title", "")
        journal = summary.get("fulljournalname") or summary.get("source", "")
        pubdate = summary.get("pubdate", "")
        year = ""
        if pubdate:
            ym = re.match(r"(\d{4})", pubdate)
            if ym:
                year = ym.group(1)
        doi = ""
        for aid in summary.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        authors = []
        for a in summary.get("authors", []):
            name = a.get("name", "")
            if name:
                authors.append(name)

        results.append(
            {
                "pmid": pmid,
                "title": title,
                "journal": journal,
                "pubdate": pubdate,
                "year": year,
                "doi": doi,
                "authors": authors,
                "abstract": per_pmid_abs.get(pmid, ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )

    return results


def fetch_single(pmid: str | None = None, doi: str | None = None) -> dict:
    """Convenience: resolve a single paper by PMID or DOI.

    If DOI provided, resolves to PMID first via esearch, then delegates to get_article_metadata.
    Returns a single metadata dict, or {} on failure.
    """
    if not pmid and doi:
        # Resolve DOI → PMID
        try:
            resp = _http_client.get(
                SEARCH_URL,
                params={
                    "db": "pubmed",
                    "term": f"{doi}[doi]",
                    "retmode": "json",
                },
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            pmids = resp.json().get("esearchresult", {}).get("idlist", [])
            if pmids:
                pmid = pmids[0]
        except Exception as e:
            logger.warning("DOI resolution failed for %s: %s", doi, e)
        finally:
            _sleep_rate_limit()

    if not pmid:
        return {}

    metas = get_article_metadata([pmid])
    return metas[0] if metas else {}


def extract_pdf_text(filepath: Path) -> str:
    """Extract text from a PDF file using pypdf.

    Reused pattern from chat.py's _extract_text(). Returns empty string on failure.
    """
    if not filepath.exists():
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(filepath))
        parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
        return "\n".join(parts)
    except Exception as e:
        logger.warning("PDF extraction failed for %s: %s", filepath, e)
        return ""
