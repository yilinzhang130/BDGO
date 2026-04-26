"""Conference calendar reader — sources the same YAML the conference-ingest
MCP server reads, so /timing has access to actual 2025/2026 conference dates
+ abstract_release dates rather than only hardcoded annual averages.

Why read the YAML directly:
  The conference-ingest MCP server is a stdio LLM tool — not a long-running
  HTTP service BDGO can call. The data it serves comes from a plain YAML
  file. Reading the YAML in-process avoids forking an MCP subprocess per
  /timing call and avoids a hard dependency on the MCP runtime being
  installed alongside BDGO.

Production safety:
  Production VMs often don't have ~/.openclaw/skills/ checked out. The
  reader returns [] if the file is missing — callers (timing_advisor)
  fall back to their hardcoded annual-recurring event list.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _coerce_date(v: Any) -> datetime.date | None:
    """YAML loader can give us either date objects or YYYY-MM-DD strings."""
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        try:
            return datetime.date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def _status_label(
    days_to_meeting: int | None,
    days_to_abstract_release: int | None,
) -> str:
    """BD-relevant timing status. Mirrors the conference-ingest MCP's
    upcoming() classifier so users see consistent labels whether they
    invoke /timing or call the MCP tool directly."""
    if days_to_meeting is None or days_to_abstract_release is None:
        return "unknown dates"
    if days_to_meeting < 0:
        return "past"
    if days_to_abstract_release < 0 < days_to_meeting:
        return f"abstracts public ({-days_to_abstract_release}d ago)"
    if days_to_abstract_release == 0:
        return "abstracts releasing today"
    if days_to_abstract_release < 0:
        return "past"
    return f"abstracts in {days_to_abstract_release}d, meeting in {days_to_meeting}d"


def load_calendar(
    path: Path,
    today: datetime.date | None = None,
    look_ahead_days: int = 365,
    look_back_days: int = 30,
) -> list[dict]:
    """Read the conference calendar YAML and return BD-enriched conference dicts.

    Args:
        path: Path to conferences_calendar.yml. Missing or unreadable -> [].
        today: Anchor date for window filtering. Defaults to today.
        look_ahead_days: Include conferences with date_start within this
            window forward.
        look_back_days: Include very-recent conferences (whose abstracts
            are still being discussed in BD outreach) within this window
            backward. Default 30d preserves recent ASCO/ESMO context.

    Returns:
        Sorted list (earliest meeting first) of conference dicts. Each
        carries derived fields ``days_to_meeting`` and
        ``days_to_abstract_release`` (negative = past) plus a human
        ``status_label`` for BD timing context. Source field is set to
        "calendar" so callers can distinguish from annual-fallback rows.
    """
    if not path.exists():
        logger.info("Conference calendar not found at %s — falling back to annual events", path)
        return []

    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed; conference calendar disabled")
        return []

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to parse conference calendar at %s", path)
        return []

    if not isinstance(raw, dict):
        return []
    conferences_raw = raw.get("conferences") or []
    if not isinstance(conferences_raw, list):
        return []

    today = today or datetime.date.today()
    cutoff_forward = today + datetime.timedelta(days=look_ahead_days)
    cutoff_backward = today - datetime.timedelta(days=look_back_days)

    out: list[dict] = []
    for c in conferences_raw:
        if not isinstance(c, dict):
            continue
        date_start = _coerce_date(c.get("date_start"))
        if date_start is None:
            continue
        if date_start > cutoff_forward or date_start < cutoff_backward:
            continue

        date_end = _coerce_date(c.get("date_end"))
        abstract_release = _coerce_date(c.get("abstract_release"))

        days_to_meeting = (date_start - today).days
        days_to_abstract_release = (abstract_release - today).days if abstract_release else None

        out.append(
            {
                "id": c.get("id") or "",
                "name": c.get("name") or "",
                "ta": c.get("ta") or "",
                "bd_priority": c.get("bd_priority") or "",
                "date_start": date_start.isoformat(),
                "date_end": date_end.isoformat() if date_end else "",
                "abstract_release": abstract_release.isoformat() if abstract_release else "",
                "location": c.get("location") or "",
                "data_source": c.get("data_source") or "",
                "yaofangmofang_eta": c.get("yaofangmofang_eta") or "",
                "notes": c.get("notes") or "",
                "days_to_meeting": days_to_meeting,
                "days_to_abstract_release": days_to_abstract_release,
                "status_label": _status_label(days_to_meeting, days_to_abstract_release),
                "source": "calendar",
            }
        )

    out.sort(key=lambda x: x["date_start"])
    return out
