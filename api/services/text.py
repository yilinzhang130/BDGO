"""Shared text utilities for report services."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def safe_json_loads(raw: Any, default: _T) -> Any | _T:
    """Tolerant JSON parse for CRM columns that may store dict/list, a JSON
    string, or be NULL/empty. Returns ``default`` on any parse failure."""
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("JSON parse failed for value: %r", str(raw)[:100])
        return default


def safe_slug(text: str, max_len: int = 40) -> str:
    """Slugify text for filename safety (lowercase, spaces→underscores, CJK-aware)."""
    t = re.sub(r"\s+", "_", text.strip().lower())
    t = re.sub(r"[^\w\u4e00-\u9fff_\-]", "", t)
    return t[:max_len] or "untitled"


def format_web_results(
    results: list[dict],
    enabled: bool,
    include_query: bool = True,
) -> str:
    """Format web search results for LLM prompt injection.

    Shared across all report services to avoid per-service duplication.
    """
    if not enabled:
        return "(网络检索未启用)"
    if not results:
        return "(网络检索未返回结果)"
    lines = []
    for i, r in enumerate(results, 1):
        parts = [f"[{i}] {r.get('title', '')}"]
        parts.append(f"    URL: {r.get('url', '')}")
        if include_query and r.get("query"):
            parts.append(f"    Query: {r.get('query', '')}")
        parts.append(f"    Snippet: {(r.get('snippet') or '')[:350]}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def search_and_deduplicate(
    queries: list[str],
    max_results_per_query: int = 3,
) -> list[dict]:
    """Run multiple Tavily web searches, deduplicate results by URL.

    Each result dict gets an extra "query" key with the originating query string.
    Respects sequential key drain (calls are serialized within search_web).
    """
    from services.external.search import search_web

    seen_urls: set[str] = set()
    combined: list[dict] = []
    for q in queries:
        results = search_web(q, max_results=max_results_per_query)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                combined.append({**r, "query": q})
    return combined
