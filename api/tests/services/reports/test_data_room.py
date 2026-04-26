"""
Unit tests for DataRoomService.

LLM call (`run()`) is integration territory. These tests cover:
  - Service registration
  - Input model validation (required fields, modality + phase enums)
  - _build_suggested_commands chip wiring per purpose
  - chat_tool_input_schema shape
  - SYSTEM_PROMPT covers all 8 categories + key adaptation rules
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.data_room import (
    _AUDIENCES,
    _CATEGORIES,
    _PURPOSES,
    SYSTEM_PROMPT,
    DataRoomInput,
    DataRoomService,
)


@pytest.fixture
def svc() -> DataRoomService:
    return DataRoomService()


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "data-room" in REPORT_SERVICES
    s = REPORT_SERVICES["data-room"]
    assert isinstance(s, DataRoomService)
    assert s.slug == "data-room"
    assert "docx" in s.output_formats and "md" in s.output_formats


def test_eight_categories_defined():
    assert len(_CATEGORIES) == 8
    keys = {k for k, _ in _CATEGORIES}
    assert keys == {
        "clinical",
        "cmc",
        "nonclinical",
        "regulatory",
        "ip",
        "quality",
        "commercial",
        "corporate",
    }


# ── Input model ─────────────────────────────────────────────


def test_input_minimal_required_only():
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
    )
    # Defaults applied
    assert inp.purpose == "licensing"
    assert inp.audience == "mnc_buyer"
    assert inp.indication is None
    assert inp.target is None


def test_input_full():
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="adc",
        phase="Phase 3",
        indication="HER2+ breast cancer",
        target="HER2",
        purpose="acquisition",
        audience="private_equity",
        extra_context="FDA breakthrough designation granted 2025-06.",
    )
    assert inp.modality == "adc"
    assert inp.purpose == "acquisition"
    assert inp.audience == "private_equity"


def test_input_rejects_missing_required():
    with pytest.raises(ValueError):
        DataRoomInput(
            company_name="Peg-Bio",
            # missing asset_name
            modality="small_molecule",
            phase="Phase 2",
        )  # type: ignore[call-arg]


def test_input_rejects_invalid_modality():
    with pytest.raises(ValueError):
        DataRoomInput(
            company_name="X",
            asset_name="Y",
            modality="lipid_nanoparticle",  # type: ignore[arg-type]
            phase="Phase 2",
        )


def test_input_rejects_invalid_phase():
    with pytest.raises(ValueError):
        DataRoomInput(
            company_name="X",
            asset_name="Y",
            modality="small_molecule",
            phase="Phase 4",  # type: ignore[arg-type]
        )


def test_input_rejects_invalid_purpose():
    with pytest.raises(ValueError):
        DataRoomInput(
            company_name="X",
            asset_name="Y",
            modality="small_molecule",
            phase="Phase 2",
            purpose="cooperation",  # type: ignore[arg-type]
        )


def test_input_rejects_invalid_audience():
    with pytest.raises(ValueError):
        DataRoomInput(
            company_name="X",
            asset_name="Y",
            modality="small_molecule",
            phase="Phase 2",
            audience="vc",  # type: ignore[arg-type]
        )


# ── System prompt content ──────────────────────────────────


def test_system_prompt_covers_eight_categories():
    """Every category must be referenced in the prompt template."""
    expected = [
        "Clinical",
        "CMC",
        "Nonclinical",
        "Regulatory",
        "IP",
        "Quality",
        "Commercial",
        "Corporate",
    ]
    for cat in expected:
        assert cat in SYSTEM_PROMPT, f"category {cat} missing from SYSTEM_PROMPT"


def test_system_prompt_covers_key_modalities():
    """Modality-adaptation guidance must be in the prompt for major types."""
    for kw in ("small_molecule", "mAb", "ADC", "cell_gene_therapy", "radioligand"):
        assert kw in SYSTEM_PROMPT


def test_system_prompt_covers_priority_emojis():
    """The 3-tier priority system must be documented."""
    assert "🔴" in SYSTEM_PROMPT
    assert "🟡" in SYSTEM_PROMPT
    assert "🟢" in SYSTEM_PROMPT


# ── _build_suggested_commands ──────────────────────────────


def test_chips_always_offers_seller_dd_prep(svc):
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
    )
    chips = svc._build_suggested_commands(inp)
    dd = next((c for c in chips if c["slug"] == "dd-checklist"), None)
    assert dd is not None
    assert "perspective=seller" in dd["command"]
    assert 'company="Peg-Bio"' in dd["command"]
    assert 'asset_name="PEG-001"' in dd["command"]


def test_chips_licensing_does_not_offer_broken_cda_chip(svc):
    """Previously: licensing/partnership purpose offered "Draft CDA / NDA"
    routing to /legal contract_type=cda — but /legal is review-mode and
    needs contract_text the user doesn't have, plus there's no /draft-cda
    service. The chip was a dead-end. Removed in fix."""
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
        indication="NSCLC",
        purpose="licensing",
    )
    chips = svc._build_suggested_commands(inp)
    assert not any(c["slug"] == "legal-review" for c in chips), (
        "Broken CDA chip should not appear; user can /legal manually when they have a CDA to review"
    )
    # The valuable seller-DD-prep chip should still be there
    assert any(c["slug"] == "dd-checklist" for c in chips)


def test_chips_partnership_does_not_offer_broken_cda_chip(svc):
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
        purpose="partnership",
    )
    chips = svc._build_suggested_commands(inp)
    assert not any(c["slug"] == "legal-review" for c in chips)


@pytest.mark.parametrize("purpose", ["acquisition", "dd_response"])
def test_chips_acquisition_or_dd_response_no_cda(svc, purpose):
    """Acquisition / dd_response usually means CDA already signed → don't suggest."""
    inp = DataRoomInput(
        company_name="X",
        asset_name="Y",
        modality="small_molecule",
        phase="Phase 2",
        purpose=purpose,
    )
    chips = svc._build_suggested_commands(inp)
    assert not any(c["slug"] == "legal-review" for c in chips)


