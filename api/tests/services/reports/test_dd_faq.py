"""Tests for DDFaqService (S3-04)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from services.reports.dd_faq import (
    _MEETING_STAGES,
    _STAGE_LABEL,
    DDFaqInput,
    DDFaqService,
)

# ─────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────


def test_service_registered():
    from services import REPORT_SERVICES

    assert "dd-faq" in REPORT_SERVICES


def test_chat_tool_name():
    svc = DDFaqService()
    assert svc.chat_tool_name == "generate_dd_faq"


def test_slug():
    assert DDFaqService.slug == "dd-faq"


def test_output_formats():
    svc = DDFaqService()
    assert "md" in svc.output_formats
    assert "docx" not in svc.output_formats


# ─────────────────────────────────────────────────────────────
# Input validation
# ─────────────────────────────────────────────────────────────


def test_input_minimal():
    inp = DDFaqInput(asset_context="KRAS G12D inhibitor, NSCLC 2L, Phase 2")
    assert inp.meeting_stage == "data_room"
    assert inp.n_questions == 12
    assert inp.our_perspective == "seller"
    assert inp.include_web_search is True


def test_input_full():
    inp = DDFaqInput(
        asset_context="anti-PD1 mAb, NSCLC 1L, Phase 3, ORR 42%",
        meeting_stage="term_sheet",
        counterparty="Pfizer",
        our_perspective="seller",
        known_gaps="no OS data yet",
        n_questions=8,
        include_web_search=False,
        extra_context="Met at ASCO",
    )
    assert inp.meeting_stage == "term_sheet"
    assert inp.n_questions == 8
    assert inp.counterparty == "Pfizer"


def test_empty_asset_context_raises():
    with pytest.raises(ValidationError):
        DDFaqInput(asset_context="")


def test_whitespace_asset_context_raises():
    with pytest.raises(ValidationError):
        DDFaqInput(asset_context="   ")


def test_n_questions_too_low_raises():
    with pytest.raises(ValidationError):
        DDFaqInput(asset_context="test", n_questions=4)


def test_n_questions_too_high_raises():
    with pytest.raises(ValidationError):
        DDFaqInput(asset_context="test", n_questions=21)


def test_n_questions_boundary_values():
    DDFaqInput(asset_context="test", n_questions=5)
    DDFaqInput(asset_context="test", n_questions=20)


def test_invalid_meeting_stage_raises():
    with pytest.raises(ValidationError):
        DDFaqInput(asset_context="test", meeting_stage="unknown_stage")


def test_all_meeting_stages_valid():
    for stage in _MEETING_STAGES:
        inp = DDFaqInput(asset_context="test asset", meeting_stage=stage)
        assert inp.meeting_stage == stage


# ─────────────────────────────────────────────────────────────
# Stage labels
# ─────────────────────────────────────────────────────────────


def test_all_stages_have_labels():
    for stage in _MEETING_STAGES:
        assert stage in _STAGE_LABEL
        assert len(_STAGE_LABEL[stage]) > 5


# ─────────────────────────────────────────────────────────────
# Chip routing
# ─────────────────────────────────────────────────────────────


def test_chips_always_include_dd_checklist():
    svc = DDFaqService()
    for stage in _MEETING_STAGES:
        inp = DDFaqInput(asset_context="KRAS inhibitor", meeting_stage=stage)
        chips = svc._build_chips(inp)
        slugs = [c["slug"] for c in chips]
        assert "dd-checklist" in slugs


def test_chips_intro_pitch_includes_meeting_brief():
    svc = DDFaqService()
    inp = DDFaqInput(
        asset_context="KRAS inhibitor",
        meeting_stage="intro_pitch",
        counterparty="AstraZeneca",
    )
    chips = svc._build_chips(inp)
    slugs = [c["slug"] for c in chips]
    assert "meeting-brief" in slugs


def test_chips_term_sheet_includes_draft_ts():
    svc = DDFaqService()
    inp = DDFaqInput(asset_context="KRAS inhibitor", meeting_stage="term_sheet")
    chips = svc._build_chips(inp)
    slugs = [c["slug"] for c in chips]
    assert "draft-ts" in slugs


def test_chips_data_room_includes_dataroom():
    svc = DDFaqService()
    inp = DDFaqInput(asset_context="KRAS inhibitor", meeting_stage="data_room")
    chips = svc._build_chips(inp)
    slugs = [c["slug"] for c in chips]
    assert "data-room" in slugs


def test_chips_dd_checklist_includes_counterparty_in_command():
    svc = DDFaqService()
    inp = DDFaqInput(
        asset_context="KRAS inhibitor",
        meeting_stage="data_room",
        counterparty="Novartis",
    )
    chips = svc._build_chips(inp)
    dd_chip = next(c for c in chips if c["slug"] == "dd-checklist")
    assert "Novartis" in dd_chip["command"]


# ─────────────────────────────────────────────────────────────
# Schema fields
# ─────────────────────────────────────────────────────────────


def test_chat_tool_schema_required_fields():
    svc = DDFaqService()
    schema = svc.chat_tool_input_schema
    assert "asset_context" in schema["required"]


def test_chat_tool_schema_n_questions_bounds():
    svc = DDFaqService()
    schema = svc.chat_tool_input_schema
    n_q = schema["properties"]["n_questions"]
    assert n_q["minimum"] == 5
    assert n_q["maximum"] == 20


# ─────────────────────────────────────────────────────────────
# Planner prompt sync
# ─────────────────────────────────────────────────────────────


def test_dd_faq_in_planner_prompt():
    from planner import PLANNER_SYSTEM_PROMPT

    svc = DDFaqService()
    assert svc.chat_tool_name in PLANNER_SYSTEM_PROMPT, (
        f"chat_tool_name '{svc.chat_tool_name}' not found in PLANNER_SYSTEM_PROMPT. "
        "Add it to the tool list in planner.py."
    )
