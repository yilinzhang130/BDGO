"""
Unit tests for OutreachEmailService input + helper logic.

LLM call (`run()`) is integration territory — these tests cover:
  - Service registration in REPORT_SERVICES
  - Input model validation (defaults, invalid enums)
  - Per-purpose suggested_commands lifecycle chips
  - Markdown composition (header + body)
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.outreach_email import (
    _PURPOSE_FRAGMENTS,
    _PURPOSE_LABEL,
    _PURPOSES,
    OutreachEmailInput,
    OutreachEmailService,
)


def test_service_registered():
    assert "outreach-email" in REPORT_SERVICES
    svc = REPORT_SERVICES["outreach-email"]
    assert isinstance(svc, OutreachEmailService)
    assert svc.slug == "outreach-email"
    assert svc.output_formats == ["md"]
    assert svc.mode == "async"


def test_all_purposes_have_label_and_fragment():
    """Every value in the Literal must have a fragment + a human label."""
    expected = set(_PURPOSES)
    assert set(_PURPOSE_FRAGMENTS.keys()) == expected
    assert set(_PURPOSE_LABEL.keys()) == expected


def test_input_minimal_defaults():
    inp = OutreachEmailInput(to_company="Eli Lilly")
    assert inp.to_company == "Eli Lilly"
    assert inp.purpose == "cold_outreach"
    assert inp.from_perspective == "seller"
    assert inp.tone == "formal"
    assert inp.language == "en"


def test_input_full_buyer_perspective():
    inp = OutreachEmailInput(
        to_company="Peg-Bio",
        purpose="data_room_request",
        from_perspective="buyer",
        asset_context="PEG-001 — Phase 2 KRAS G12C inhibitor in NSCLC",
        from_company="GenericPharma",
        from_name="Sarah Chen",
        from_role="Head of External Innovation",
        tone="warm",
        language="zh",
        extra_context="CDA signed 2 weeks ago.",
    )
    assert inp.from_perspective == "buyer"
    assert inp.tone == "warm"
    assert inp.language == "zh"


def test_input_rejects_invalid_purpose():
    with pytest.raises(ValueError):
        OutreachEmailInput(
            to_company="X",
            purpose="invitation",  # type: ignore[arg-type]
        )


def test_input_rejects_invalid_perspective():
    with pytest.raises(ValueError):
        OutreachEmailInput(
            to_company="X",
            from_perspective="advisor",  # type: ignore[arg-type]
        )


def test_input_rejects_invalid_tone():
    with pytest.raises(ValueError):
        OutreachEmailInput(
            to_company="X",
            tone="aggressive",  # type: ignore[arg-type]
        )


def test_input_rejects_invalid_language():
    with pytest.raises(ValueError):
        OutreachEmailInput(
            to_company="X",
            language="ja",  # type: ignore[arg-type]
        )


def test_perspective_blurb_seller():
    svc = OutreachEmailService()
    blurb = svc._perspective_blurb("seller")
    assert "SELLER" in blurb


def test_perspective_blurb_buyer():
    svc = OutreachEmailService()
    blurb = svc._perspective_blurb("buyer")
    assert "BUYER" in blurb


def test_asset_block_with_context():
    svc = OutreachEmailService()
    inp = OutreachEmailInput(
        to_company="X",
        asset_context="PEG-001 KRAS G12C NSCLC",
    )
    assert "PEG-001" in svc._asset_block(inp)


def test_asset_block_without_context_falls_back():
    svc = OutreachEmailService()
    inp = OutreachEmailInput(to_company="X")
    block = svc._asset_block(inp)
    assert "no specific asset" in block.lower() or "generic" in block.lower()


def test_compose_markdown_includes_metadata_and_body():
    svc = OutreachEmailService()
    inp = OutreachEmailInput(
        to_company="Eli Lilly",
        purpose="cold_outreach",
        language="en",
        tone="formal",
    )
    body = "Subject: Test\n\nBody here.\n\n— BD"
    md = svc._compose_markdown(inp, body, "2026-04-26")
    assert "BD Go Outreach Email" in md
    assert "Eli Lilly" in md
    assert "cold_outreach" in md
    assert "Body here." in md


def test_suggested_commands_cold_outreach_offers_cda():
    """Cold outreach → next step is CDA."""
    svc = OutreachEmailService()
    inp = OutreachEmailInput(to_company="Eli Lilly", purpose="cold_outreach")
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 1
    assert sc[0]["slug"] == "legal-review"
    assert "contract_type=cda" in sc[0]["command"]
    assert 'counterparty="Eli Lilly"' in sc[0]["command"]


def test_suggested_commands_cda_followup_offers_dd():
    """CDA followup → assume signed → next is DD."""
    svc = OutreachEmailService()
    inp = OutreachEmailInput(to_company="Eli Lilly", purpose="cda_followup")
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 1
    assert sc[0]["slug"] == "dd-checklist"
    assert 'company="Eli Lilly"' in sc[0]["command"]


@pytest.mark.parametrize(
    "purpose",
    ["data_room_request", "term_sheet_send", "meeting_request", "follow_up"],
)
def test_suggested_commands_other_purposes_silent(purpose):
    """Mid-lifecycle / generic purposes don't auto-suggest a single next step."""
    svc = OutreachEmailService()
    inp = OutreachEmailInput(to_company="X", purpose=purpose)
    assert svc._build_suggested_commands(inp) == []


def test_chat_tool_input_schema_required_only_to_company():
    svc = OutreachEmailService()
    schema = svc.chat_tool_input_schema
    assert schema["required"] == ["to_company"]
    assert schema["properties"]["purpose"]["default"] == "cold_outreach"
    assert schema["properties"]["from_perspective"]["default"] == "seller"
    assert "to_company" in schema["properties"]
    assert "asset_context" in schema["properties"]
    assert "extra_context" in schema["properties"]
