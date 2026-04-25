from pathlib import Path

from services.document.asset_extract import (
    _parse_json_loosely,
    build_teaser_command,
    extract_asset_metadata,
)


def test_parse_json_clean():
    assert _parse_json_loosely('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_parse_json_with_fence():
    raw = '```json\n{"company_name": "Foo", "asset_name": "ABC-1"}\n```'
    parsed = _parse_json_loosely(raw)
    assert parsed == {"company_name": "Foo", "asset_name": "ABC-1"}


def test_parse_json_with_prose():
    raw = 'Here is the answer:\n{"phase": "Phase 2"}\nThanks.'
    assert _parse_json_loosely(raw) == {"phase": "Phase 2"}


def test_parse_json_invalid_returns_none():
    assert _parse_json_loosely("not json at all") is None
    assert _parse_json_loosely("") is None


def test_build_teaser_command_full():
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "ABC-1234",
        "indication": "NSCLC",
        "target": "PD-1",
        "phase": "Phase 2",
        "moa": "Anti-PD-1",
    }
    cmd = build_teaser_command(asset)
    assert cmd is not None
    assert cmd.startswith("/teaser")
    assert 'company_name="Foo Bio"' in cmd
    assert 'asset_name="ABC-1234"' in cmd
    assert 'phase="Phase 2"' in cmd
    assert 'moa="Anti-PD-1"' in cmd


def test_build_teaser_command_too_few_fields():
    # Only 2 of 5 required fields → no suggestion
    asset = {"company_name": "Foo Bio", "asset_name": "ABC-1234"}
    assert build_teaser_command(asset) is None


def test_build_teaser_command_threshold():
    # Exactly 3 of 5 required → suggestion emitted
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "ABC-1234",
        "indication": "NSCLC",
        "target": "",
        "phase": "",
    }
    cmd = build_teaser_command(asset)
    assert cmd is not None
    assert "target" not in cmd
    assert 'company_name="Foo Bio"' in cmd


def test_extract_metadata_short_text(tmp_path: Path):
    # Empty file → text_too_short error
    f = tmp_path / "empty.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    result = extract_asset_metadata(f, lambda **_: "{}")
    assert "error" in result


def test_extract_metadata_llm_failure(tmp_path: Path, monkeypatch):
    # Stub text extraction to return long text; force LLM to fail
    f = tmp_path / "bp.docx"
    f.write_bytes(b"")

    def fake_text(_):
        return "x" * 1000

    monkeypatch.setattr("services.document.asset_extract._extract_text", fake_text)

    def boom(**_):
        raise RuntimeError("LLM down")

    result = extract_asset_metadata(f, boom)
    assert result == {"error": "llm_call_failed"}


def test_extract_metadata_happy_path(tmp_path: Path, monkeypatch):
    f = tmp_path / "bp.docx"
    f.write_bytes(b"")
    monkeypatch.setattr("services.document.asset_extract._extract_text", lambda _: "x" * 1000)

    def fake_llm(**_):
        return '{"company_name": "Acme Bio", "asset_name": "ABC-9", "indication": "NSCLC", "target": "PD-1", "phase": "Phase 2", "moa": "mAb"}'

    result = extract_asset_metadata(f, fake_llm)
    assert result["company_name"] == "Acme Bio"
    assert result["asset_name"] == "ABC-9"
    assert result["phase"] == "Phase 2"
