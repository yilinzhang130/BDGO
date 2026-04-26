"""Tests for BatchOutreachService (S2-09)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from services.reports.batch_outreach import (
    _MAX_COMPANIES,
    BatchOutreachInput,
    BatchOutreachService,
)

# ─────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────


def test_service_registered():
    from services import REPORT_SERVICES

    assert "batch-outreach" in REPORT_SERVICES


def test_chat_tool_name():
    svc = BatchOutreachService()
    assert svc.chat_tool_name == "batch_outreach_email"


def test_slug():
    assert BatchOutreachService.slug == "batch-outreach"


def test_output_formats():
    svc = BatchOutreachService()
    assert "md" in svc.output_formats
    assert "docx" not in svc.output_formats


# ─────────────────────────────────────────────────────────────
# Input validation
# ─────────────────────────────────────────────────────────────


def test_input_valid_minimal():
    inp = BatchOutreachInput(companies=["AstraZeneca"])
    assert inp.companies == ["AstraZeneca"]
    assert inp.purpose == "cold_outreach"
    assert inp.from_perspective == "seller"


def test_input_valid_full():
    inp = BatchOutreachInput(
        companies=["Pfizer", "Novartis"],
        purpose="meeting_request",
        from_perspective="buyer",
        asset_context="Anti-PD1 mAb Phase 2",
        from_company="Acme Bio",
        from_name="Jane Lee",
        from_role="VP BD",
        tone="warm",
        language="zh",
        extra_context="Met at ASCO 2026",
    )
    assert len(inp.companies) == 2
    assert inp.purpose == "meeting_request"
    assert inp.tone == "warm"


def test_empty_companies_raises():
    with pytest.raises(ValidationError):
        BatchOutreachInput(companies=[])


def test_whitespace_only_companies_raises():
    with pytest.raises(ValidationError):
        BatchOutreachInput(companies=["   ", "  "])


def test_too_many_companies_raises():
    with pytest.raises(ValidationError):
        BatchOutreachInput(companies=[f"Company{i}" for i in range(_MAX_COMPANIES + 1)])


def test_exactly_max_companies_ok():
    inp = BatchOutreachInput(companies=[f"Company{i}" for i in range(_MAX_COMPANIES)])
    assert len(inp.companies) == _MAX_COMPANIES


def test_invalid_purpose_raises():
    with pytest.raises(ValidationError):
        BatchOutreachInput(companies=["Pfizer"], purpose="term_sheet_send")  # not in batch enum


def test_whitespace_stripped_from_companies():
    inp = BatchOutreachInput(companies=["  Pfizer  ", "  Novartis  "])
    assert inp.companies == ["Pfizer", "Novartis"]


# ─────────────────────────────────────────────────────────────
# Section parsing
# ─────────────────────────────────────────────────────────────


def test_parse_sections_with_delimiters():
    svc = BatchOutreachService()
    raw = (
        "===EMAIL:Pfizer===\nSubject: KRAS data\n\nBody for Pfizer.\n\nBest,\nJane\n"
        "===EMAIL:Novartis===\nSubject: KRAS data\n\nBody for Novartis.\n\nBest,\nJane\n"
    )
    sections = svc._parse_sections(raw, ["Pfizer", "Novartis"])
    assert "Pfizer" in sections
    assert "Novartis" in sections
    assert "Pfizer" in sections["Pfizer"] or "Subject" in sections["Pfizer"]


def test_parse_sections_fallback_no_delimiters():
    svc = BatchOutreachService()
    raw = "Subject: KRAS data\n\nSome email body here.\n\nBest, Jane"
    sections = svc._parse_sections(raw, ["AstraZeneca"])
    assert "AstraZeneca" in sections
    assert len(sections["AstraZeneca"]) > 10


def test_parse_sections_missing_company_filled():
    svc = BatchOutreachService()
    raw = "===EMAIL:Pfizer===\nSubject: Hi\n\nBody.\n\nBest,\nJane\n"
    sections = svc._parse_sections(raw, ["Pfizer", "Novartis"])
    # Novartis wasn't in output — should still have a key
    assert "Novartis" in sections


# ─────────────────────────────────────────────────────────────
# Subject extraction
# ─────────────────────────────────────────────────────────────


def test_extract_subject_found():
    svc = BatchOutreachService()
    body = "Subject: KRAS G12D Phase 2 data\n\nDear John,"
    assert svc._extract_subject(body) == "KRAS G12D Phase 2 data"


def test_extract_subject_case_insensitive():
    svc = BatchOutreachService()
    body = "SUBJECT: Test line\n\nBody"
    assert svc._extract_subject(body) == "Test line"


def test_extract_subject_missing_returns_none():
    svc = BatchOutreachService()
    body = "No subject line here.\n\nBody text."
    assert svc._extract_subject(body) is None


# ─────────────────────────────────────────────────────────────
# Chips
# ─────────────────────────────────────────────────────────────


def test_chips_cold_outreach_includes_pipeline_and_meeting():
    svc = BatchOutreachService()
    inp = BatchOutreachInput(
        companies=["AstraZeneca"],
        purpose="cold_outreach",
        asset_context="KRAS G12D Phase 2",
    )
    chips = svc._build_chips(inp)
    slugs = [c["slug"] for c in chips]
    assert "outreach-list" in slugs
    assert "meeting-brief" in slugs


def test_chips_follow_up_no_meeting():
    svc = BatchOutreachService()
    inp = BatchOutreachInput(companies=["Pfizer"], purpose="follow_up")
    chips = svc._build_chips(inp)
    slugs = [c["slug"] for c in chips]
    assert "outreach-list" in slugs
    assert "meeting-brief" not in slugs


# ─────────────────────────────────────────────────────────────
# Planner prompt sync
# ─────────────────────────────────────────────────────────────


def test_batch_outreach_in_planner_prompt():
    from planner import PLANNER_SYSTEM_PROMPT

    svc = BatchOutreachService()
    assert svc.chat_tool_name in PLANNER_SYSTEM_PROMPT, (
        f"chat_tool_name '{svc.chat_tool_name}' not found in PLANNER_SYSTEM_PROMPT. "
        "Add it to the tool list in planner.py."
    )
