"""
Unit tests for ImportReplyService.

LLM call + DB write (`run()`) is integration territory. These tests cover:
  - Service registration
  - Input model validation
  - _normalize_status / _normalize_purpose mappings
  - _compose_notes assembly
  - _format_confirmation markdown shape
  - _build_suggested_commands chip wiring per status
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.import_reply import ImportReplyInput, ImportReplyService


@pytest.fixture
def svc() -> ImportReplyService:
    return ImportReplyService()


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "import-reply" in REPORT_SERVICES
    s = REPORT_SERVICES["import-reply"]
    assert isinstance(s, ImportReplyService)
    assert s.output_formats == ["md"]


# ── Input model ─────────────────────────────────────────────


def test_input_minimal():
    inp = ImportReplyInput(reply_text="x" * 50)
    assert inp.to_company_hint is None
    assert inp.perspective is None


def test_input_full():
    inp = ImportReplyInput(
        reply_text="Hi Sarah, thanks for reaching out about PEG-001..." * 5,
        to_company_hint="Eli Lilly",
        perspective="seller",
        notes_prefix="Pre-meeting context:",
    )
    assert inp.to_company_hint == "Eli Lilly"
    assert inp.perspective == "seller"


def test_input_rejects_too_short():
    with pytest.raises(ValueError):
        ImportReplyInput(reply_text="hi")


def test_input_rejects_too_long():
    with pytest.raises(ValueError):
        ImportReplyInput(reply_text="x" * 25_000)


def test_input_rejects_invalid_perspective():
    with pytest.raises(ValueError):
        ImportReplyInput(
            reply_text="x" * 50,
            perspective="advisor",  # type: ignore[arg-type]
        )


# ── _normalize_status ───────────────────────────────────────


def test_normalize_status_canonical(svc):
    assert svc._normalize_status("replied") == "replied"
    assert svc._normalize_status("meeting") == "meeting"
    assert svc._normalize_status("cda_signed") == "cda_signed"
    assert svc._normalize_status("passed") == "passed"


def test_normalize_status_aliases(svc):
    assert svc._normalize_status("responded") == "replied"
    assert svc._normalize_status("interested") == "replied"
    assert svc._normalize_status("scheduled") == "meeting"
    assert svc._normalize_status("rejected") == "passed"
    assert svc._normalize_status("declined") == "passed"
    assert svc._normalize_status("nda_signed") == "cda_signed"


def test_normalize_status_unknown_falls_back_to_replied(svc):
    assert svc._normalize_status("totally_made_up") == "replied"


def test_normalize_status_none_or_empty(svc):
    assert svc._normalize_status(None) == "replied"
    assert svc._normalize_status("") == "replied"


def test_normalize_status_case_insensitive(svc):
    assert svc._normalize_status("REPLIED") == "replied"
    assert svc._normalize_status("Passed") == "passed"


# ── _normalize_purpose ──────────────────────────────────────


def test_normalize_purpose_canonical(svc):
    assert svc._normalize_purpose("cold_outreach") == "cold_outreach"
    assert svc._normalize_purpose("cda_followup") == "cda_followup"
    assert svc._normalize_purpose("meeting_request") == "meeting_request"


def test_normalize_purpose_unknown_falls_back(svc):
    assert svc._normalize_purpose("random_thing") == "follow_up"


def test_normalize_purpose_none(svc):
    assert svc._normalize_purpose(None) == "follow_up"


# ── _compose_notes ──────────────────────────────────────────


def test_compose_notes_full(svc):
    notes = svc._compose_notes(
        prefix="Manual note:",
        summary="They liked the deck.",
        next_action="Send CDA template by Friday",
        key_dates=["2026-05-10"],
    )
    assert "Manual note:" in notes
    assert "Summary: They liked the deck." in notes
    assert "Next: Send CDA template by Friday" in notes
    assert "Dates: 2026-05-10" in notes
    # Joined with " | "
    assert " | " in notes


def test_compose_notes_minimal(svc):
    notes = svc._compose_notes(prefix=None, summary="", next_action="", key_dates=[])
    assert notes == ""


def test_compose_notes_skips_empty_dates(svc):
    notes = svc._compose_notes(
        prefix=None, summary="ok", next_action="", key_dates=[None, "", "2026-05-10"]
    )
    assert "2026-05-10" in notes
    assert "None" not in notes


# ── _format_confirmation ────────────────────────────────────


def test_format_confirmation_minimal(svc):
    md = svc._format_confirmation(
        event_id=42,
        company="Eli Lilly",
        contact=None,
        status="replied",
        purpose="follow_up",
        subject=None,
        summary="",
        next_action="",
        key_dates=[],
        llm_used_hint=False,
    )
    assert "#42" in md
    assert "Eli Lilly" in md
    assert "replied" in md
    assert "/outreach" in md
    # No 'used hint' note when not used
    assert "to_company_hint" not in md


def test_format_confirmation_full(svc):
    md = svc._format_confirmation(
        event_id=99,
        company="Pfizer",
        contact="Dr. Sarah Chen, Head of Oncology BD",
        status="meeting",
        purpose="meeting_request",
        subject="Re: PEG-001 follow-up",
        summary="They want a 30-min call next Tuesday to discuss Phase 2 data.",
        next_action="Send Phase 2 ORR + safety summary, propose 3 time slots",
        key_dates=["2026-05-12"],
        llm_used_hint=True,
    )
    assert "Sarah Chen" in md
    assert "meeting" in md
    assert "PEG-001 follow-up" in md
    assert "Phase 2" in md
    assert "Send Phase 2" in md
    assert "2026-05-12" in md
    assert "to_company_hint" in md  # hint usage noted


# ── _build_suggested_commands ───────────────────────────────


@pytest.mark.parametrize(
    "status",
    ["replied", "passed", "dead", "definitive_signed"],
)
def test_chip_neutral_status_only_view_thread(svc, status):
    chips = svc._build_suggested_commands(company="Pfizer", status=status)
    assert len(chips) == 1
    assert chips[0]["slug"] == "outreach-list"
    assert chips[0]["command"].startswith("/outreach")


def test_chip_cda_signed_offers_dd(svc):
    chips = svc._build_suggested_commands(company="Pfizer", status="cda_signed")
    assert len(chips) == 2
    slugs = [c["slug"] for c in chips]
    assert "dd-checklist" in slugs
    dd = next(c for c in chips if c["slug"] == "dd-checklist")
    assert 'company="Pfizer"' in dd["command"]


def test_chip_ts_signed_offers_license(svc):
    chips = svc._build_suggested_commands(company="Pfizer", status="ts_signed")
    assert len(chips) == 2
    license_chip = next(c for c in chips if c["slug"] == "legal-review")
    assert "contract_type=license" in license_chip["command"]
    assert 'counterparty="Pfizer"' in license_chip["command"]


def test_chip_meeting_offers_dd_prep(svc):
    chips = svc._build_suggested_commands(company="Pfizer", status="meeting")
    assert len(chips) == 2
    dd = next(c for c in chips if c["slug"] == "dd-checklist")
    assert 'company="Pfizer"' in dd["command"]


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert schema["required"] == ["reply_text"]
    assert "reply_text" in schema["properties"]
    assert "to_company_hint" in schema["properties"]
    assert "perspective" in schema["properties"]
    assert schema["properties"]["perspective"]["enum"] == ["buyer", "seller"]
