"""
Unit tests for DraftMTAService.

LLM call (`run()`) is integration territory. These tests cover:
  - Service registration
  - Input model validation (required fields, our_role, ranges)
  - _build_suggested_commands chip wiring per our_role
  - _build_gap_fill_prompt filtering
  - SYSTEM_PROMPT covers all 12 sections + MTA red-flag avoidance
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.draft_mta import (
    _BINDING_SECTIONS,
    SYSTEM_PROMPT,
    DraftMTAInput,
    DraftMTAService,
)


@pytest.fixture
def svc() -> DraftMTAService:
    return DraftMTAService()


def _minimal_input(**overrides) -> DraftMTAInput:
    base = {
        "provider": "Peg-Bio",
        "recipient": "Stanford University",
        "our_role": "provider",
        "material_name": "PEG-001",
        "project_title": "Combination study with anti-CTLA4",
        "project_scope": "In vitro and mouse studies of PEG-001 + ipilimumab combination",
    }
    base.update(overrides)
    return DraftMTAInput(**base)


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "draft-mta" in REPORT_SERVICES
    s = REPORT_SERVICES["draft-mta"]
    assert isinstance(s, DraftMTAService)
    assert s.slug == "draft-mta"
    assert "docx" in s.output_formats and "md" in s.output_formats


# ── Input validation ───────────────────────────────────────


def test_input_minimal():
    inp = _minimal_input()
    assert inp.our_role == "provider"
    assert inp.material_type == "other"
    assert inp.derivatives_ownership == "negotiated"
    assert inp.publication_review_days == 30
    assert inp.term_months == 12
    assert inp.governing_law == "Hong Kong"
    assert inp.dispute_forum == "HKIAC"


def test_input_full():
    inp = DraftMTAInput(
        provider="Peg-Bio",
        recipient="Stanford University",
        our_role="provider",
        material_name="PEG-001",
        material_type="antibody",
        material_description="Humanized anti-PD1 mAb, IgG4",
        project_title="Combination study",
        project_scope="In vitro mAb + small molecule combos",
        derivatives_ownership="provider",
        publication_review_days=60,
        term_months=24,
        governing_law="New York",
        dispute_forum="ICC",
        extra_context="Provider retains ROFN on combination compositions.",
    )
    assert inp.material_type == "antibody"
    assert inp.derivatives_ownership == "provider"
    assert inp.publication_review_days == 60


def test_input_rejects_missing_required():
    with pytest.raises(ValueError):
        DraftMTAInput(
            provider="X",
            recipient="Y",
            # missing our_role
            material_name="Z",
            project_title="P",
            project_scope="S",
        )  # type: ignore[call-arg]


def test_input_rejects_invalid_our_role():
    with pytest.raises(ValueError):
        _minimal_input(our_role="advisor")


def test_input_rejects_invalid_material_type():
    with pytest.raises(ValueError):
        _minimal_input(material_type="lipid_nanoparticle")


def test_input_rejects_invalid_derivatives_ownership():
    with pytest.raises(ValueError):
        _minimal_input(derivatives_ownership="provider_owned")


def test_input_term_months_range():
    with pytest.raises(ValueError):
        _minimal_input(term_months=0)
    with pytest.raises(ValueError):
        _minimal_input(term_months=72)


def test_input_publication_review_days_range():
    with pytest.raises(ValueError):
        _minimal_input(publication_review_days=-1)
    with pytest.raises(ValueError):
        _minimal_input(publication_review_days=200)


# ── System prompt content ──────────────────────────────────


def test_system_prompt_covers_all_12_sections():
    expected = [
        "Parties",
        "Material Definition",
        "Research Use",
        "Disclosure",
        "Derivatives",
        "IP Ownership",
        "Publications",
        "Confidentiality",
        "Material Return",
        "Term & Termination",
        "Reps & Warranties",
        "Governing Law",
    ]
    for s in expected:
        # Most sections appear in the heading list inside the prompt;
        # one or two might be referenced via Chinese variants.
        assert s in SYSTEM_PROMPT or s.replace(" & ", " ").replace(" / ", " ") in SYSTEM_PROMPT


def test_system_prompt_lists_binding_sections():
    """Multiple BINDING markers required for MTA (more than TS — MTA is
    binding throughout)."""
    assert SYSTEM_PROMPT.count("BINDING") >= 5
    for s in _BINDING_SECTIONS:
        assert s.split(" / ")[0].split()[0] in SYSTEM_PROMPT


def test_system_prompt_disclaims_legal_advice():
    assert "Not legal advice" in SYSTEM_PROMPT
    assert "counsel" in SYSTEM_PROMPT.lower()


def test_system_prompt_calls_out_red_flag_for_any_purpose():
    """The 'for any purpose' MTA red flag must be explicitly forbidden."""
    assert "for any purpose" in SYSTEM_PROMPT or "为任何目的" in SYSTEM_PROMPT


def test_system_prompt_calls_out_stealth_license_quartet():
    """The 'fully paid-up / worldwide / royalty-free / sublicensable'
    red-flag combination must be flagged."""
    assert "fully paid-up" in SYSTEM_PROMPT.lower()
    assert "royalty-free" in SYSTEM_PROMPT.lower()


def test_system_prompt_emphasizes_perspective_adaptation():
    assert "provider" in SYSTEM_PROMPT.lower()
    assert "recipient" in SYSTEM_PROMPT.lower()


# ── Suggested commands ────────────────────────────────────


def test_chips_always_offers_legal_review(svc):
    inp = _minimal_input()
    chips = svc._build_suggested_commands(inp, "test-task-abc123")
    review = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert review is not None
    assert "contract_type=mta" in review["command"]


def test_chips_provider_role_offers_draft_ts_followup(svc):
    """Provider's natural BD next step is the license that follows."""
    inp = _minimal_input(our_role="provider")
    chips = svc._build_suggested_commands(inp, "test-task-abc123")
    ts = next((c for c in chips if c["slug"] == "draft-ts"), None)
    assert ts is not None
    assert "our_role=licensor" in ts["command"]


