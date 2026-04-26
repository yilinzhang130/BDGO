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


def test_chips_licensing_offers_cda(svc):
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
        indication="NSCLC",
        purpose="licensing",
    )
    chips = svc._build_suggested_commands(inp)
    cda = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert cda is not None
    assert "contract_type=cda" in cda["command"]
    assert 'project_name="PEG-001 (NSCLC)"' in cda["command"]


def test_chips_partnership_offers_cda(svc):
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
        purpose="partnership",
    )
    chips = svc._build_suggested_commands(inp)
    assert any(c["slug"] == "legal-review" for c in chips)


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


def test_chips_project_name_omits_indication_when_absent(svc):
    inp = DataRoomInput(
        company_name="Peg-Bio",
        asset_name="PEG-001",
        modality="small_molecule",
        phase="Phase 2",
        purpose="licensing",
        # no indication
    )
    chips = svc._build_suggested_commands(inp)
    cda = next(c for c in chips if c["slug"] == "legal-review")
    # Project name has just the asset, no parenthesized indication
    assert 'project_name="PEG-001"' in cda["command"]


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert set(schema["required"]) == {"company_name", "asset_name", "modality", "phase"}
    assert schema["properties"]["purpose"]["default"] == "licensing"
    assert schema["properties"]["audience"]["default"] == "mnc_buyer"
    assert set(schema["properties"]["purpose"]["enum"]) == set(_PURPOSES)
    assert set(schema["properties"]["audience"]["enum"]) == set(_AUDIENCES)
