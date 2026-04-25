"""
Unit tests for CompanyAnalysisService input + helper logic.

LLM call (`run()`) is integration territory — these tests cover:
  - Service registration
  - Input model defaults & validation
  - Block formatters (CRM data → prompt blocks)
  - Per-perspective suggested_commands chips
  - chat_tool_input_schema shape
"""

from __future__ import annotations

import pytest
from services import REPORT_SERVICES
from services.reports.company_analysis import (
    _PERSPECTIVE_LABEL,
    CompanyAnalysisInput,
    CompanyAnalysisService,
)


@pytest.fixture
def svc() -> CompanyAnalysisService:
    return CompanyAnalysisService()


def test_service_registered():
    assert "company-analysis" in REPORT_SERVICES
    s = REPORT_SERVICES["company-analysis"]
    assert isinstance(s, CompanyAnalysisService)
    assert s.slug == "company-analysis"
    assert "docx" in s.output_formats and "md" in s.output_formats


def test_all_perspectives_have_label():
    expected = {"buyer", "seller", "neutral"}
    assert set(_PERSPECTIVE_LABEL.keys()) == expected


def test_input_minimal_defaults():
    inp = CompanyAnalysisInput(company_name="Peg-Bio")
    assert inp.company_name == "Peg-Bio"
    assert inp.perspective == "neutral"
    assert inp.include_web_search is True
    assert inp.focus is None


def test_input_buyer_perspective_with_focus():
    inp = CompanyAnalysisInput(
        company_name="Peg-Bio",
        perspective="buyer",
        focus="重点看 BD 历史和管线 gap",
        include_web_search=False,
    )
    assert inp.perspective == "buyer"
    assert inp.include_web_search is False


def test_input_rejects_invalid_perspective():
    with pytest.raises(ValueError):
        CompanyAnalysisInput(
            company_name="X",
            perspective="advisor",  # type: ignore[arg-type]
        )


def test_format_company_block_with_data(svc):
    row = {
        "客户名称": "Peg-Bio",
        "客户类型": "Biotech",
        "所处国家": "China",
        "核心产品的阶段": "Phase 2",
        "主要核心pipeline的名字": "PEG-001",
    }
    block = svc._format_company_block(row, "Peg-Bio")
    assert "Peg-Bio" in block
    assert "Phase 2" in block
    assert "客户类型" in block


def test_format_company_block_no_match(svc):
    block = svc._format_company_block(None, "UnknownCo")
    assert "未命中" in block or "UnknownCo" in block


def test_format_assets_block_with_data(svc):
    assets = [
        {
            "资产名称": "PEG-001",
            "靶点": "KRAS G12C",
            "临床阶段": "Phase 2",
            "适应症": "NSCLC",
            "差异化分级": "BIC",
        }
    ]
    block = svc._format_assets_block(assets)
    assert "PEG-001" in block
    assert "KRAS G12C" in block
    assert "BIC" in block


def test_format_assets_block_empty(svc):
    block = svc._format_assets_block([])
    assert "无资产" in block or "网络检索" in block


def test_format_deals_block_with_data(svc):
    deals = [
        {
            "宣布日期": "2024-09-15",
            "买方公司": "Eli Lilly",
            "卖方/合作方": "Peg-Bio",
            "交易类型": "License",
            "资产名称": "PEG-001",
            "首付款($M)": 50,
            "交易总额($M)": 800,
        }
    ]
    block = svc._format_deals_block(deals, "Peg-Bio")
    assert "2024-09-15" in block
    assert "Eli Lilly" in block
    assert "$50M" in block
    assert "$800M" in block


def test_format_deals_block_empty(svc):
    block = svc._format_deals_block([], "Peg-Bio")
    assert "Peg-Bio" in block
    assert "无" in block


# ── Suggested commands ──────────────────────────────────────


