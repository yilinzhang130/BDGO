"""Unit tests for the company news chat tool (P2-12).

Tests:
  1. Tool registered in TOOLS and TOOL_IMPL.
  2. Schema: required field, input_schema presence.
  3. Error guard: missing company_name.
  4. Happy-path: search_news called with correct query.
  5. search_news extended: search_news() called for asset + company combo.
  6. Deduplication: second query results merged without duplicates.
  7. Limit clamping (1–10).
  8. days_back clamping (1–365).
  9. search_news function added to services/external/search.py.
 10. Planner inventory includes search_company_news.
"""

from __future__ import annotations

from unittest.mock import patch

# ─────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────


def test_tool_registered_in_tools():
    from routers.chat.tools import TOOLS

    assert any(t["name"] == "search_company_news" for t in TOOLS)


def test_tool_impl_registered():
    from routers.chat.tools import TOOL_IMPL

    assert "search_company_news" in TOOL_IMPL
    assert callable(TOOL_IMPL["search_company_news"])


def test_tool_module_exports():
    from routers.chat.tools import news as news_mod

    assert hasattr(news_mod, "SCHEMAS")
    assert hasattr(news_mod, "IMPLS")
    assert hasattr(news_mod, "TABLE_MAP")
    assert news_mod.TABLE_MAP == {}


def test_schema_has_required_company_name():
    from routers.chat.tools import TOOLS

    schema = next(t for t in TOOLS if t["name"] == "search_company_news")
    required = schema["input_schema"].get("required", [])
    assert "company_name" in required


def test_schema_has_all_input_fields():
    from routers.chat.tools import TOOLS

    schema = next(t for t in TOOLS if t["name"] == "search_company_news")
    props = schema["input_schema"]["properties"]
    for f in ("company_name", "asset_name", "topic", "days_back", "max_results"):
        assert f in props, f"Missing field: {f}"


# ─────────────────────────────────────────────────────────────
# Error guard
# ─────────────────────────────────────────────────────────────


def test_empty_company_name_returns_error():
    from routers.chat.tools.news import _search_company_news

    result = _search_company_news(company_name="")
    assert "error" in result
    assert result["articles"] == []
    assert result["total"] == 0


def test_whitespace_company_name_returns_error():
    from routers.chat.tools.news import _search_company_news

    result = _search_company_news(company_name="   ")
    assert "error" in result


# ─────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────

_FAKE_ARTICLES = [
    {
        "title": "BeiGene signs deal with Novartis",
        "url": "https://example.com/1",
        "snippet": "BeiGene ...",
        "published_date": "2026-04-10",
    },
    {
        "title": "Tislelizumab Phase 3 data",
        "url": "https://example.com/2",
        "snippet": "Phase 3 ...",
        "published_date": "2026-04-08",
    },
]


def test_happy_path_returns_articles():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=_FAKE_ARTICLES) as mock_sn:
        result = _search_company_news(company_name="BeiGene")

    assert result["total"] == 2
    assert result["articles"] == _FAKE_ARTICLES
    mock_sn.assert_called_once()
    # Query should contain the company name
    call_query = mock_sn.call_args[1].get("query") or mock_sn.call_args[0][0]
    assert "BeiGene" in call_query


def test_asset_appended_to_query():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=_FAKE_ARTICLES) as mock_sn:
        _search_company_news(company_name="BeiGene", asset_name="tislelizumab")

    call_query = mock_sn.call_args[1].get("query") or mock_sn.call_args[0][0]
    assert "tislelizumab" in call_query


def test_topic_appended_to_query():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=_FAKE_ARTICLES) as mock_sn:
        _search_company_news(company_name="BeiGene", topic="FDA approval")

    call_query = mock_sn.call_args[1].get("query") or mock_sn.call_args[0][0]
    assert "FDA approval" in call_query


def test_days_back_passed_to_search_news():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=_FAKE_ARTICLES) as mock_sn:
        _search_company_news(company_name="Amgen", days_back=7)

    call_days = mock_sn.call_args[1].get("days") or mock_sn.call_args[0][1]
    assert call_days == 7


# ─────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────


def test_deduplication_no_duplicate_urls():
    """Second query must not re-add articles already in the first batch."""
    from routers.chat.tools.news import _search_company_news

    first_batch = [{"title": "A", "url": "https://u.com/1", "snippet": "x", "published_date": ""}]
    second_batch = [
        {"title": "A-dup", "url": "https://u.com/1", "snippet": "x", "published_date": ""},  # dup
        {"title": "B-new", "url": "https://u.com/2", "snippet": "y", "published_date": ""},  # new
    ]
    call_count = 0

    def fake_search_news(**kwargs):
        nonlocal call_count
        call_count += 1
        return first_batch if call_count == 1 else second_batch

    with patch("routers.chat.tools.news.search_news", side_effect=fake_search_news):
        # Supply asset_name + no topic so the fallback branch can trigger
        result = _search_company_news(company_name="Foo Bio", asset_name="FOO-1", max_results=10)

    urls = [a["url"] for a in result["articles"]]
    assert len(urls) == len(set(urls)), "Duplicate URLs found in result"


# ─────────────────────────────────────────────────────────────
# Parameter clamping
# ─────────────────────────────────────────────────────────────


def test_max_results_clamped_to_10():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=[]) as mock_sn:
        _search_company_news(company_name="X", max_results=999)

    call_max = mock_sn.call_args[1].get("max_results") or mock_sn.call_args[0][2]
    assert call_max <= 10


def test_max_results_clamped_minimum_1():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=[]) as mock_sn:
        _search_company_news(company_name="X", max_results=0)

    call_max = mock_sn.call_args[1].get("max_results") or mock_sn.call_args[0][2]
    assert call_max >= 1


def test_days_back_clamped_to_365():
    from routers.chat.tools.news import _search_company_news

    with patch("routers.chat.tools.news.search_news", return_value=[]) as mock_sn:
        _search_company_news(company_name="X", days_back=9999)

    call_days = mock_sn.call_args[1].get("days") or mock_sn.call_args[0][1]
    assert call_days <= 365


# ─────────────────────────────────────────────────────────────
# search_news function in external/search
# ─────────────────────────────────────────────────────────────


def test_search_news_function_exists():
    from services.external.search import search_news

    assert callable(search_news)


def test_search_news_returns_empty_on_blank_query():
    from services.external.search import search_news

    assert search_news("") == []
    assert search_news("   ") == []


def test_search_news_topic_mode_in_payload():
    """search_news must send topic='news' to Tavily."""
    from services.external import search as search_mod

    captured: dict = {}

    def fake_post(url, json, headers, timeout):
        captured["payload"] = json
        from unittest.mock import MagicMock

        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"results": []}
        return r

    with (
        patch.object(search_mod._http_client, "post", side_effect=fake_post),
        patch.object(search_mod, "_KEYS", ["fake-key"]),
        patch.object(search_mod, "_banned", set()),
        patch.object(search_mod, "_usage", {"fake-key": 0}),
    ):
        search_mod.search_news("Amgen news", days=14)

    assert captured.get("payload", {}).get("topic") == "news"
    assert captured.get("payload", {}).get("days") == 14


# ─────────────────────────────────────────────────────────────
# Planner sync
# ─────────────────────────────────────────────────────────────


def test_planner_prompt_includes_search_company_news():
    from planner import PLANNER_SYSTEM_PROMPT

    assert "search_company_news" in PLANNER_SYSTEM_PROMPT, (
        "search_company_news missing from PLANNER_SYSTEM_PROMPT — add it to the tool inventory"
    )
