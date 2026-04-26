"""
Unit tests for OutreachLogService.

The DB write itself (`run()`) is integration territory — it requires a
live Postgres + an authenticated user. These tests cover:
  - Service registration
  - Input model validation (defaults, invalid enums)
  - _format_confirmation markdown shape
  - Per-status suggested_commands chip wiring
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.outreach_log import OutreachLogInput, OutreachLogService


@pytest.fixture
def svc() -> OutreachLogService:
    return OutreachLogService()


def test_service_registered():
    assert "outreach-log" in REPORT_SERVICES
    s = REPORT_SERVICES["outreach-log"]
    assert isinstance(s, OutreachLogService)
    assert s.slug == "outreach-log"
    assert s.output_formats == ["md"]


def test_input_minimal_defaults():
    inp = OutreachLogInput(to_company="Pfizer")
    assert inp.to_company == "Pfizer"
    assert inp.purpose == "cold_outreach"
    assert inp.status == "sent"
    assert inp.channel == "email"
    assert inp.perspective is None


def test_input_full():
    inp = OutreachLogInput(
        to_company="Pfizer",
        purpose="cda_followup",
        status="replied",
        channel="linkedin",
        to_contact="Sarah Chen",
        asset_context="PEG-001 — NSCLC",
        perspective="seller",
        subject="Following up on PEG-001 conversation",
        notes="They asked for Phase 1 ORR data.",
    )
    assert inp.purpose == "cda_followup"
    assert inp.status == "replied"
    assert inp.channel == "linkedin"


def test_input_rejects_invalid_purpose():
    with pytest.raises(ValueError):
        OutreachLogInput(to_company="X", purpose="invitation")  # type: ignore[arg-type]


def test_input_rejects_invalid_status():
    with pytest.raises(ValueError):
        OutreachLogInput(to_company="X", status="ghosted")  # type: ignore[arg-type]


def test_input_rejects_invalid_channel():
    with pytest.raises(ValueError):
        OutreachLogInput(to_company="X", channel="carrier_pigeon")  # type: ignore[arg-type]


# ── _format_confirmation ────────────────────────────────────


def test_format_confirmation_minimal(svc):
    inp = OutreachLogInput(to_company="Pfizer")
    md = svc._format_confirmation(inp, event_id=42)
    assert "#42" in md or "event #42" in md.lower()
    assert "Pfizer" in md
    assert "cold_outreach" in md
    assert "sent" in md


def test_format_confirmation_full(svc):
    inp = OutreachLogInput(
        to_company="Pfizer",
        purpose="cda_followup",
        status="replied",
        to_contact="Sarah Chen",
        asset_context="PEG-001 — NSCLC",
        perspective="seller",
        subject="Following up",
        notes="Asked for ORR.",
    )
    md = svc._format_confirmation(inp, event_id=99)
    assert "Sarah Chen" in md
    assert "PEG-001" in md
    assert "Following up" in md
    assert "Asked for ORR" in md
    assert "seller" in md


# ── _build_suggested_commands ───────────────────────────────


def test_chip_cda_signed_offers_dd(svc):
    inp = OutreachLogInput(to_company="Pfizer", status="cda_signed", purpose="cda_followup")
    chips = svc._build_suggested_commands(inp)
    assert len(chips) == 1
    assert chips[0]["slug"] == "dd-checklist"
    assert 'company="Pfizer"' in chips[0]["command"]


def test_chip_ts_signed_routes_to_draft_license_seller_default(svc):
    """ts_signed default (no perspective) → /draft-license with our_role=licensor.

    Previously fired /legal contract_type=license — but /legal is review
    mode and requires contract_text the user doesn't have yet. Now routes
    to /draft-license so the BD can actually start the next step.
    """
    inp = OutreachLogInput(
        to_company="Pfizer",
        status="ts_signed",
        purpose="term_sheet_send",
        asset_context="PEG-001 (NSCLC)",
    )
    chips = svc._build_suggested_commands(inp)
    assert len(chips) == 1
    assert chips[0]["slug"] == "draft-license"
    cmd = chips[0]["command"]
    assert cmd.startswith("/draft-license")
    assert "our_role=licensor" in cmd
    assert 'licensee="Pfizer"' in cmd
    assert 'asset_name="PEG-001 (NSCLC)"' in cmd


def test_chip_ts_signed_buyer_perspective_inverts_role(svc):
    """When we're the buyer (licensee), counterparty is licensor."""
    inp = OutreachLogInput(
        to_company="BeiGene",
        status="ts_signed",
        purpose="term_sheet_send",
        perspective="buyer",
    )
    chips = svc._build_suggested_commands(inp)
    cmd = chips[0]["command"]
    assert "our_role=licensee" in cmd
    assert 'licensor="BeiGene"' in cmd


def test_chip_sent_offers_view_thread(svc):
    inp = OutreachLogInput(to_company="Pfizer", status="sent")
    chips = svc._build_suggested_commands(inp)
    assert len(chips) == 1
    assert chips[0]["slug"] == "outreach-list"
    assert chips[0]["command"].startswith("/outreach")


@pytest.mark.parametrize("status", ["replied", "meeting"])
def test_chip_active_status_offers_view_thread(svc, status):
    inp = OutreachLogInput(to_company="Pfizer", status=status)
    chips = svc._build_suggested_commands(inp)
    assert len(chips) == 1
    assert chips[0]["slug"] == "outreach-list"


@pytest.mark.parametrize("status", ["passed", "dead", "definitive_signed"])
def test_chip_terminal_status_silent(svc, status):
    """Terminal / closed statuses don't suggest further chips."""
    inp = OutreachLogInput(to_company="Pfizer", status=status)
    assert svc._build_suggested_commands(inp) == []


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert schema["required"] == ["to_company"]
    assert schema["properties"]["purpose"]["default"] == "cold_outreach"
    assert schema["properties"]["status"]["default"] == "sent"
    assert schema["properties"]["channel"]["default"] == "email"
    assert "purpose" in schema["properties"]
    assert "status" in schema["properties"]
    assert "channel" in schema["properties"]