def test_suggested_commands_neutral_with_no_assets(svc):
    """Neutral perspective + no CRM assets → just /email cold outreach."""
    inp = CompanyAnalysisInput(company_name="Peg-Bio", perspective="neutral")
    chips = svc._build_suggested_commands(inp, [])
    assert len(chips) == 1
    assert chips[0]["slug"] == "outreach-email"
    assert chips[0]["command"].startswith("/email")
    # neutral defaults to seller for outreach
    assert "from_perspective=seller" in chips[0]["command"]


def test_suggested_commands_buyer_with_full_asset(svc):
    """Buyer + asset with all fields → /email + /evaluate chips."""
    inp = CompanyAnalysisInput(company_name="Peg-Bio", perspective="buyer")
    assets = [
        {
            "资产名称": "PEG-001",
            "靶点": "KRAS G12C",
            "临床阶段": "Phase 2",
            "适应症": "NSCLC",
        }
    ]
    chips = svc._build_suggested_commands(inp, assets)
    slugs = [c["slug"] for c in chips]
    assert "outreach-email" in slugs
    assert "deal-evaluator" in slugs

    email = next(c for c in chips if c["slug"] == "outreach-email")
    assert "from_perspective=buyer" in email["command"]
    assert 'asset_context="PEG-001 — NSCLC"' in email["command"]

    evaluate = next(c for c in chips if c["slug"] == "deal-evaluator")
    assert 'company_name="Peg-Bio"' in evaluate["command"]
    assert 'asset_name="PEG-001"' in evaluate["command"]
    assert 'target="KRAS G12C"' in evaluate["command"]


def test_suggested_commands_buyer_with_partial_asset(svc):
    """Buyer + asset missing fields → only /email chip (evaluate suppressed)."""
    inp = CompanyAnalysisInput(company_name="Peg-Bio", perspective="buyer")
    assets = [{"资产名称": "PEG-001", "靶点": "KRAS G12C"}]  # missing indication, phase
    chips = svc._build_suggested_commands(inp, assets)
    slugs = [c["slug"] for c in chips]
    assert "outreach-email" in slugs
    assert "deal-evaluator" not in slugs


def test_suggested_commands_seller_emits_seller_email(svc):
    """Seller → /email with from_perspective=seller (we're pitching this MNC)."""
    inp = CompanyAnalysisInput(company_name="Eli Lilly", perspective="seller")
    chips = svc._build_suggested_commands(inp, [])
    assert len(chips) == 1
    cmd = chips[0]["command"]
    assert 'to_company="Eli Lilly"' in cmd
    assert "from_perspective=seller" in cmd


def test_suggested_commands_email_has_asset_context_when_lead_present(svc):
    """If CRM has a lead asset, asset_context is injected for personalization."""
    inp = CompanyAnalysisInput(company_name="Peg-Bio", perspective="seller")
    assets = [{"资产名称": "PEG-001", "适应症": "NSCLC"}]
    chips = svc._build_suggested_commands(inp, assets)
    email = chips[0]
    assert 'asset_context="PEG-001 — NSCLC"' in email["command"]


def test_suggested_commands_email_omits_asset_context_when_no_indication(svc):
    """asset_name without indication → still inject, with just the name."""
    inp = CompanyAnalysisInput(company_name="Peg-Bio", perspective="seller")
    assets = [{"资产名称": "PEG-001"}]
    chips = svc._build_suggested_commands(inp, assets)
    cmd = chips[0]["command"]
    assert 'asset_context="PEG-001"' in cmd
    assert "—" not in cmd.split('asset_context="')[1].split('"')[0]


# ── Schema ──────────────────────────────────────────────────


def test_chat_tool_input_schema(svc):
    schema = svc.chat_tool_input_schema
    assert schema["required"] == ["company_name"]
    assert schema["properties"]["perspective"]["default"] == "neutral"
    assert set(schema["properties"]["perspective"]["enum"]) == {"buyer", "seller", "neutral"}
    assert "focus" in schema["properties"]
    assert "include_web_search" in schema["properties"]
