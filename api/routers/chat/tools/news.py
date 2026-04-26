"""Company / asset news search tool for the BDGO chat assistant.

Exposes ``search_company_news`` — uses Tavily's news-topic mode to fetch
recent news about a biotech company or specific asset.

Use-cases:
  - Pre-meeting brief: "what happened with AstraZeneca in the last 30 days?"
  - BD trigger detection: "any recent deals / partnerships for BeiGene?"
  - Asset status tracking: "recent updates on sotorasib NSCLC trials?"
  - Catalyst monitoring: "has Amgen published any Phase 3 data for AMG 757?"
"""

from __future__ import annotations

import logging

from services.external.search import search_news

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Tool schema
# ─────────────────────────────────────────────────────────────

SCHEMAS = [
    {
        "name": "search_company_news",
        "description": (
            "Fetch recent news articles about a biotech company or drug/asset. "
            "Uses Tavily news search — results are real news (press releases, "
            "clinical trial updates, deal announcements, financing rounds, FDA decisions). "
            "Optionally focus on a specific asset or topic. "
            "Returns up to 10 articles with title, URL, snippet, and publish date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Company name to search news for (e.g. 'BeiGene', 'Zymeworks')",
                },
                "asset_name": {
                    "type": "string",
                    "description": (
                        "Optional drug or asset name to narrow the search "
                        "(e.g. 'tislelizumab', 'zanidatamab')"
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "Optional extra topic keyword to focus the search "
                        "(e.g. 'clinical trial', 'partnership deal', 'FDA approval', "
                        "'financing', 'Phase 3 results')"
                    ),
                },
                "days_back": {
                    "type": "integer",
                    "description": "Look back this many days for news (default 30, max 365)",
                    "default": 30,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max articles to return (1–10, default 5)",
                    "default": 5,
                },
            },
            "required": ["company_name"],
        },
    }
]

# ─────────────────────────────────────────────────────────────
# Implementation
# ─────────────────────────────────────────────────────────────


def _search_company_news(
    company_name: str = "",
    asset_name: str = "",
    topic: str = "",
    days_back: int = 30,
    max_results: int = 5,
    **_: object,
) -> dict:
    """Run 1-2 Tavily news queries and return deduplicated articles."""
    if not company_name.strip():
        return {"error": "company_name is required", "articles": [], "total": 0}

    days_back = max(1, min(days_back, 365))
    max_results = max(1, min(max_results, 10))

    # Build the primary query
    parts = [company_name]
    if asset_name:
        parts.append(asset_name)
    if topic:
        parts.append(topic)
    primary_query = " ".join(parts)

    articles = search_news(
        query=primary_query,
        days=days_back,
        max_results=max_results,
    )

    # If the primary query yielded few results and we have an asset, try
    # a broader company-only query to supplement (cap to avoid double Tavily calls
    # when results are already good).
    if len(articles) < max_results // 2 and asset_name and not topic:
        extra = search_news(
            query=f"{company_name} biotech news",
            days=days_back,
            max_results=max_results - len(articles),
        )
        # Deduplicate by URL
        seen_urls = {a["url"] for a in articles}
        for a in extra:
            if a["url"] not in seen_urls:
                articles.append(a)
                seen_urls.add(a["url"])

    return {
        "articles": articles,
        "total": len(articles),
        "query": primary_query,
        "days_back": days_back,
        "source": "Tavily news search",
    }


# ─────────────────────────────────────────────────────────────
# Registry exports
# ─────────────────────────────────────────────────────────────

IMPLS: dict = {"search_company_news": _search_company_news}
TABLE_MAP: dict = {}
