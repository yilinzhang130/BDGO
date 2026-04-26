from pathlib import Path

from services.document.asset_extract import (
    _ASSET_FIELDS,
    _EXTENDED_FIELDS,
    _parse_json_loosely,
    build_intake_seed,
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
        "modality": "单克隆抗体",
    }
    cmd = build_teaser_command(asset)
    assert cmd is not None
    assert cmd.startswith("/teaser")
    assert 'company_name="Foo Bio"' in cmd
    assert 'asset_name="ABC-1234"' in cmd
    assert 'phase="Phase 2"' in cmd
    assert 'moa="Anti-PD-1"' in cmd
    assert 'modality="单克隆抗体"' in cmd


def test_build_teaser_command_modality_omitted_when_empty():
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "ABC-1234",
        "indication": "NSCLC",
        "target": "PD-1",
        "phase": "Phase 2",
        "modality": "",
    }
    cmd = build_teaser_command(asset)
    assert cmd is not None
    assert "modality" not in cmd


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
        return (
            '{"company_name": "Acme Bio", "asset_name": "ABC-9", "indication": "NSCLC", '
            '"target": "PD-1", "phase": "Phase 2", "moa": "mAb", '
            '"modality": "单克隆抗体", "ip_timeline": "化合物专利2034年到期", '
            '"funding": "Series B $80M 2024", "team": "CEO: John Smith"}'
        )

    result = extract_asset_metadata(f, fake_llm)
    assert result["company_name"] == "Acme Bio"
    assert result["asset_name"] == "ABC-9"
    assert result["phase"] == "Phase 2"
    # S1-03: new fields
    assert result["modality"] == "单克隆抗体"
    assert result["ip_timeline"] == "化合物专利2034年到期"
    assert result["funding"] == "Series B $80M 2024"
    assert result["team"] == "CEO: John Smith"


def test_extract_metadata_ten_fields_returned(tmp_path: Path, monkeypatch):
    """Result always has all 10 keys, empty string when not found."""
    f = tmp_path / "bp.pdf"
    f.write_bytes(b"")
    monkeypatch.setattr("services.document.asset_extract._extract_text", lambda _: "x" * 1000)

    # LLM returns only core 6 fields
    def fake_llm(**_):
        return '{"company_name": "Foo", "asset_name": "F-1", "indication": "CRC", "target": "RAS", "phase": "Phase 1", "moa": ""}'

    result = extract_asset_metadata(f, fake_llm)
    assert set(result.keys()) == set(_ASSET_FIELDS)
    # Extended fields default to empty string
    for field in _EXTENDED_FIELDS:
        assert result[field] == ""


def test_asset_fields_count():
    """Sanity: always 10 fields total."""
    assert len(_ASSET_FIELDS) == 10


# ── build_intake_seed ───────────────────────────────────────


def test_build_intake_seed_full_asset():
    asset = {
        "company_name": "Peg-Bio",
        "asset_name": "PEG-001",
        "target": "KRAS G12C",
        "indication": "NSCLC",
        "phase": "Phase 2",
        "moa": "covalent inhibitor",
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    # Must mention company + asset
    assert "Peg-Bio" in seed
    assert "PEG-001" in seed
    # Must include the available context fields
    assert "KRAS G12C" in seed
    assert "NSCLC" in seed
    assert "Phase 2" in seed
    # Must trigger should_plan: contains "评估" keyword or > 150 chars
    assert "评估" in seed or len(seed) > 150
    # Must mention key intake steps so planner LLM picks the right tools
    assert "靶点" in seed
    assert "BD intake" in seed or "intake" in seed.lower()


def test_build_intake_seed_minimal_asset():
    """Only company + asset_name → still produces a valid seed."""
    asset = {"company_name": "Foo Bio", "asset_name": "FOO-1"}
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "Foo Bio" in seed
    assert "FOO-1" in seed
    # No fields → no parenthesized field block
    assert "（" not in seed and "(" not in seed.split("FOO-1")[1].split("启动")[0]


def test_build_intake_seed_missing_company_returns_none():
    asset = {"asset_name": "X-1", "target": "EGFR"}
    assert build_intake_seed(asset) is None


def test_build_intake_seed_missing_asset_returns_none():
    asset = {"company_name": "Foo", "target": "EGFR"}
    assert build_intake_seed(asset) is None


def test_build_intake_seed_partial_fields_included():
    """When only some optional fields present, only those appear."""
    asset = {
        "company_name": "Bar Inc",
        "asset_name": "BAR-9",
        "indication": "DLBCL",
        # no target, no phase, no moa
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "DLBCL" in seed
    assert "靶点" not in seed.split("启动")[0]  # no 靶点 X in the parenthesized prefix


# ── S1-03: new extended fields in intake seed ───────────────


def test_build_intake_seed_includes_modality():
    asset = {
        "company_name": "Peg-Bio",
        "asset_name": "PEG-001",
        "modality": "ADC",
        "target": "KRAS G12D",
        "indication": "NSCLC",
        "phase": "Phase 2",
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "ADC" in seed
    # modality should appear in parenthesized field block before 启动
    prefix = seed.split("启动")[0]
    assert "ADC" in prefix


def test_build_intake_seed_includes_funding():
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "FOO-2",
        "funding": "Series B $80M 2024",
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "Series B" in seed or "80M" in seed or "融资" in seed


def test_build_intake_seed_includes_team():
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "FOO-2",
        "team": "CEO: John Smith; CMO: Dr. Jane Lee",
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "John Smith" in seed or "核心团队" in seed


def test_build_intake_seed_includes_ip_timeline():
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "FOO-2",
        "ip_timeline": "化合物专利2034年到期",
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "2034" in seed or "IP" in seed


def test_build_intake_seed_empty_extended_fields_no_extra_text():
    """When extended fields are all empty, seed doesn't contain placeholder text."""
    asset = {
        "company_name": "Foo Bio",
        "asset_name": "FOO-2",
        "modality": "",
        "funding": "",
        "team": "",
        "ip_timeline": "",
    }
    seed = build_intake_seed(asset)
    assert seed is not None
    assert "融资背景" not in seed
    assert "核心团队" not in seed
    assert "IP 情况" not in seed
