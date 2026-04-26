"""
Unit tests for MeetingBriefService input validation + chip logic.

LLM call (run()) is integration territory — these tests cover:
  - Service registration in REPORT_SERVICES
  - Input model validation (defaults, invalid values)
  - Chip routing per meeting purpose
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.meeting_brief import (
    _PURPOSE_LABEL,
    MeetingBriefInput,
    MeetingBriefService,
)


def test_service_registered():
    assert "meeting-brief" in REPORT_SERVICES
    svc = REPORT_SERVICES["meeting-brief"]
    assert isinstance(svc, MeetingBriefService)
    assert svc.slug == "meeting-brief"
    assert svc.output_formats == ["md"]
    assert svc.mode == "async"
    assert svc.chat_tool_name == "generate_meeting_brief"


def test_all_purposes_have_label():
    purposes = [
        "intro_pitch",
        "cda_negotiation",
        "data_room_review",
        "term_sheet",
        "partnership",
        "follow_up",
    ]
    for p in purposes:
        assert p in _PURPOSE_LABEL, f"Missing label for purpose: {p}"


def test_input_minimal_defaults():
    inp = MeetingBriefInput(counterparty="AstraZeneca")
    assert inp.counterparty == "AstraZeneca"
    assert inp.meeting_purpose == "intro_pitch"
    assert inp.our_perspective == "seller"
    assert inp.include_web_search is True
    assert inp.meeting_date is None
    assert inp.asset_context is None


def test_input_full():
    inp = MeetingBriefInput(
        counterparty="Pfizer BD",
        meeting_purpose="term_sheet",
        our_perspective="seller",
        asset_context="KRAS G12D inhibitor Phase 2 NSCLC",
        meeting_date="2026-05-01",
        attendees_our_side="CEO + Head of BD",
        attendees_their_side="VP External Innovation",
        extra_context="They asked about milestone schedule last time",
        include_web_search=False,
    )
    assert inp.counterparty == "Pfizer BD"
    assert inp.meeting_purpose == "term_sheet"
    assert inp.include_web_search is False


def test_input_empty_counterparty_raises():
    with pytest.raises(ValueError, match="counterparty"):
        MeetingBriefInput(counterparty="   ")


def test_input_invalid_purpose_raises():
    with pytest.raises(Exception):
        MeetingBriefInput(counterparty="Novartis", meeting_purpose="random_purpose")


class TestChipRouting:
    """Chip logic without LLM — verifies _build_chips() returns correct slugs."""

    def setup_method(self):
        self.svc = MeetingBriefService()

    def _chips(self, **kwargs) -> list[dict]:
        inp = MeetingBriefInput(counterparty="Eli Lilly", **kwargs)
        return self.svc._build_chips(inp)

    def test_intro_pitch_chips(self):
        chips = self._chips(meeting_purpose="intro_pitch")
        slugs = [c["slug"] for c in chips]
        assert "outreach-log" in slugs
        assert "outreach-email" in slugs

    def test_data_room_chips(self):
        chips = self._chips(meeting_purpose="data_room_review")
        slugs = [c["slug"] for c in chips]
        assert "outreach-log" in slugs
        assert "dd-checklist" in slugs

    def test_term_sheet_chips(self):
        chips = self._chips(meeting_purpose="term_sheet", asset_context="KRAS G12D")
        slugs = [c["slug"] for c in chips]
        assert "outreach-log" in slugs
        assert "draft-ts" in slugs
        # draft-ts command should contain the asset name
        ts_chip = next(c for c in chips if c["slug"] == "draft-ts")
        assert "KRAS G12D" in ts_chip["command"]

    def test_follow_up_chips(self):
        chips = self._chips(meeting_purpose="follow_up")
        slugs = [c["slug"] for c in chips]
        assert "outreach-log" in slugs
        # follow_up only has the log chip
        assert len(chips) == 1

    def test_log_chip_contains_counterparty(self):
        chips = self._chips(meeting_purpose="cda_negotiation")
        log_chip = next(c for c in chips if c["slug"] == "outreach-log")
        assert "Eli Lilly" in log_chip["command"]
        assert "meeting" in log_chip["command"]


def test_schema_required_fields():
    schema = MeetingBriefService().chat_tool_input_schema
    assert schema["required"] == ["counterparty"]


def test_schema_meeting_purpose_enum():
    schema = MeetingBriefService().chat_tool_input_schema
    purpose_enum = schema["properties"]["meeting_purpose"]["enum"]
    assert "intro_pitch" in purpose_enum
    assert "term_sheet" in purpose_enum
    assert len(purpose_enum) == 6
