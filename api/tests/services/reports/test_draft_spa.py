"""Unit tests for DraftSPAService."""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.draft_spa import (
    SYSTEM_PROMPT,
    DraftSPAInput,
    DraftSPAService,
)


@pytest.fixture
def svc() -> DraftSPAService:
    return DraftSPAService()


def _minimal_input(**overrides) -> DraftSPAInput:
    base = {
        "buyer": "Pfizer",
        "seller": "Founders & VCs of TargetCo",
        "target_company": "TargetCo",
        "our_role": "buyer",
    }
    base.update(overrides)
    return DraftSPAInput(**base)


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "draft-spa" in REPORT_SERVICES
    s = REPORT_SERVICES["draft-spa"]
    assert isinstance(s, DraftSPAService)
    assert "docx" in s.output_formats and "md" in s.output_formats


# ── Input validation ───────────────────────────────────────


def test_input_minimal_defaults():
    inp = _minimal_input()
    assert inp.our_role == "buyer"
    assert inp.deal_structure == "stock_purchase"
    assert inp.price_structure == "all_cash"
    assert inp.indemnity_cap_pct_of_price == 15.0
    assert inp.indemnity_basket_usd_mm == 0.5
    assert inp.indemnity_survival_months == 18
    assert inp.has_mac_clause is True
    assert inp.interim_period_months == 6
    assert inp.non_compete_months == 24
    assert inp.non_solicit_months == 24
    assert inp.governing_law == "Delaware"
    assert inp.dispute_forum == "Delaware Court of Chancery"


def test_input_full_overrides():
    inp = DraftSPAInput(
        buyer="Roche",
        seller="X-Founders",
        target_company="TargetCo",
        our_role="seller",
        deal_structure="reverse_triangular_merger",
        price_structure="cash_plus_earnout",
        enterprise_value_usd_mm=500.0,
        cash_at_closing_usd_mm=400.0,
        stock_consideration_pct=20.0,
        earnout_max_usd_mm=150.0,
        indemnity_cap_pct_of_price=20.0,
        indemnity_basket_usd_mm=1.0,
        indemnity_survival_months=24,
        requires_hsr_approval=True,
        requires_cfius_review=True,
        requires_china_antitrust=True,
        has_mac_clause=False,
        interim_period_months=9,
        non_compete_months=36,
        non_solicit_months=36,
        governing_law="New York",
        dispute_forum="JAMS New York",
    )
    assert inp.deal_structure == "reverse_triangular_merger"
    assert inp.price_structure == "cash_plus_earnout"
    assert inp.requires_hsr_approval is True
    assert inp.requires_cfius_review is True
    assert inp.requires_china_antitrust is True
    assert inp.has_mac_clause is False


def test_input_rejects_missing_required():
    with pytest.raises(ValueError):
        DraftSPAInput(
            buyer="Pfizer",
            seller="X",
            # missing target_company + our_role
        )  # type: ignore[call-arg]


def test_input_rejects_invalid_our_role():
    with pytest.raises(ValueError):
        _minimal_input(our_role="advisor")


def test_input_rejects_invalid_deal_structure():
    with pytest.raises(ValueError):
        _minimal_input(deal_structure="lbo")


def test_input_rejects_invalid_price_structure():
    with pytest.raises(ValueError):
        _minimal_input(price_structure="seller_note")


def test_input_indemnity_cap_range():
    with pytest.raises(ValueError):
        _minimal_input(indemnity_cap_pct_of_price=-1)
    with pytest.raises(ValueError):
        _minimal_input(indemnity_cap_pct_of_price=101)


def test_input_indemnity_survival_range():
    with pytest.raises(ValueError):
        _minimal_input(indemnity_survival_months=5)
    with pytest.raises(ValueError):
        _minimal_input(indemnity_survival_months=73)


def test_input_interim_period_range():
    with pytest.raises(ValueError):
        _minimal_input(interim_period_months=0)
    with pytest.raises(ValueError):
        _minimal_input(interim_period_months=25)


def test_input_non_compete_zero_allowed():
    """Zero is a valid value (= no NC) — only negative or > 60 should fail."""
    inp = _minimal_input(non_compete_months=0, non_solicit_months=0)
    assert inp.non_compete_months == 0
    assert inp.non_solicit_months == 0


def test_input_non_compete_range():
    with pytest.raises(ValueError):
        _minimal_input(non_compete_months=-1)
    with pytest.raises(ValueError):
        _minimal_input(non_compete_months=61)


# ── System prompt content ──────────────────────────────────


def test_system_prompt_covers_all_13_sections():
    expected = [
        "Parties",
        "Definitions",
        "Purchase Price",
        "Closing Conditions",
        "Interim Period",
        "Reps & Warranties",
        "Fundamentals",
        "General Business",
        "Indemnification",
        "Termination",
        "Tax Matters",
        "Post-Closing",
        "Escrow",
        "Governing Law",
    ]
    for s in expected:
        assert s in SYSTEM_PROMPT, f"section keyword '{s}' missing from prompt"


