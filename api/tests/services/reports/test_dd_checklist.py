"""
Unit tests for DDChecklistService._build_suggested_commands.

Exercises:
  - Full CRM data → both /evaluate + /rnpv chips
  - Missing target → no /evaluate chip
  - Missing modality → no /rnpv chip
  - No asset_name at all → empty (can't build asset-level valuation)
  - Chips carry correct slug, command prefix, and param values
"""

from __future__ import annotations

import pytest
from services.reports.dd_checklist import DDChecklistInput, DDChecklistService


@pytest.fixture
def svc() -> DDChecklistService:
    return DDChecklistService()


def _inp(company: str = "Peg-Bio", asset_name: str | None = None) -> DDChecklistInput:
    return DDChecklistInput(company=company, asset_name=asset_name)


def test_full_crm_data_emits_both_chips(svc):
    inp = _inp("Peg-Bio", "PEG-001")
    lead = {
        "资产名称": "PEG-001",
        "靶点": "KRAS G12C",
        "适应症": "NSCLC",
        "技术平台类别": "小分子",
    }
    cmds = svc._build_suggested_commands(inp, lead, "Phase 2")
    slugs = [c["slug"] for c in cmds]
    assert "deal-evaluator" in slugs
    assert "rnpv-valuation" in slugs
    assert len(cmds) == 2


def test_evaluate_chip_contains_required_fields(svc):
    inp = _inp("Peg-Bio", "PEG-001")
    lead = {
        "资产名称": "PEG-001",
        "靶点": "KRAS G12C",
        "适应症": "NSCLC",
        "技术平台类别": "小分子",
    }
    cmds = svc._build_suggested_commands(inp, lead, "Phase 2")
    evaluate = next(c for c in cmds if c["slug"] == "deal-evaluator")
    assert evaluate["command"].startswith("/evaluate")
    assert 'company_name="Peg-Bio"' in evaluate["command"]
    assert 'asset_name="PEG-001"' in evaluate["command"]
    assert 'target="KRAS G12C"' in evaluate["command"]
    assert 'indication="NSCLC"' in evaluate["command"]
    assert 'phase="Phase 2"' in evaluate["command"]


def test_rnpv_chip_contains_required_fields(svc):
    inp = _inp("Peg-Bio", "PEG-001")
    lead = {
        "资产名称": "PEG-001",
        "靶点": "KRAS G12C",
        "适应症": "NSCLC",
        "技术平台类别": "小分子",
    }
    cmds = svc._build_suggested_commands(inp, lead, "Phase 2")
    rnpv = next(c for c in cmds if c["slug"] == "rnpv-valuation")
    assert rnpv["command"].startswith("/rnpv")
    assert 'company_name="Peg-Bio"' in rnpv["command"]
    assert 'asset_name="PEG-001"' in rnpv["command"]
    assert 'indication="NSCLC"' in rnpv["command"]
    assert 'phase="Phase 2"' in rnpv["command"]
    assert 'modality="小分子"' in rnpv["command"]


def test_missing_target_suppresses_evaluate_chip(svc):
    inp = _inp("Peg-Bio", "PEG-001")
    lead = {
        "资产名称": "PEG-001",
        "靶点": "",
        "适应症": "NSCLC",
        "技术平台类别": "ADC",
    }
    cmds = svc._build_suggested_commands(inp, lead, "Phase 1")
    slugs = [c["slug"] for c in cmds]
    assert "deal-evaluator" not in slugs
    assert "rnpv-valuation" in slugs


def test_missing_modality_suppresses_rnpv_chip(svc):
    inp = _inp("Peg-Bio", "PEG-001")
    lead = {
        "资产名称": "PEG-001",
        "靶点": "PD-L1",
        "适应症": "NSCLC",
        "技术平台类别": "",
    }
    cmds = svc._build_suggested_commands(inp, lead, "Phase 3")
    slugs = [c["slug"] for c in cmds]
    assert "deal-evaluator" in slugs
    assert "rnpv-valuation" not in slugs