def test_chips_recipient_role_no_draft_ts(svc):
    """Recipient just received material — drafting a license is premature."""
    inp = _minimal_input(our_role="recipient")
    chips = svc._build_suggested_commands(inp, "test-task-abc123")
    assert not any(c["slug"] == "draft-ts" for c in chips)


def test_chips_review_command_party_position_per_role(svc):
    """Party position in /legal review depends on our_role."""
    provider_inp = _minimal_input(our_role="provider")
    provider_chip = svc._build_suggested_commands(provider_inp, "test-task-abc123")[0]
    # As provider (transferring) we are 甲方
    assert "甲方" in provider_chip["command"]
    assert 'counterparty="Stanford University"' in provider_chip["command"]

    recipient_inp = _minimal_input(our_role="recipient")
    recipient_chip = svc._build_suggested_commands(recipient_inp, "test-task-abc123")[0]
    # As recipient we are 乙方
    assert "乙方" in recipient_chip["command"]
    assert 'counterparty="Peg-Bio"' in recipient_chip["command"]


def test_chips_review_includes_project_name(svc):
    inp = _minimal_input()
    chip = svc._build_suggested_commands(inp, "test-task-abc123")[0]
    assert "PEG-001" in chip["command"]
    assert "Combination study" in chip["command"]


# ── Gap-fill prompt builder ────────────────────────────────


def test_gap_fill_prompt_filters_warns_and_includes_markdown():
    from services.reports.draft_mta import _build_gap_fill_prompt

    class FakeFinding:
        severity = "fail"
        section = "derivatives"
        message = "缺归属规则"
        evidence = ""

    class FakeWarn:
        severity = "warn"
        section = "writing/marketing_hyperbole"
        message = "ZZ_UNIQUE_WARN_MARKER"
        evidence = ""

    class FakeAudit:
        findings = [FakeFinding(), FakeWarn()]

    prompt = _build_gap_fill_prompt("# MTA Draft\n\ncontent", FakeAudit())
    assert "[derivatives] 缺归属规则" in prompt
    assert "ZZ_UNIQUE_WARN_MARKER" not in prompt
    assert "# MTA Draft" in prompt


def test_gap_fill_prompt_truncates_long_markdown():
    from services.reports.draft_mta import _build_gap_fill_prompt

    class FakeAudit:
        findings = []

    huge_md = "x" * 70_000
    prompt = _build_gap_fill_prompt(huge_md, FakeAudit())
    assert prompt.count("x") <= 60_000


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    expected_required = {
        "provider",
        "recipient",
        "our_role",
        "material_name",
        "project_title",
        "project_scope",
    }
    assert set(schema["required"]) == expected_required
    assert schema["properties"]["our_role"]["enum"] == ["provider", "recipient"]
    assert schema["properties"]["term_months"]["default"] == 12
    assert schema["properties"]["term_months"]["maximum"] == 60
    assert schema["properties"]["publication_review_days"]["default"] == 30
    assert schema["properties"]["derivatives_ownership"]["default"] == "negotiated"


def test_chip_includes_source_task_id_for_legal_handoff(svc):
    """The /legal chip must embed source_task_id={task_id} so /legal
    can pull the just-generated draft markdown without making the user
    re-paste. This closes the /draft-X → /legal lifecycle loop."""
    inp = _minimal_input()
    chips = svc._build_suggested_commands(inp, "task-xyz-123")
    legal_chip = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert legal_chip is not None, "every /draft-X must offer a /legal chip"
    assert "source_task_id=task-xyz-123" in legal_chip["command"], (
        f"chip command missing source_task_id: {legal_chip['command']}"
    )
