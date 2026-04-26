"""
Unit tests for TimingAdvisorService input + helper logic.

LLM call (`run()`) is integration territory — these tests cover:
  - Service registration
  - Input model validation
  - _next_instance() conference date computation
  - _compute_upcoming_conferences() filtering by lookahead window
  - Catalysts and conferences block formatting
  - Suggested commands chip wiring (asset_context injection)
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import datetime

import pytest
from services import REPORT_SERVICES
from services.reports.timing_advisor import (
    _INDUSTRY_EVENTS,
    TimingAdvisorInput,
    TimingAdvisorService,
    _next_instance,
)


@pytest.fixture
def svc() -> TimingAdvisorService:
    return TimingAdvisorService()


# ── Registration & schema ───────────────────────────────────


def test_service_registered():
    assert "timing-advisor" in REPORT_SERVICES
    s = REPORT_SERVICES["timing-advisor"]
    assert isinstance(s, TimingAdvisorService)
    assert s.slug == "timing-advisor"
    assert s.output_formats == ["md"]


def test_industry_events_have_required_keys():
    for ev in _INDUSTRY_EVENTS:
        assert {"name", "short", "month", "approx_week", "category", "bd_note"} <= ev.keys()
        assert 1 <= ev["month"] <= 12
        assert 1 <= ev["approx_week"] <= 5


# ── Input model ─────────────────────────────────────────────


def test_input_minimal_defaults():
    inp = TimingAdvisorInput(company_name="Peg-Bio")
    assert inp.company_name == "Peg-Bio"
    assert inp.asset_name is None
    assert inp.perspective == "seller"
    assert inp.look_ahead_months == 12


def test_input_full():
    inp = TimingAdvisorInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        perspective="buyer",
        look_ahead_months=6,
    )
    assert inp.asset_name == "PEG-001"
    assert inp.perspective == "buyer"


def test_input_rejects_invalid_perspective():
    with pytest.raises(ValueError):
        TimingAdvisorInput(
            company_name="X",
            perspective="advisor",  # type: ignore[arg-type]
        )


def test_input_rejects_lookahead_out_of_range():
    with pytest.raises(ValueError):
        TimingAdvisorInput(company_name="X", look_ahead_months=0)
    with pytest.raises(ValueError):
        TimingAdvisorInput(company_name="X", look_ahead_months=36)


# ── _next_instance ──────────────────────────────────────────


def test_next_instance_returns_this_year_if_future():
    """JPM in January, today is Dec 1 → next JPM is Jan of NEXT year."""
    today = datetime.date(2026, 12, 1)
    d = _next_instance(month=1, approx_week=2, today=today)
    assert d.year == 2027
    assert d.month == 1


def test_next_instance_rolls_to_next_year_if_past():
    """ASCO in June, today is Aug 1 → next ASCO is June NEXT year."""
    today = datetime.date(2026, 8, 1)
    d = _next_instance(month=6, approx_week=1, today=today)
    assert d.year == 2027
    assert d.month == 6


def test_next_instance_returns_this_year_if_still_future():
    """ASH in Dec, today is Aug 1 → next ASH is THIS year."""
    today = datetime.date(2026, 8, 1)
    d = _next_instance(month=12, approx_week=2, today=today)
    assert d.year == 2026
    assert d.month == 12


# ── _compute_upcoming_conferences ───────────────────────────


def test_compute_conferences_within_look_ahead_window(svc):
    today = datetime.date(2026, 4, 1)
    result = svc._compute_upcoming_conferences(today, look_ahead_months=12)
    # Should return all annual events (each within 12 months)
    assert len(result) >= 6
    for ev in result:
        d = datetime.date.fromisoformat(ev["date"])
        assert d >= today
        assert d <= today + datetime.timedelta(days=12 * 30 + 5)
    # Sorted ascending
    dates = [ev["date"] for ev in result]
    assert dates == sorted(dates)


def test_compute_conferences_short_window_excludes_far_events(svc):
    """3-month window excludes events farther out."""
    today = datetime.date(2026, 4, 1)
    result = svc._compute_upcoming_conferences(today, look_ahead_months=3)
    cutoff = today + datetime.timedelta(days=3 * 30 + 5)
    for ev in result:
        d = datetime.date.fromisoformat(ev["date"])
        assert d <= cutoff


# ── Block formatting ────────────────────────────────────────


def test_format_catalysts_block_empty(svc):
    block = svc._format_catalysts_block([])
    assert "无催化剂" in block or "行业窗口" in block


def test_format_catalysts_block_with_data(svc):
    catalysts = [
        {
            "催化剂预计时间": "2026-08-15",
            "资产名称": "PEG-001",
            "下一个催化剂": "Phase 2 readout",
            "催化剂类型": "Readout",
            "催化剂确定性": "High",
            "适应症": "NSCLC",
            "临床期次": "Phase 2",
        }
    ]
    block = svc._format_catalysts_block(catalysts)
    assert "2026-08-15" in block
    assert "PEG-001" in block
    assert "Phase 2 readout" in block
    assert "NSCLC" in block


def test_format_conferences_block_with_data(svc):
    today = datetime.date(2026, 4, 1)
    conferences = svc._compute_upcoming_conferences(today, 12)
    block = svc._format_conferences_block(conferences)
    # At least some major short names should appear
    shorts = {ev["short"] for ev in conferences}
    for short in shorts:
        assert short in block


def test_format_conferences_block_empty(svc):
    block = svc._format_conferences_block([])
    assert "无" in block


# ── Perspective blurb ───────────────────────────────────────


def test_perspective_blurb_seller(svc):
    blurb = svc._perspective_blurb("seller")
    assert "卖方" in blurb or "seller" in blurb.lower()


def test_perspective_blurb_buyer(svc):
    blurb = svc._perspective_blurb("buyer")
    assert "买方" in blurb or "buyer" in blurb.lower()


# ── Suggested commands ─────────────────────────────────────


def test_suggested_commands_basic_email_chip(svc):
    inp = TimingAdvisorInput(company_name="Eli Lilly", perspective="seller")
    chips = svc._build_suggested_commands(inp, [])
    assert len(chips) == 1
    cmd = chips[0]["command"]
    assert chips[0]["slug"] == "outreach-email"
    assert cmd.startswith("/email")
    assert 'to_company="Eli Lilly"' in cmd
    assert "from_perspective=seller" in cmd
    # No catalysts → no asset_context
    assert "asset_context" not in cmd


def test_suggested_commands_injects_asset_context_from_lead_catalyst(svc):
    inp = TimingAdvisorInput(company_name="Peg-Bio", perspective="buyer")
    catalysts = [
        {
            "资产名称": "PEG-001",
            "适应症": "NSCLC",
            "催化剂预计时间": "2026-08-15",
        }
    ]
    chips = svc._build_suggested_commands(inp, catalysts)
    cmd = chips[0]["command"]
    assert 'asset_context="PEG-001 — NSCLC"' in cmd
    assert "from_perspective=buyer" in cmd


def test_suggested_commands_handles_asset_without_indication(svc):
    inp = TimingAdvisorInput(company_name="Peg-Bio")
    catalysts = [{"资产名称": "PEG-001", "催化剂预计时间": "2026-08-15"}]
    chips = svc._build_suggested_commands(inp, catalysts)
    cmd = chips[0]["command"]
    assert 'asset_context="PEG-001"' in cmd
    # Should not have an em-dash trailing
    asset_str = cmd.split('asset_context="')[1].split('"')[0]
    assert "—" not in asset_str


# ── chat_tool_input_schema ──────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert schema["required"] == ["company_name"]
    assert schema["properties"]["perspective"]["default"] == "seller"
    assert schema["properties"]["look_ahead_months"]["default"] == 12
    assert schema["properties"]["look_ahead_months"]["minimum"] == 1
    assert schema["properties"]["look_ahead_months"]["maximum"] == 24


# ── L0/L1 quality pass (gap-fill prompt builder) ───────────


def test_gap_fill_prompt_filters_warns_and_includes_markdown():
    from services.reports.timing_advisor import _build_gap_fill_prompt

    class FakeFinding:
        severity = "fail"
        section = "recommended_windows"
        message = "缺日期范围"
        evidence = ""

    class FakeWarn:
        severity = "warn"
        # Unique marker — the static prompt template references
        # "建议尽快联系" as a counter-example so we can't use that as
        # the WARN message itself.
        section = "writing/vague_advice"
        message = "ZZ_UNIQUE_WARN_MARKER"
        evidence = ""

    class FakeAudit:
        findings = [FakeFinding(), FakeWarn()]

    prompt = _build_gap_fill_prompt("# Timing\n\ncontent", FakeAudit())
    assert "[recommended_windows] 缺日期范围" in prompt
    # WARN finding must not be injected into the fail_list
    assert "ZZ_UNIQUE_WARN_MARKER" not in prompt
    assert "# Timing" in prompt


def test_gap_fill_prompt_truncates_long_markdown():
    from services.reports.timing_advisor import _build_gap_fill_prompt

    class FakeAudit:
        findings = []

    huge_md = "x" * 70_000
    prompt = _build_gap_fill_prompt(huge_md, FakeAudit())
    assert prompt.count("x") <= 60_000
