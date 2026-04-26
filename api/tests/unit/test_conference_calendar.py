"""Tests for services.external.conference_calendar.load_calendar."""

from __future__ import annotations

import datetime

from services.external.conference_calendar import _status_label, load_calendar

# ── _status_label ──────────────────────────────────────────


def test_status_label_abstracts_in_future():
    assert _status_label(60, 30) == "abstracts in 30d, meeting in 60d"


def test_status_label_abstracts_today():
    assert _status_label(30, 0) == "abstracts releasing today"


def test_status_label_abstracts_public_meeting_pending():
    assert _status_label(30, -7) == "abstracts public (7d ago)"


def test_status_label_meeting_past():
    assert _status_label(-5, -10) == "past"


def test_status_label_unknown():
    assert _status_label(None, None) == "unknown dates"


# ── load_calendar — file handling ──────────────────────────


def test_load_calendar_missing_file_returns_empty(tmp_path):
    result = load_calendar(tmp_path / "does_not_exist.yml")
    assert result == []


def test_load_calendar_invalid_yaml_returns_empty(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text(": : not: valid: yaml: at all", encoding="utf-8")
    result = load_calendar(bad)
    # Either parsed to an unexpected shape (-> []) or raised internally and
    # caught (-> []); either way we expect a stable empty list.
    assert result == []


def test_load_calendar_root_not_dict(tmp_path):
    p = tmp_path / "list_root.yml"
    p.write_text("- not_a_dict\n", encoding="utf-8")
    assert load_calendar(p) == []


def test_load_calendar_no_conferences_key(tmp_path):
    p = tmp_path / "no_key.yml"
    p.write_text("other_key: 1\n", encoding="utf-8")
    assert load_calendar(p) == []


# ── load_calendar — happy path ─────────────────────────────


def _calendar_yaml(*entries: str) -> str:
    body = "\n".join(entries)
    return f"conferences:\n{body}\n"


def test_load_calendar_basic_entry(tmp_path):
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml(
            "  - id: ASCO-2026\n"
            "    name: ASCO Annual Meeting 2026\n"
            "    ta: oncology\n"
            "    bd_priority: P0\n"
            "    date_start: 2026-05-29\n"
            "    date_end: 2026-06-02\n"
            "    abstract_release: 2026-05-21\n"
            "    location: Chicago, IL\n"
        ),
        encoding="utf-8",
    )
    today = datetime.date(2026, 4, 1)
    result = load_calendar(p, today=today, look_ahead_days=180)
    assert len(result) == 1
    row = result[0]
    assert row["id"] == "ASCO-2026"
    assert row["date_start"] == "2026-05-29"
    assert row["abstract_release"] == "2026-05-21"
    assert row["days_to_meeting"] == (datetime.date(2026, 5, 29) - today).days
    assert row["days_to_abstract_release"] == (datetime.date(2026, 5, 21) - today).days
    assert row["source"] == "calendar"
    assert "abstracts in" in row["status_label"]


def test_load_calendar_filters_far_future(tmp_path):
    """date_start beyond look_ahead_days is excluded."""
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml(
            "  - id: ASCO-2027\n"
            "    name: ASCO 2027\n"
            "    date_start: 2027-06-01\n"
            "    abstract_release: 2027-05-22\n"
        ),
        encoding="utf-8",
    )
    today = datetime.date(2026, 4, 1)
    # Look ahead only 90d → 2027 conference excluded
    assert load_calendar(p, today=today, look_ahead_days=90) == []


def test_load_calendar_keeps_recent_past(tmp_path):
    """look_back_days default = 30 keeps just-finished conferences in the
    output so BD outreach can reference recent abstracts."""
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml(
            "  - id: AACR-2026\n"
            "    name: AACR 2026\n"
            "    date_start: 2026-04-25\n"
            "    abstract_release: 2026-03-25\n"
        ),
        encoding="utf-8",
    )
    today = datetime.date(2026, 5, 5)  # 10 days after AACR ended
    result = load_calendar(p, today=today, look_ahead_days=180)
    assert len(result) == 1
    assert result[0]["id"] == "AACR-2026"
    assert result[0]["days_to_meeting"] == -10
    assert "past" in result[0]["status_label"]


def test_load_calendar_drops_too_old(tmp_path):
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml(
            "  - id: ASH-2024\n"
            "    name: ASH 2024\n"
            "    date_start: 2024-12-08\n"
            "    abstract_release: 2024-11-05\n"
        ),
        encoding="utf-8",
    )
    today = datetime.date(2026, 4, 1)  # >1 year past
    assert load_calendar(p, today=today) == []


def test_load_calendar_handles_missing_optional_fields(tmp_path):
    """abstract_release / date_end / location can be absent without crashing."""
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml(
            "  - id: BIO-Europe-Spring-2026\n"
            "    name: BIO-Europe Spring 2026\n"
            "    date_start: 2026-04-15\n"
        ),
        encoding="utf-8",
    )
    today = datetime.date(2026, 4, 1)
    result = load_calendar(p, today=today, look_ahead_days=30)
    assert len(result) == 1
    row = result[0]
    assert row["abstract_release"] == ""
    assert row["days_to_abstract_release"] is None
    assert row["status_label"] == "unknown dates"


def test_load_calendar_skips_entries_without_date_start(tmp_path):
    """Calendar entries missing date_start (typo / TBD) are silently dropped."""
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml("  - id: TBD-CONFERENCE\n    name: TBD\n    bd_priority: P1\n"),
        encoding="utf-8",
    )
    assert load_calendar(p, today=datetime.date(2026, 4, 1)) == []


def test_load_calendar_sorts_by_date_start(tmp_path):
    p = tmp_path / "cal.yml"
    p.write_text(
        _calendar_yaml(
            "  - id: ASH-2026\n"
            "    name: ASH 2026\n"
            "    date_start: 2026-12-05\n"
            "    abstract_release: 2026-11-05\n"
            "  - id: ASCO-2026\n"
            "    name: ASCO 2026\n"
            "    date_start: 2026-05-29\n"
            "    abstract_release: 2026-05-21\n"
        ),
        encoding="utf-8",
    )
    result = load_calendar(p, today=datetime.date(2026, 4, 1), look_ahead_days=400)
    assert [r["id"] for r in result] == ["ASCO-2026", "ASH-2026"]