def test_chips_dd_prep_present_regardless_of_indication(svc):
    """The DD-prep chip is the always-on seller value-add — must work
    even without indication. (Previously this test verified project_name
    formatting on the now-removed CDA chip.)"""
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
        purpose="licensing",
        # no indication
    )
    chips = svc._build_suggested_commands(inp)
    dd = next(c for c in chips if c["slug"] == "dd-checklist")
    assert 'company="Peg-Bio"' in dd["command"]
    assert 'asset_name="PEG-001"' in dd["command"]


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert set(schema["required"]) == {"company_name", "asset_name", "modality", "phase"}
    assert schema["properties"]["purpose"]["default"] == "licensing"
    assert schema["properties"]["audience"]["default"] == "mnc_buyer"
    assert set(schema["properties"]["purpose"]["enum"]) == set(_PURPOSES)
    assert set(schema["properties"]["audience"]["enum"]) == set(_AUDIENCES)


# ── L0/L1 quality pass (gap-fill prompt builder) ───────────


def test_gap_fill_prompt_filters_warns_and_includes_markdown():
    from services.reports.data_room import _build_gap_fill_prompt

    class FakeFinding:
        severity = "fail"
        section = "clinical_data"
        message = "category 缺失"
        evidence = ""

    class FakeWarn:
        severity = "warn"
        section = "writing/marketing_hyperbole"
        message = "industry-leading"
        evidence = ""

    class FakeAudit:
        findings = [FakeFinding(), FakeWarn()]

    prompt = _build_gap_fill_prompt("# Sample\n\ncontent", FakeAudit())
    assert "[clinical_data] category 缺失" in prompt
    # WARN filtered out
    assert "industry-leading" not in prompt
    assert "# Sample" in prompt


def test_gap_fill_prompt_truncates_long_markdown():
    from services.reports.data_room import _build_gap_fill_prompt

    class FakeAudit:
        findings = []

    huge_md = "x" * 70_000
    prompt = _build_gap_fill_prompt(huge_md, FakeAudit())
    assert prompt.count("x") <= 60_000
