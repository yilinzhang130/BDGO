"""
Unit tests for BDSynthesizeService.

DB read + file read + LLM call (`run()`) is integration territory. These
tests cover:
  - Service registration
  - Input model validation
  - _asset_label() composition
  - _format_sources_block() shape
  - _read_task_markdown() — tested via tmp_path with fake REPORTS_DIR
  - _build_suggested_commands() — buyer chip + timing chip wiring
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.bd_synthesize import (
    _MAX_TASK_IDS,
    _PER_SOURCE_CHARS,
    BDSynthesizeService,
    SynthesizeInput,
)


@pytest.fixture
def svc() -> BDSynthesizeService:
    return BDSynthesizeService()


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "bd-synthesize" in REPORT_SERVICES
    s = REPORT_SERVICES["bd-synthesize"]
    assert isinstance(s, BDSynthesizeService)
    assert s.slug == "bd-synthesize"
    assert "md" in s.output_formats and "docx" in s.output_formats


# ── Input model ─────────────────────────────────────────────


def test_input_minimal():
    inp = SynthesizeInput(task_ids=["a", "b"])
    assert len(inp.task_ids) == 2
    assert inp.asset_name is None
    assert inp.company is None


def test_input_full():
    inp = SynthesizeInput(
        task_ids=["a", "b", "c"],
        asset_name="PEG-001",
        company="Peg-Bio",
        focus="重点看 Top-3 买方排序",
    )
    assert inp.asset_name == "PEG-001"
    assert inp.focus == "重点看 Top-3 买方排序"


def test_input_rejects_too_few_task_ids():
    with pytest.raises(ValueError):
        SynthesizeInput(task_ids=["a"])


def test_input_rejects_zero_task_ids():
    with pytest.raises(ValueError):
        SynthesizeInput(task_ids=[])


def test_input_rejects_too_many_task_ids():
    with pytest.raises(ValueError):
        SynthesizeInput(task_ids=[f"id-{i}" for i in range(_MAX_TASK_IDS + 1)])


# ── Asset label ─────────────────────────────────────────────


def test_asset_label_full(svc):
    inp = SynthesizeInput(task_ids=["a", "b"], company="Peg-Bio", asset_name="PEG-001")
    assert svc._asset_label(inp) == "Peg-Bio / PEG-001"


def test_asset_label_only_asset(svc):
    inp = SynthesizeInput(task_ids=["a", "b"], asset_name="PEG-001")
    assert svc._asset_label(inp) == "PEG-001"


def test_asset_label_only_company(svc):
    inp = SynthesizeInput(task_ids=["a", "b"], company="Peg-Bio")
    assert svc._asset_label(inp) == "Peg-Bio"


def test_asset_label_neither(svc):
    inp = SynthesizeInput(task_ids=["a", "b"])
    label = svc._asset_label(inp)
    assert "unspecified" in label.lower()


# ── Sources block formatting ────────────────────────────────


def test_format_sources_block_single(svc):
    sources = [
        {
            "task_id": "abc123",
            "slug": "target-radar",
            "title": "PEG-001 — Target Radar",
            "markdown": "# Target analysis\n\nKRAS G12C is a key target...",
            "truncated": False,
            "meta": {},
        }
    ]
    block = svc._format_sources_block(sources)
    assert "[来源 1]" in block
    assert "target-radar" in block
    assert "abc123" in block
    assert "KRAS G12C" in block
    assert "已截断" not in block


def test_format_sources_block_multiple(svc):
    sources = [
        {
            "task_id": "t1",
            "slug": "target-radar",
            "title": "Target",
            "markdown": "# T\n",
            "truncated": False,
            "meta": {},
        },
        {
            "task_id": "t2",
            "slug": "deal-evaluator",
            "title": "Eval",
            "markdown": "# E\n",
            "truncated": False,
            "meta": {},
        },
    ]
    block = svc._format_sources_block(sources)
    assert "[来源 1]" in block
    assert "[来源 2]" in block
    # Sources separated by horizontal rule
    assert "---" in block


def test_format_sources_block_marks_truncated(svc):
    sources = [
        {
            "task_id": "t1",
            "slug": "target-radar",
            "title": "T",
            "markdown": "x",
            "truncated": True,
            "meta": {},
        }
    ]
    block = svc._format_sources_block(sources)
    assert "已截断" in block
    assert str(_PER_SOURCE_CHARS) in block


# ── _read_task_markdown ─────────────────────────────────────


def test_read_task_markdown_via_files_json(svc, tmp_path, monkeypatch):
    """Happy path: files_json points to a real .md file under REPORTS_DIR."""
    import json as _json

    from services.reports import bd_synthesize as mod

    # Redirect REPORTS_DIR to tmp_path for the test
    monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

    task_dir = tmp_path / "task-abc"
    task_dir.mkdir()
    md_file = task_dir / "report.md"
    md_file.write_text("# hello world\n\ncontent here.\n", encoding="utf-8")

    files_json = _json.dumps(
        [
            {"filename": "report.docx", "format": "docx"},
            {"filename": "report.md", "format": "md"},
        ]
    )
    text = svc._read_task_markdown("task-abc", files_json)
    assert "hello world" in text


def test_read_task_markdown_glob_fallback(svc, tmp_path, monkeypatch):
    """If files_json is missing/invalid, fall back to globbing the dir."""
    from services.reports import bd_synthesize as mod

    monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)

    task_dir = tmp_path / "task-xyz"
    task_dir.mkdir()
    (task_dir / "report.md").write_text("from glob", encoding="utf-8")

    text = svc._read_task_markdown("task-xyz", None)
    assert text == "from glob"


def test_read_task_markdown_nonexistent_returns_empty(svc, tmp_path, monkeypatch):
    from services.reports import bd_synthesize as mod

    monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path)
    # No directory created — should return ""
    assert svc._read_task_markdown("does-not-exist", None) == ""


# ── Suggested commands ──────────────────────────────────────


def test_suggested_commands_email_chip_always(svc):
    inp = SynthesizeInput(task_ids=["a", "b"])
    chips = svc._build_suggested_commands(inp, [])
    assert any(c["slug"] == "outreach-email" for c in chips)
    email = next(c for c in chips if c["slug"] == "outreach-email")
    assert email["command"].startswith("/email")
    # No company / asset → no timing chip
    assert not any(c["slug"] == "timing-advisor" for c in chips)


def test_suggested_commands_timing_chip_when_company_present(svc):
    inp = SynthesizeInput(task_ids=["a", "b"], company="Peg-Bio", asset_name="PEG-001")
    chips = svc._build_suggested_commands(inp, [])
    assert any(c["slug"] == "timing-advisor" for c in chips)
    timing = next(c for c in chips if c["slug"] == "timing-advisor")
    assert 'company_name="Peg-Bio"' in timing["command"]
    assert 'asset_name="PEG-001"' in timing["command"]
    assert "perspective=seller" in timing["command"]


def test_suggested_commands_email_chip_includes_asset_context(svc):
    inp = SynthesizeInput(task_ids=["a", "b"], asset_name="PEG-001")
    sources = [{"slug": "target-radar", "meta": {"indication": "NSCLC"}}]
    chips = svc._build_suggested_commands(inp, sources)
    email = next(c for c in chips if c["slug"] == "outreach-email")
    assert 'asset_context="PEG-001 — NSCLC"' in email["command"]


def test_suggested_commands_email_chip_uses_just_asset_when_no_indication(svc):
    inp = SynthesizeInput(task_ids=["a", "b"], asset_name="PEG-001")
    chips = svc._build_suggested_commands(inp, [])
    email = next(c for c in chips if c["slug"] == "outreach-email")
    assert 'asset_context="PEG-001"' in email["command"]


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert schema["required"] == ["task_ids"]
    assert schema["properties"]["task_ids"]["type"] == "array"
    assert schema["properties"]["task_ids"]["minItems"] == 2
    assert schema["properties"]["task_ids"]["maxItems"] == _MAX_TASK_IDS
    assert "asset_name" in schema["properties"]
    assert "company" in schema["properties"]
    assert "focus" in schema["properties"]
