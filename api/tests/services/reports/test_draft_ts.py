"""
Unit tests for DraftTSService.

LLM call (`run()`) is integration territory. These tests cover:
  - Service registration
  - Input model validation (required fields, our_role enum, ranges)
  - FinancialTerms nested model defaults
  - _fmt_amount / _fmt_royalty_range helper formatting
  - _build_suggested_commands chip wiring per our_role
  - SYSTEM_PROMPT covers all 13 sections + binding map
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.draft_ts import (
    _BINDING_SECTIONS,
    SYSTEM_PROMPT,
    DraftTSInput,
    DraftTSService,
    FinancialTerms,
)


@pytest.fixture
def svc() -> DraftTSService:
    return DraftTSService()


def _minimal_input(**overrides) -> DraftTSInput:
    base = {
        "licensor": "Peg-Bio",
        "licensee": "Eli Lilly",
        "our_role": "licensor",
        "asset_name": "PEG-001",
        "indication": "NSCLC",
        "phase": "Phase 2",
    }
    base.update(overrides)
    return DraftTSInput(**base)


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "draft-ts" in REPORT_SERVICES
    s = REPORT_SERVICES["draft-ts"]
    assert isinstance(s, DraftTSService)
    assert s.slug == "draft-ts"
    assert "docx" in s.output_formats and "md" in s.output_formats


# ── Input validation ───────────────────────────────────────


def test_input_minimal():
    inp = _minimal_input()
    assert inp.our_role == "licensor"
    assert inp.territory == "Worldwide"
    assert inp.field_of_use == "All therapeutic uses"
    assert inp.exclusivity == "exclusive"
    assert inp.sublicense_allowed is True
    assert inp.term_years == 15
    assert inp.no_shop_days == 60
    assert inp.governing_law == "Hong Kong"
    assert inp.dispute_forum == "HKIAC"
    assert isinstance(inp.financial_terms, FinancialTerms)
    # All financial terms blank by default
    assert inp.financial_terms.upfront_usd_mm is None


def test_input_full_with_financial_terms():
    inp = DraftTSInput(
        licensor="Peg-Bio",
        licensee="Eli Lilly",
        our_role="licensor",
        asset_name="PEG-001",
        indication="NSCLC",
        target="KRAS G12C",
        modality="adc",
        phase="Phase 2",
        territory="ex-China",
        field_of_use="Oncology only",
        exclusivity="co-exclusive",
        sublicense_allowed=False,
        financial_terms=FinancialTerms(
            upfront_usd_mm=50,
            equity_pct=2.5,
            dev_milestones_total_usd_mm=300,
            sales_milestones_total_usd_mm=500,
            royalty_low_pct=8,
            royalty_high_pct=15,
            deal_total_anchor_usd_mm=850,
        ),
        term_years=20,
        no_shop_days=90,
        governing_law="New York",
        dispute_forum="ICC",
        extra_context="FDA Breakthrough Designation granted Oct 2025.",
    )
    assert inp.modality == "adc"
    assert inp.exclusivity == "co-exclusive"
    assert inp.financial_terms.upfront_usd_mm == 50


def test_input_rejects_missing_required():
    with pytest.raises(ValueError):
        DraftTSInput(
            licensor="X",
            licensee="Y",
            # missing our_role
            asset_name="Z",
            indication="W",
            phase="Phase 2",
        )  # type: ignore[call-arg]


def test_input_rejects_invalid_our_role():
    with pytest.raises(ValueError):
        _minimal_input(our_role="advisor")


def test_input_rejects_invalid_phase():
    with pytest.raises(ValueError):
        _minimal_input(phase="Phase 4")


def test_input_rejects_invalid_modality():
    with pytest.raises(ValueError):
        _minimal_input(modality="lipid_nanoparticle")


def test_input_rejects_invalid_exclusivity():
    with pytest.raises(ValueError):
        _minimal_input(exclusivity="open")


def test_input_term_years_range():
    with pytest.raises(ValueError):
        _minimal_input(term_years=0)
    with pytest.raises(ValueError):
        _minimal_input(term_years=50)


def test_input_no_shop_days_range():
    with pytest.raises(ValueError):
        _minimal_input(no_shop_days=-1)
    with pytest.raises(ValueError):
        _minimal_input(no_shop_days=200)


# ── Formatting helpers ─────────────────────────────────────


def test_fmt_amount_none(svc):
    assert svc._fmt_amount(None, "$", "M") == "[TBD]"


def test_fmt_amount_integer(svc):
    assert svc._fmt_amount(50.0, "$", "M") == "$50M"
    assert svc._fmt_amount(100, "$", "M") == "$100M"


def test_fmt_amount_decimal(svc):
    assert svc._fmt_amount(2.5, "", "%") == "2.5%"


def test_fmt_royalty_range_both(svc):
    assert svc._fmt_royalty_range(8, 15) == "8-15% tiered"


def test_fmt_royalty_range_low_only(svc):
    assert svc._fmt_royalty_range(8, None) == "≥ 8%"


def test_fmt_royalty_range_high_only(svc):
    assert svc._fmt_royalty_range(None, 15) == "≤ 15%"


def test_fmt_royalty_range_neither(svc):
    assert svc._fmt_royalty_range(None, None) == "[TBD]"


# ── System prompt content ──────────────────────────────────


def test_system_prompt_covers_all_13_sections():
    """Verify every numbered section appears in the prompt template."""
    expected = [
        "Parties",
        "Subject Asset",
        "Field of Use",
        "Territory",
        "Exclusivity",
        "Financial Terms",
        "Diligence",
        "IP Ownership",
        "Reps & Warranties",
        "Confidentiality",
        "No-Shop",
        "Term & Termination",
        "Governing Law",
    ]
    for section in expected:
        assert section in SYSTEM_PROMPT, f"section '{section}' missing from prompt"


def test_system_prompt_lists_binding_sections():
    """Binding map is required for the LLM to mark sections correctly."""
    assert "BINDING" in SYSTEM_PROMPT
    assert "Confidentiality" in SYSTEM_PROMPT
    # All canonical binding sections referenced
    for s in _BINDING_SECTIONS:
        # split on / so multi-word sections still match
        keyword = s.split(" / ")[0]
        assert keyword.split()[0] in SYSTEM_PROMPT


def test_system_prompt_disclaims_legal_advice():
    assert "Not legal advice" in SYSTEM_PROMPT
    assert "counsel review" in SYSTEM_PROMPT.lower() or "counsel" in SYSTEM_PROMPT.lower()


def test_system_prompt_emphasizes_perspective_adaptation():
    """LLM must adapt language to our_role."""
    assert "licensor-favorable" in SYSTEM_PROMPT or "licensor" in SYSTEM_PROMPT
    assert "licensee-favorable" in SYSTEM_PROMPT or "licensee" in SYSTEM_PROMPT


# ── Suggested commands ────────────────────────────────────


def test_chips_always_offers_legal_review(svc):
    inp = _minimal_input()
    chips = svc._build_suggested_commands(inp)
    review = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert review is not None
    assert "contract_type=ts" in review["command"]


def test_chips_licensor_role_offers_seller_dd_prep(svc):
    inp = _minimal_input(our_role="licensor")
    chips = svc._build_suggested_commands(inp)
    dd = next((c for c in chips if c["slug"] == "dd-checklist"), None)
    assert dd is not None
    assert "perspective=seller" in dd["command"]


def test_chips_licensee_role_no_dd_prep(svc):
    """As licensee (buyer), TS draft → review only; we already did our DD."""
    inp = _minimal_input(our_role="licensee")
    chips = svc._build_suggested_commands(inp)
    assert not any(c["slug"] == "dd-checklist" for c in chips)


def test_chips_review_command_party_position_per_role(svc):
    """Party position in /legal review depends on our_role."""
    licensor_inp = _minimal_input(our_role="licensor")
    licensor_chip = svc._build_suggested_commands(licensor_inp)[0]
    # As licensor (我方授权出去) we are 乙方 in legal review
    assert "乙方" in licensor_chip["command"]
    # Counterparty is the licensee
    assert 'counterparty="Eli Lilly"' in licensor_chip["command"]

    licensee_inp = _minimal_input(our_role="licensee")
    licensee_chip = svc._build_suggested_commands(licensee_inp)[0]
    # As licensee (我方授权进来) we are 甲方
    assert "甲方" in licensee_chip["command"]
    assert 'counterparty="Peg-Bio"' in licensee_chip["command"]


def test_chips_review_includes_project_name(svc):
    inp = _minimal_input()
    chip = svc._build_suggested_commands(inp)[0]
    assert 'project_name="PEG-001 (NSCLC)"' in chip["command"]


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    expected_required = {"licensor", "licensee", "our_role", "asset_name", "indication", "phase"}
    assert set(schema["required"]) == expected_required
    assert schema["properties"]["our_role"]["enum"] == ["licensor", "licensee"]
    assert schema["properties"]["term_years"]["default"] == 15
    assert schema["properties"]["term_years"]["maximum"] == 30
    assert schema["properties"]["no_shop_days"]["default"] == 60
    assert "financial_terms" in schema["properties"]
    assert schema["properties"]["financial_terms"]["type"] == "object"
