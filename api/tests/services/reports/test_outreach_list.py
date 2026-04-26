"""
Unit tests for OutreachListService.

DB read (`run()`) is integration territory. These tests cover:
  - Service registration
  - Input model defaults & validation
  - _format_pipeline_md output shape (empty + populated)
  - _format_thread_md output shape (empty + populated)
  - _thread_chips composition
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import datetime

import pytest
from services import REPORT_SERVICES
from services.reports.outreach_list import OutreachListInput, OutreachListService


@pytest.fixture
def svc() -> OutreachListService:
    return OutreachListService()


def test_service_registered():
    assert "outreach-list" in REPORT_SERVICES
    s = REPORT_SERVICES["outreach-list"]
    assert isinstance(s, OutreachListService)
    assert s.slug == "outreach-list"
    assert s.output_formats == ["md"]


def test_input_minimal_defaults():
    inp = OutreachListInput()
    assert inp.company is None
    assert inp.status is None
    assert inp.purpose is None
    assert inp.recent_days is None
    assert inp.limit == 50


def test_input_with_filters():
    inp = OutreachListInput(
        company="Pfizer",
        status="replied",
        purpose="cold_outreach",
        perspective="seller",
        recent_days=30,
        limit=100,
    )
    assert inp.company == "Pfizer"
    assert inp.recent_days == 30


def test_input_rejects_invalid_status():
    with pytest.raises(ValueError):
        OutreachListInput(status="ghosted")  # type: ignore[arg-type]


def test_input_rejects_invalid_recent_days():
    with pytest.raises(ValueError):
        OutreachListInput(recent_days=0)
    with pytest.raises(ValueError):
        OutreachListInput(recent_days=400)


# ── Pipeline view formatting ────────────────────────────────


def test_format_pipeline_empty_all_time(svc):
    inp = OutreachListInput()
    md = svc._format_pipeline_md([], inp)
    assert "Outreach Pipeline" in md
    assert "全部时间" in md or "还没有" in md
    assert "/log" in md  # Should hint at logging


def test_format_pipeline_empty_recent(svc):
    inp = OutreachListInput(recent_days=14)
    md = svc._format_pipeline_md([], inp)
    assert "14" in md


def test_format_pipeline_with_data(svc):
    rows = [
        {
            "to_company": "Pfizer",
            "status": "sent",
            "n": 2,
            "last_touched": datetime.datetime(2026, 4, 20, 14, 0),
        },
        {
            "to_company": "Pfizer",
            "status": "replied",
            "n": 1,
            "last_touched": datetime.datetime(2026, 4, 22, 10, 0),
        },
        {
            "to_company": "Eli Lilly",
            "status": "sent",
            "n": 1,
            "last_touched": datetime.datetime(2026, 4, 18, 9, 0),
        },
    ]
    md = svc._format_pipeline_md(rows, OutreachListInput())
    assert "Pfizer" in md
    assert "Eli Lilly" in md
    # Status counts should appear
    assert "sent=2" in md
    assert "replied=1" in md
    # Total events = 4
    assert "4" in md
    # Pfizer sorted before Eli Lilly (more recent last_touched)
    assert md.index("Pfizer") < md.index("Eli Lilly")


# ── Thread view formatting ──────────────────────────────────


def test_format_thread_empty(svc):
    inp = OutreachListInput(company="Pfizer")
    md = svc._format_thread_md([], inp)
    assert "Pfizer" in md
    assert "没有匹配" in md or "no matching" in md.lower()


def test_format_thread_with_events(svc):
    events = [
        {
            "id": 1,
            "to_company": "Pfizer",
            "to_contact": "Sarah Chen",
            "purpose": "cold_outreach",
            "channel": "email",
            "status": "sent",
            "asset_context": "PEG-001",
            "subject": "Initial intro re PEG-001",
            "notes": None,
            "created_at": datetime.datetime(2026, 4, 20, 14, 0),
        },
        {
            "id": 2,
            "to_company": "Pfizer",
            "to_contact": "Sarah Chen",
            "purpose": "follow_up",
            "channel": "email",
            "status": "replied",
            "asset_context": None,
            "subject": None,
            "notes": "Asked for Phase 1 readout.",
            "created_at": datetime.datetime(2026, 4, 22, 10, 0),
        },
    ]
    md = svc._format_thread_md(events, OutreachListInput(company="Pfizer"))
    assert "Pfizer" in md
    assert "Sarah Chen" in md
    assert "cold_outreach" in md
    assert "replied" in md
    assert "Asked for Phase 1 readout" in md


def test_format_thread_truncates_long_notes(svc):
    long_notes = "x" * 200
    events = [
        {
            "id": 1,
            "to_company": "Pfizer",
            "to_contact": None,
            "purpose": "follow_up",
            "channel": "email",
            "status": "sent",
            "asset_context": None,
            "subject": None,
            "notes": long_notes,
            "created_at": datetime.datetime(2026, 4, 20, 14, 0),
        }
    ]
    md = svc._format_thread_md(events, OutreachListInput(company="Pfizer"))
    # Long notes should be truncated with ellipsis
    assert "…" in md or "..." in md


# ── Thread chips ────────────────────────────────────────────


def test_thread_chips_offer_log_replies_and_meetings(svc):
    inp = OutreachListInput(company="Pfizer")
    chips = svc._thread_chips(inp)
    assert len(chips) == 2
    slugs = [c["slug"] for c in chips]
    assert all(s == "outreach-log" for s in slugs)
    cmds = [c["command"] for c in chips]
    assert any("status=replied" in c for c in cmds)
    assert any("status=meeting" in c for c in cmds)
    for c in cmds:
        assert 'to_company="Pfizer"' in c


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert schema["required"] == []
    assert schema["properties"]["limit"]["default"] == 50
    assert schema["properties"]["limit"]["maximum"] == 500
    assert "company" in schema["properties"]
    assert "status" in schema["properties"]
    assert "recent_days" in schema["properties"]


# ─────────────────────────────────────────────────────────────
# Structured meta — backing the chat-embedded mini-table (PR D)
# ─────────────────────────────────────────────────────────────


def test_pipeline_rows_for_meta_groups_per_company(svc):
    """Multiple status rows for the same company collapse into one
    company entry with status counts dict + summed total_events."""
    raw = [
        {
            "to_company": "Pfizer",
            "status": "sent",
            "n": 3,
            "last_touched": datetime.datetime(2026, 4, 20, 10, 0),
        },
        {
            "to_company": "Pfizer",
            "status": "replied",
            "n": 1,
            "last_touched": datetime.datetime(2026, 4, 22, 14, 0),
        },
        {
            "to_company": "Lilly",
            "status": "sent",
            "n": 2,
            "last_touched": datetime.datetime(2026, 4, 18, 9, 0),
        },
    ]
    rows = svc._pipeline_rows_for_meta(raw)
    assert len(rows) == 2
    pfizer = next(r for r in rows if r["company"] == "Pfizer")
    assert pfizer["statuses"] == {"sent": 3, "replied": 1}
    assert pfizer["total_events"] == 4
    # Pfizer's last_touched should be the later of the two timestamps
    assert pfizer["last_touched"] == "2026-04-22T14:00:00"


def test_pipeline_rows_for_meta_sorted_by_last_touched_desc(svc):
    """Most recently touched company appears first — matches the markdown
    pipeline view's sort order so users see the same ordering in either
    rendering."""
    raw = [
        {
            "to_company": "Old Co",
            "status": "sent",
            "n": 1,
            "last_touched": datetime.datetime(2026, 1, 1),
        },
        {
            "to_company": "Recent Co",
            "status": "sent",
            "n": 1,
            "last_touched": datetime.datetime(2026, 4, 25),
        },
    ]
    rows = svc._pipeline_rows_for_meta(raw)
    assert [r["company"] for r in rows] == ["Recent Co", "Old Co"]


def test_pipeline_rows_for_meta_empty(svc):
    assert svc._pipeline_rows_for_meta([]) == []


def test_pipeline_rows_for_meta_serializes_datetime(svc):
    """meta is JSON-encoded into the report_history table; datetimes
    must be stringified before they get there."""
    import json

    raw = [
        {
            "to_company": "X",
            "status": "sent",
            "n": 1,
            "last_touched": datetime.datetime(2026, 4, 26, 12, 30),
        }
    ]
    rows = svc._pipeline_rows_for_meta(raw)
    # Must round-trip through JSON cleanly
    payload = json.dumps(rows)
    assert "2026-04-26T12:30:00" in payload


def test_thread_events_for_meta_projects_safe_shape(svc):
    """Long notes are truncated; missing fields default to empty
    strings; datetime → ISO."""
    raw = [
        {
            "id": "evt-001",
            "created_at": datetime.datetime(2026, 4, 25, 10, 15),
            "status": "replied",
            "purpose": "cda_followup",
            "channel": "email",
            "to_contact": "Sarah Chen, Head of BD",
            "subject": "Re: PEG-001 partnership",
            "notes": "x" * 600,  # over the 400-char cap
            "asset_context": "PEG-001 (NSCLC)",
        },
        {
            # Missing optional fields
            "id": "evt-002",
            "created_at": None,
            "status": "sent",
            "purpose": "cold_outreach",
            "channel": "email",
        },
    ]
    out = svc._thread_events_for_meta(raw)
    assert len(out) == 2
    assert out[0]["event_id"] == "evt-001"
    assert out[0]["ts"] == "2026-04-25T10:15:00"
    assert len(out[0]["notes"]) == 400  # truncated
    # Missing fields default to "" not None (avoids JS undefined-handling pain)
    assert out[1]["ts"] == ""
    assert out[1]["to_contact"] == ""
    assert out[1]["asset_context"] == ""


def test_thread_events_for_meta_empty(svc):
    assert svc._thread_events_for_meta([]) == []
