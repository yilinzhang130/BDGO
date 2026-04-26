"""Unit tests for DraftLicenseService."""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.draft_license import (
    SYSTEM_PROMPT,
    DraftLicenseInput,
    DraftLicenseService,
    FinancialTerms,
)


@pytest.fixture
def svc() -> DraftLicenseService:
    return DraftLicenseService()


def _minimal_input(**overrides) -> DraftLicenseInput:
    base = {
        "licensor": "Peg-Bio",
        "licensee": "Eli Lilly",
        "our_role": "licensor",
        "asset_name": "PEG-001",
        "indication": "NSCLC",
        "phase": "Phase 2",
        "field_of_use": "Oncology",
    }
    base.update(overrides)
    return DraftLicenseInput(**base)


# ── Registration ────────────────────────────────────────────


def test_service_registered():
    assert "draft-license" in REPORT_SERVICES
    s = REPORT_SERVICES["draft-license"]
    assert isinstance(s, DraftLicenseService)
    assert "docx" in s.output_formats and "md" in s.output_formats


# ── Input validation ───────────────────────────────────────


def test_input_minimal():
    inp = _minimal_input()
    assert inp.our_role == "licensor"
    assert inp.exclusivity == "exclusive"
    assert inp.sublicense_right == "with_consent"
    assert inp.patent_prosecution_lead == "licensor"
    assert inp.term_basis == "last-to-expire-patent"
    assert inp.royalty_term_years_post_first_sale == 10
    assert isinstance(inp.financial_terms, FinancialTerms)


def test_input_full_with_lists():
    inp = DraftLicenseInput(
        licensor="Peg-Bio",
        licensee="Eli Lilly",
        our_role="licensor",
        asset_name="PEG-001",
        indication="NSCLC",
        target="KRAS G12C",
        modality="adc",
        phase="Phase 2",
        field_of_use="Oncology",
        territory="ex-China",
        exclusivity="co-exclusive",
        sublicense_right="free",
        financial_terms=FinancialTerms(
            upfront_usd_mm=50,
            equity_pct=2.5,
            dev_milestones=["IND $5M", "P2 entry $20M", "NDA $50M"],
            sales_milestones=["First $100M $25M", "$500M $75M"],
            royalty_tiered=["<$100M: 8%", "$100M-500M: 12%", ">$500M: 15%"],
        ),
        patent_prosecution_lead="licensee",
        enforcement_lead="joint",
        term_basis="fixed-term",
        fixed_term_years=20,
        royalty_term_years_post_first_sale=12,
        governing_law="New York",
        dispute_forum="ICC",
    )
    assert inp.modality == "adc"
    assert inp.term_basis == "fixed-term"
    assert inp.fixed_term_years == 20
    assert inp.financial_terms.dev_milestones == ["IND $5M", "P2 entry $20M", "NDA $50M"]


def test_input_rejects_missing_required():
    with pytest.raises(ValueError):
        DraftLicenseInput(
            licensor="X",
            licensee="Y",
            our_role="licensor",
            asset_name="Z",
            indication="W",
            phase="Phase 2",
            # missing field_of_use
        )  # type: ignore[call-arg]


def test_input_rejects_invalid_our_role():
    with pytest.raises(ValueError):
        _minimal_input(our_role="advisor")


def test_input_rejects_invalid_sublicense_right():
    with pytest.raises(ValueError):
        _minimal_input(sublicense_right="unrestricted")


def test_input_rejects_invalid_term_basis():
    with pytest.raises(ValueError):
        _minimal_input(term_basis="forever")


def test_input_royalty_term_range():
    with pytest.raises(ValueError):
        _minimal_input(royalty_term_years_post_first_sale=4)
    with pytest.raises(ValueError):
        _minimal_input(royalty_term_years_post_first_sale=21)


# ── System prompt content ──────────────────────────────────


def test_system_prompt_covers_all_13_sections():
    expected = [
        "Parties",
        "Definitions",
        "License Grant",
        "Sublicense",
        "Diligence",
        "Financial Terms",
        "Royalty Reports",
        "Audit",
        "Patent Prosecution",
        "Enforcement",
        "Improvements",
        "Confidentiality",
        "Reps",
        "Indemnification",
        "Term",
        "Termination",
        "Governing Law",
    ]
    for s in expected:
        assert s in SYSTEM_PROMPT, f"section keyword '{s}' missing from prompt"


