"""Unit tests for DraftCoDevService."""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.draft_codev import (
    SYSTEM_PROMPT,
    DraftCoDevInput,
    DraftCoDevService,
)


@pytest.fixture
def svc() -> DraftCoDevService:
    return DraftCoDevService()


def _minimal_input(**overrides) -> DraftCoDevInput:
    base = {
        "party_a": "Peg-Bio",
        "party_b": "BeiGene",
        "our_role": "party_a",
        "program_name": "PEG-001 Co-Dev",
        "indication": "NSCLC",
    }
    base.update(overrides)
    return DraftCoDevInput(**base)


def test_service_registered():
    assert "draft-codev" in REPORT_SERVICES


def test_input_minimal():
    inp = _minimal_input()
    assert inp.our_role == "party_a"
    assert inp.cost_split_model == "50_50"
    assert inp.party_a_share_pct == 50
    assert inp.profit_model == "weighted_by_cost"
    assert inp.decision_making == "jsc_consensus"
    assert inp.deadlock_mechanism == "ceo_escalation"
    assert inp.commercialization_split == "Joint worldwide"


def test_input_full():
    inp = DraftCoDevInput(
        party_a="Peg-Bio",
        party_b="BeiGene",
        our_role="party_a",
        program_name="PEG-001 Co-Dev",
        indication="NSCLC",
        target="KRAS G12C",
        modality="adc",
        starting_phase="Phase 2",
        cost_split_model="weighted_60_40",
        party_a_share_pct=60,
        profit_model="weighted_by_cost",
        decision_making="jsc_majority",
        deadlock_mechanism="buyout_option",
        commercialization_split="Party A owns ex-China, Party B owns China",
        term_basis="fixed-term",
        fixed_term_years=15,
        governing_law="New York",
        dispute_forum="ICC",
    )
    assert inp.cost_split_model == "weighted_60_40"
    assert inp.party_a_share_pct == 60


def test_input_rejects_missing_required():
    with pytest.raises(ValueError):
        DraftCoDevInput(
            party_a="X",
            party_b="Y",
            our_role="party_a",
            program_name="P",
            # missing indication
        )  # type: ignore[call-arg]


def test_input_rejects_invalid_our_role():
    with pytest.raises(ValueError):
        _minimal_input(our_role="party_c")


def test_input_rejects_invalid_cost_split():
    with pytest.raises(ValueError):
        _minimal_input(cost_split_model="favored")


def test_input_rejects_invalid_decision_making():
    with pytest.raises(ValueError):
        _minimal_input(decision_making="dictator")


def test_input_party_a_share_pct_range():
    with pytest.raises(ValueError):
        _minimal_input(party_a_share_pct=-1)
    with pytest.raises(ValueError):
        _minimal_input(party_a_share_pct=101)


# ── System prompt content ──────────────────────────────────


def test_system_prompt_covers_all_12_sections():
    expected = [
        "Parties",
        "Definitions",
        "JSC",
        "Cost Sharing",
        "IP Ownership",
        "Commercialization",
        "Diligence",
        "Confidentiality",
        "Reps",
        "Indemnification",
        "Term",
        "Termination",
        "Buyout",
        "Governing Law",
    ]
    for s in expected:
        assert s in SYSTEM_PROMPT, f"section keyword '{s}' missing"


def test_system_prompt_emphasizes_symmetry():
    """Co-Dev must use Party A / Party B language, not licensor/licensee."""
    assert "Party A" in SYSTEM_PROMPT
    assert "Party B" in SYSTEM_PROMPT
    # Sanity check: the prompt mentions avoiding licensor/licensee
    assert "对称" in SYSTEM_PROMPT or "symmetric" in SYSTEM_PROMPT.lower()


def test_system_prompt_requires_5_risks():
    assert "≥ 5" in SYSTEM_PROMPT or "5 条" in SYSTEM_PROMPT or "5 commercial-risk" in SYSTEM_PROMPT


def test_system_prompt_addresses_buyout_mechanism():
    """Buyout / change-of-control is critical for Co-Dev."""
    assert "Buyout" in SYSTEM_PROMPT or "fair-market-value" in SYSTEM_PROMPT


def test_system_prompt_disclaims_legal_advice():
    assert "Not legal advice" in SYSTEM_PROMPT


# ── Suggested commands ────────────────────────────────────


def test_chips_offers_legal_review(svc):
    inp = _minimal_input()
    chips = svc._build_suggested_commands(inp)
    review = next((c for c in chips if c["slug"] == "legal-review"), None)
    assert review is not None
    assert "contract_type=co_dev" in review["command"]


def test_chips_party_position_per_role(svc):
    inp_a = _minimal_input(our_role="party_a")
    chip_a = svc._build_suggested_commands(inp_a)[0]
    assert "乙方" in chip_a["command"]
    assert 'counterparty="BeiGene"' in chip_a["command"]

    inp_b = _minimal_input(our_role="party_b")
    chip_b = svc._build_suggested_commands(inp_b)[0]
    assert "甲方" in chip_b["command"]
    assert 'counterparty="Peg-Bio"' in chip_b["command"]


# ── Gap-fill prompt builder ────────────────────────────────


def test_gap_fill_prompt_filters_warns():
    from services.reports.draft_codev import _build_gap_fill_prompt

    class FakeFinding:
        severity = "fail"
        section = "jsc"
        message = "缺 voting 规则"
        evidence = ""

    class FakeWarn:
        severity = "warn"
        section = "writing/marketing_hyperbole"
        message = "ZZ_UNIQUE_WARN"
        evidence = ""

    class FakeAudit:
        findings = [FakeFinding(), FakeWarn()]

    prompt = _build_gap_fill_prompt("# CoDev\n\ncontent", FakeAudit())
    assert "[jsc] 缺 voting 规则" in prompt
    assert "ZZ_UNIQUE_WARN" not in prompt


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    expected_required = {
        "party_a",
        "party_b",
        "our_role",
        "program_name",
        "indication",
    }
    assert set(schema["required"]) == expected_required
    assert schema["properties"]["our_role"]["enum"] == ["party_a", "party_b"]
    assert schema["properties"]["cost_split_model"]["default"] == "50_50"
    assert schema["properties"]["party_a_share_pct"]["default"] == 50
