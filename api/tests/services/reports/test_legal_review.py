"""
Unit tests for LegalReviewService input + helper logic.

These don't make LLM calls — that's integration territory. We exercise:
  - Input validation (text or filename required)
  - Per-type checklist coverage (all 6 types)
  - Title composition
  - Truncation
  - Service registration in REPORT_SERVICES
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.legal_review import (
    _CONTRACT_TYPE_NAMES,
    _MAX_CONTRACT_CHARS,
    _TYPE_CHECKLISTS,
    LegalReviewInput,
    LegalReviewService,
)


def test_service_registered():
    assert "legal-review" in REPORT_SERVICES
    svc = REPORT_SERVICES["legal-review"]
    assert isinstance(svc, LegalReviewService)
    assert svc.slug == "legal-review"
    assert "docx" in svc.output_formats and "md" in svc.output_formats


def test_input_requires_text_or_filename():
    with pytest.raises(ValueError, match="contract_text"):
        LegalReviewInput(contract_type="cda", party_position="甲方")


def test_input_accepts_text():
    inp = LegalReviewInput(
        contract_type="cda",
        party_position="甲方",
        contract_text="Confidential Information means...",
    )
    assert inp.contract_text.startswith("Confidential")


def test_input_accepts_filename():
    inp = LegalReviewInput(
        contract_type="mta",
        party_position="乙方",
        filename="emaygene_lilly_mta.pdf",
    )
    assert inp.filename == "emaygene_lilly_mta.pdf"


def test_all_contract_types_have_checklists():
    """Every value in the Literal must have a matching checklist + name."""
    expected = {"cda", "ts", "mta", "license", "co_dev", "spa"}
    assert set(_TYPE_CHECKLISTS.keys()) == expected
    assert set(_CONTRACT_TYPE_NAMES.keys()) == expected


def test_invalid_contract_type_rejected():
    with pytest.raises(ValueError):
        LegalReviewInput(
            contract_type="amendment",  # type: ignore[arg-type]
            party_position="甲方",
            contract_text="...",
        )


def test_invalid_party_position_rejected():
    with pytest.raises(ValueError):
        LegalReviewInput(
            contract_type="cda",
            party_position="第三方",  # type: ignore[arg-type]
            contract_text="...",
        )


def test_compose_title_with_full_context():
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="license",
        party_position="甲方",
        contract_text="x",
        counterparty="Eli Lilly",
        project_name="Project Aurora",
    )
    title = svc._compose_title(inp, _CONTRACT_TYPE_NAMES["license"])
    assert "Eli Lilly" in title
    assert "Project Aurora" in title
    assert "License Agreement" in title
    assert "审查意见" in title


def test_compose_title_minimal():
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="cda",
        party_position="乙方",
        contract_text="x",
    )
    title = svc._compose_title(inp, _CONTRACT_TYPE_NAMES["cda"])
    assert "审查意见" in title


def test_truncate_passthrough_under_limit():
    svc = LegalReviewService()
    text = "x" * 1000
    out, truncated = svc._truncate(text)
    assert out == text
    assert truncated is False


def test_truncate_caps_oversized_input():
    svc = LegalReviewService()
    text = "x" * (_MAX_CONTRACT_CHARS + 5000)
    out, truncated = svc._truncate(text)
    assert len(out) == _MAX_CONTRACT_CHARS
    assert truncated is True


def test_suggested_commands_cda_with_counterparty():
    """Stage 4 of BD lifecycle: CDA + known counterparty → offer /dd."""
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="cda",
        party_position="乙方",
        contract_text="x",
        counterparty="Eli Lilly",
    )
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 1
    assert sc[0]["slug"] == "dd-checklist"
    assert 'company="Eli Lilly"' in sc[0]["command"]
    assert sc[0]["command"].startswith("/dd")


def test_suggested_commands_cda_without_counterparty():
    """No counterparty → no useful /dd suggestion (DD needs a company)."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="cda", party_position="乙方", contract_text="x")
    assert svc._build_suggested_commands(inp) == []


def test_suggested_commands_non_cda_ts_silent():
    """Contract types with no wired handoff return empty list."""
    svc = LegalReviewService()
    for ct in ("mta", "license", "co_dev", "spa"):
        inp = LegalReviewInput(
            contract_type=ct,
            party_position="甲方",
            contract_text="x",
            counterparty="Foo Pharma",
        )
        assert svc._build_suggested_commands(inp) == [], f"{ct} should not suggest"


def test_suggested_commands_ts_emits_license_and_codev():
    """Stage 6: TS review → offer License Agreement + Co-Dev Agreement chips."""
    svc = LegalReviewService()
    inp = LegalReviewInput(
        contract_type="ts",
        party_position="乙方",
        contract_text="x",
        counterparty="Eli Lilly",
        project_name="PEG-001 (NSCLC)",
    )
    sc = svc._build_suggested_commands(inp)
    slugs = [c["slug"] for c in sc]
    assert slugs.count("legal-review") == 2
    cmds = [c["command"] for c in sc]
    license_cmd = next(c for c in cmds if "contract_type=license" in c)
    codev_cmd = next(c for c in cmds if "contract_type=co_dev" in c)
    for cmd in (license_cmd, codev_cmd):
        assert 'counterparty="Eli Lilly"' in cmd
        assert 'project_name="PEG-001 (NSCLC)"' in cmd
        assert 'party_position="乙方"' in cmd


def test_suggested_commands_ts_without_counterparty():
    """TS with no counterparty still emits chips (counterparty field omitted)."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="ts", party_position="甲方", contract_text="x")
    sc = svc._build_suggested_commands(inp)
    assert len(sc) == 2
    for c in sc:
        assert "counterparty" not in c["command"]


def test_suggested_commands_ts_labels():
    """Chip labels are human-readable."""
    svc = LegalReviewService()
    inp = LegalReviewInput(contract_type="ts", party_position="乙方", contract_text="x")
    sc = svc._build_suggested_commands(inp)
    labels = {c["label"] for c in sc}
    assert "Draft License Agreement" in labels
    assert "Draft Co-Dev Agreement" in labels


def test_chat_tool_input_schema_is_well_formed():
    svc = LegalReviewService()
    schema = svc.chat_tool_input_schema
    assert schema["type"] == "object"
    assert "contract_type" in schema["properties"]
    # Both contract_text and filename should be optional in the schema —
    # the cross-field requirement is enforced at pydantic level, not via
    # JSON Schema's "required" array.
    assert "required" in schema
    assert "contract_text" not in schema["required"]
    assert "filename" not in schema["required"]
    assert "contract_type" in schema["required"]
    assert "party_position" in schema["required"]