def test_system_prompt_lists_definitions_terms():
    """Definitions section must reference the 8 core terms."""
    for t in [
        "Affiliate",
        "Licensed Product",
        "Net Sales",
        "Field",
        "Territory",
        "Effective Date",
        "Phase",
        "Sublicense",
    ]:
        assert t in SYSTEM_PROMPT


def test_system_prompt_disclaims_legal_advice():
    assert "Not legal advice" in SYSTEM_PROMPT
    assert "counsel" in SYSTEM_PROMPT.lower()


def test_system_prompt_requires_5_risks():
    """License is more complex than TS/MTA — needs ≥5 risks."""
    assert "≥ 5" in SYSTEM_PROMPT or "5 条" in SYSTEM_PROMPT or "5 commercial-risk" in SYSTEM_PROMPT


def test_system_prompt_emphasizes_termination_effects():
    """Effects of Termination is a key license-specific section."""
    assert "Effects of Termination" in SYSTEM_PROMPT or "终止后" in SYSTEM_PROMPT


# ── Formatting helpers ─────────────────────────────────────


def test_fmt_amount_none(svc):
    assert svc._fmt_amount(None, "$", "M") == "[TBD]"


def test_fmt_amount_integer(svc):
    assert svc._fmt_amount(50, "$", "M") == "$50M"


def test_fmt_list_none(svc):
    assert svc._fmt_list(None) == "[TBD]"


def test_fmt_list_empty(svc):
    assert svc._fmt_list([]) == "[TBD]"


def test_fmt_list_joins(svc):
    assert svc._fmt_list(["IND $5M", "P2 $20M"]) == "IND $5M; P2 $20M"


# ── Suggested commands ────────────────────────────────────


def test_chips_always_offers_legal_review(svc):
    inp = _minimal_input()
    chips = svc._build_suggested_commands(inp, "test-task-abc123")
    review = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert review is not None
    assert "contract_type=license" in review["command"]


def test_chips_licensor_offers_seller_dd(svc):
    inp = _minimal_input(our_role="licensor")
    chips = svc._build_suggested_commands(inp, "test-task-abc123")
    dd = next((c for c in chips if c["slug"] == "dd-checklist"), None)
    assert dd is not None
    assert "perspective=seller" in dd["command"]


def test_chips_licensee_no_dd(svc):
    inp = _minimal_input(our_role="licensee")
    chips = svc._build_suggested_commands(inp, "test-task-abc123")
    assert not any(c["slug"] == "dd-checklist" for c in chips)


def test_chips_party_position_per_role(svc):
    licensor_inp = _minimal_input(our_role="licensor")
    licensor_chip = svc._build_suggested_commands(licensor_inp, "test-task-abc123")[0]
    assert "乙方" in licensor_chip["command"]
    assert 'counterparty="Eli Lilly"' in licensor_chip["command"]

    licensee_inp = _minimal_input(our_role="licensee")
    licensee_chip = svc._build_suggested_commands(licensee_inp, "test-task-abc123")[0]
    assert "甲方" in licensee_chip["command"]
    assert 'counterparty="Peg-Bio"' in licensee_chip["command"]


# ── Gap-fill prompt builder ────────────────────────────────


def test_gap_fill_prompt_filters_warns():
    from services.reports.draft_license import _build_gap_fill_prompt

    class FakeFinding:
        severity = "fail"
        section = "definitions"
        message = "缺 Net Sales 定义"
        evidence = ""

    class FakeWarn:
        severity = "warn"
        section = "writing/marketing_hyperbole"
        message = "ZZ_UNIQUE_WARN"
        evidence = ""

    class FakeAudit:
        findings = [FakeFinding(), FakeWarn()]

    prompt = _build_gap_fill_prompt("# License\n\ncontent", FakeAudit())
    assert "[definitions] 缺 Net Sales 定义" in prompt
    assert "ZZ_UNIQUE_WARN" not in prompt


def test_gap_fill_prompt_truncates():
    from services.reports.draft_license import _build_gap_fill_prompt

    class FakeAudit:
        findings = []

    huge_md = "x" * 70_000
    prompt = _build_gap_fill_prompt(huge_md, FakeAudit())
    assert prompt.count("x") <= 60_000


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    expected_required = {
        "licensor",
        "licensee",
        "our_role",
        "asset_name",
        "indication",
        "phase",
        "field_of_use",
    }
    assert set(schema["required"]) == expected_required
    assert schema["properties"]["term_basis"]["default"] == "last-to-expire-patent"
    assert schema["properties"]["royalty_term_years_post_first_sale"]["default"] == 10


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
