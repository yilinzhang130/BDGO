"""
Smoke tests for ``services.quality.schema_validator``.

The validator is a port of the harness validator at
``~/.openclaw/workspace/harness_design/mnc/schema_validator.py``. These
tests guard the BDGO public surface (``validate_markdown`` /
``audit_to_dict``) and ensure it stays JSON-serialisable for
``meta_json`` storage.
"""

from __future__ import annotations

import json

import pytest
from services.quality import audit_to_dict, validate_markdown
from services.quality.schema_validator import (
    AuditResult,
    Finding,
    count_chars,
    load_md_text,
)


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        validate_markdown("# foo", mode="not_a_mode")


def test_validate_markdown_empty_returns_audit():
    """Empty input still returns an AuditResult — most checks will FAIL."""
    audit = validate_markdown("", mode="mnc")
    assert isinstance(audit, AuditResult)
    assert audit.n_fail > 0
    assert audit.stats["mode"] == "mnc"
    assert audit.stats["schema"] == "mnc_main.yaml"


def test_audit_to_dict_is_json_safe():
    """Output must round-trip through json.dumps for meta_json storage."""
    audit = validate_markdown("# Test\n\nshort body", mode="mnc")
    payload = audit_to_dict(audit)

    # Must serialise without falling over on sets, dataclasses, etc.
    serialised = json.dumps(payload, ensure_ascii=False, default=str)
    parsed = json.loads(serialised)
    assert "n_fail" in parsed
    assert "n_warn" in parsed
    assert "findings" in parsed
    assert isinstance(parsed["findings"], list)


def test_audit_to_dict_truncates_findings():
    audit = AuditResult()
    for i in range(150):
        audit.add("warn", "test", "x", f"finding {i}")
    payload = audit_to_dict(audit, max_findings=50)
    assert len(payload["findings"]) == 50
    assert payload["findings_truncated"] == 100


def test_load_md_text_parses_headings_and_tables():
    md = """
# Title

Some paragraph.

## Subheading

| col1 | col2 |
| --- | --- |
| a | b |
""".strip()
    blocks = load_md_text(md)
    kinds = [b.kind for b in blocks]
    assert kinds.count("heading") == 2
    assert kinds.count("paragraph") == 1
    assert kinds.count("table") == 1


def test_count_chars_strips_whitespace():
    assert count_chars("  a  b  ") == 2
    assert count_chars("中文 字符") == 4


def test_finding_evidence_truncated():
    f = Finding("warn", "cat", "sec", "msg", evidence="x" * 500)
    audit = AuditResult()
    audit.findings.append(f)
    # The dataclass itself doesn't truncate — only AuditResult.add does
    audit.add("warn", "cat", "sec", "msg", evidence="y" * 500)
    assert len(audit.findings[1].evidence) == 200


def test_commercial_biotech_schema_loads():
    """The second mode's schema file should also load without error."""
    audit = validate_markdown("# Test", mode="commercial_biotech")
    assert audit.stats["schema"] == "commercial_biotech_main.yaml"


# ─────────────────────────────────────────────────────────────
# Drift tests — keep _SCHEMA_BY_MODE in sync with schemas/ dir
# ─────────────────────────────────────────────────────────────


def test_every_yaml_in_schemas_dir_is_registered():
    """Orphan schema files are dead weight and signal forgotten plumbing.

    If you add a YAML to api/services/quality/schemas/ but forget to
    register it in _SCHEMA_BY_MODE, no service can validate against it
    and the file rots. This test catches that drift.
    """
    from services.quality.schema_validator import _SCHEMA_BY_MODE, _SCHEMAS_DIR

    on_disk = {p.name for p in _SCHEMAS_DIR.glob("*.yaml")}
    registered = set(_SCHEMA_BY_MODE.values())
    orphans = on_disk - registered
    assert not orphans, (
        f"Schema YAMLs exist on disk but are not in _SCHEMA_BY_MODE: "
        f"{sorted(orphans)}. Either register them or delete them."
    )


def test_every_registered_mode_has_a_yaml_file():
    """Inverse drift: a _SCHEMA_BY_MODE entry pointing to a missing
    file would raise FileNotFoundError at validate_markdown call time.
    Surface that at test time instead.
    """
    from services.quality.schema_validator import _SCHEMA_BY_MODE, _SCHEMAS_DIR

    missing = [
        f"{mode} → {fname}"
        for mode, fname in _SCHEMA_BY_MODE.items()
        if not (_SCHEMAS_DIR / fname).exists()
    ]
    assert not missing, (
        f"_SCHEMA_BY_MODE references YAML files that don't exist on disk: "
        f"{missing}. Either add the YAMLs or remove the modes."
    )