def test_no_asset_name_returns_empty(svc):
    """No asset → can't build asset-level valuation commands."""
    inp = _inp("Peg-Bio", None)
    lead = {}
    cmds = svc._build_suggested_commands(inp, lead, "Phase 1")
    assert cmds == []


def test_asset_name_from_inp_used_when_lead_empty(svc):
    """inp.asset_name fallback if lead dict has no 资产名称."""
    inp = _inp("Pharma Co", "TEST-999")
    lead = {
        "靶点": "EGFR",
        "适应症": "Lung Cancer",
        "技术平台类别": "mAb",
    }
    cmds = svc._build_suggested_commands(inp, lead, "Phase 2")
    evaluate = next((c for c in cmds if c["slug"] == "deal-evaluator"), None)
    assert evaluate is not None
    assert 'asset_name="TEST-999"' in evaluate["command"]


# ── Perspective parameter (S3-02) ───────────────────────────


def test_input_default_perspective_is_buyer():
    inp = DDChecklistInput(company="Peg-Bio")
    assert inp.perspective == "buyer"


def test_input_accepts_seller_perspective():
    inp = DDChecklistInput(company="Peg-Bio", perspective="seller")
    assert inp.perspective == "seller"


def test_input_rejects_invalid_perspective():
    import pytest

    with pytest.raises(ValueError):
        DDChecklistInput(company="Peg-Bio", perspective="advisor")  # type: ignore[arg-type]


def test_get_system_prompt_buyer():
    from services.reports.dd_checklist import _get_system_prompt

    prompt = _get_system_prompt("buyer")
    assert "代表**买方" in prompt
    assert "尽调问题清单" in prompt


def test_get_system_prompt_seller():
    from services.reports.dd_checklist import _get_system_prompt

    prompt = _get_system_prompt("seller")
    assert "代表**卖方" in prompt
    assert "买方最可能问的尖锐问题" in prompt
    assert "我方应当准备的答复要点" in prompt


def test_get_executive_summary_prompt_buyer():
    from services.reports.dd_checklist import _get_executive_summary_prompt

    prompt = _get_executive_summary_prompt("buyer")
    assert "DD 的核心关注点" in prompt or "DD" in prompt


def test_get_executive_summary_prompt_seller():
    from services.reports.dd_checklist import _get_executive_summary_prompt

    prompt = _get_executive_summary_prompt("seller")
    assert "买方" in prompt
    assert "会议" in prompt or "攻防" in prompt


def test_chapter_prompt_buyer_uses_buyer_template():
    """Buyer perspective → output template asks for `期望答复` only."""
    from services.reports.dd_checklist import _CHAPTER_TITLES, _chapter_prompt

    prompt = _chapter_prompt(
        chapter_indices=[1],
        chapter_titles=_CHAPTER_TITLES,
        chapter_weights=["medium"] * 8,
        asset_info="...",
        positioning="FIC",
        stage="Phase 2",
        extra_context="",
        web_block="",
        perspective="buyer",
    )
    assert "期望答复" in prompt
    assert "我方答复要点" not in prompt
    assert "DD 问题清单" in prompt


def test_chapter_prompt_seller_uses_seller_template():
    """Seller perspective → output template asks for Q + 我方答复要点."""
    from services.reports.dd_checklist import _CHAPTER_TITLES, _chapter_prompt

    prompt = _chapter_prompt(
        chapter_indices=[1],
        chapter_titles=_CHAPTER_TITLES,
        chapter_weights=["medium"] * 8,
        asset_info="...",
        positioning="FIC",
        stage="Phase 2",
        extra_context="",
        web_block="",
        perspective="seller",
    )
    assert "我方答复要点" in prompt
    assert "买方可能问的问题" in prompt or "买方最可能问的问题" in prompt
    assert "买方在 DD 会议上最可能问的问题 + 我方答复要点" in prompt


def test_chat_tool_input_schema_includes_perspective(svc):
    schema = svc.chat_tool_input_schema
    assert "perspective" in schema["properties"]
    assert schema["properties"]["perspective"]["enum"] == ["buyer", "seller"]
    assert schema["properties"]["perspective"]["default"] == "buyer"