def test_system_prompt_disclaims_legal_advice():
    assert "Not legal advice" in SYSTEM_PROMPT
    assert "counsel" in SYSTEM_PROMPT.lower()


def test_system_prompt_warns_skeleton_only():
    """SPAs run 100+ pages — prompt must call out skeleton nature."""
    assert "100" in SYSTEM_PROMPT and "skeleton" in SYSTEM_PROMPT.lower()


def test_system_prompt_requires_6_risks():
    """SPA is the most complex /draft-X — needs ≥6 risks."""
    assert "≥ 6" in SYSTEM_PROMPT or "6 条" in SYSTEM_PROMPT or "6 commercial-risk" in SYSTEM_PROMPT


def test_system_prompt_indemnification_three_tuple():
    """Cap + basket + survival are the SPA-specific hallmark."""
    assert "cap" in SYSTEM_PROMPT.lower()
    assert "basket" in SYSTEM_PROMPT.lower()
    assert "survival" in SYSTEM_PROMPT.lower()


def test_system_prompt_lists_regulatory_filings():
    """Closing conditions section must reference HSR / CFIUS / SAMR."""
    for kw in ["HSR", "CFIUS", "SAMR"]:
        assert kw in SYSTEM_PROMPT


def test_system_prompt_rw_split_fundamentals_vs_general():
    """R&W must distinguish Fundamentals (uncapped) from General Business."""
    assert "Fundamental" in SYSTEM_PROMPT
    assert "General" in SYSTEM_PROMPT or "general" in SYSTEM_PROMPT


# ── Formatting helpers ─────────────────────────────────────


def test_fmt_amount_none(svc):
    assert svc._fmt_amount(None, "$", "M") == "[TBD]"


def test_fmt_amount_integer(svc):
    assert svc._fmt_amount(500, "$", "M") == "$500M"


def test_fmt_amount_decimal(svc):
    assert svc._fmt_amount(2.5, "", "%") == "2.5%"


# ── Suggested commands ────────────────────────────────────


def test_chips_offers_legal_review(svc):
    inp = _minimal_input()
    chips = svc._build_suggested_commands(inp)
    review = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert review is not None
    assert "contract_type=spa" in review["command"]


def test_chips_buyer_is_jiafang(svc):
    """SPA convention: buyer = 甲方."""
    inp = _minimal_input(our_role="buyer")
    chip = svc._build_suggested_commands(inp)[0]
    assert "甲方" in chip["command"]
    assert 'counterparty="Founders & VCs of TargetCo"' in chip["command"]


def test_chips_seller_is_yifang(svc):
    """SPA convention: seller = 乙方."""
    inp = _minimal_input(our_role="seller")
    chip = svc._build_suggested_commands(inp)[0]
    assert "乙方" in chip["command"]
    assert 'counterparty="Pfizer"' in chip["command"]


def test_chips_project_includes_deal_structure(svc):
    inp = _minimal_input(deal_structure="merger")
    chip = svc._build_suggested_commands(inp)[0]
    assert "merger" in chip["command"]
    assert "TargetCo" in chip["command"]


# ── Gap-fill prompt builder ────────────────────────────────


def test_gap_fill_prompt_filters_warns():
    from services.reports.draft_spa import _build_gap_fill_prompt

    class FakeFinding:
        severity = "fail"
        section = "indemnification"
        message = "缺 cap/basket/survival"
        evidence = ""

    class FakeWarn:
        severity = "warn"
        section = "writing/marketing_hyperbole"
        message = "ZZ_UNIQUE_WARN_FOR_SPA"
        evidence = ""

    class FakeAudit:
        findings = [FakeFinding(), FakeWarn()]

    prompt = _build_gap_fill_prompt("# SPA\n\ncontent", FakeAudit())
    assert "[indemnification] 缺 cap/basket/survival" in prompt
    assert "ZZ_UNIQUE_WARN_FOR_SPA" not in prompt


def test_gap_fill_prompt_truncates():
    from services.reports.draft_spa import _build_gap_fill_prompt

    class FakeAudit:
        findings = []

    huge_md = "x" * 70_000
    prompt = _build_gap_fill_prompt(huge_md, FakeAudit())
    assert prompt.count("x") <= 60_000


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    expected_required = {"buyer", "seller", "target_company", "our_role"}
    assert set(schema["required"]) == expected_required
    assert schema["properties"]["deal_structure"]["default"] == "stock_purchase"
    assert schema["properties"]["price_structure"]["default"] == "all_cash"
    assert schema["properties"]["indemnity_cap_pct_of_price"]["default"] == 15.0
    assert schema["properties"]["indemnity_basket_usd_mm"]["default"] == 0.5
    assert schema["properties"]["indemnity_survival_months"]["default"] == 18
    assert schema["properties"]["governing_law"]["default"] == "Delaware"
