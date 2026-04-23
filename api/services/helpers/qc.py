"""
QC (质量控制) engine for AI-generated reports.

Flow:
  1. LLM extracts factual claims from report markdown (structured JSON)
  2. Each claim is verified against CRM or spot-checked via Tavily
  3. Returns a QCResult with per-claim tiers and a badge block to append

Confidence tiers:
  ✅ verified   — matched in CRM database
  🔍 sourced    — has URL citation, not re-checked
  ⚠️ unverified — model-generated, Tavily found supporting evidence
  ❌ suspicious  — model-generated, Tavily found nothing or contradiction

Usage:
    result = run_qc(markdown_text, ctx)
    final_md = markdown_text + result.badge_md
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported at type-check time — avoids a runtime dependency on
    # the report_builder module (which pulls in heavy dependencies).
    from services.report_builder import ReportContext

logger = logging.getLogger(__name__)

# ─── Prompts ────────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """你是医疗BD情报的事实核查专家。从以下报告中提取所有可核查的事实性声明。

规则：
- 只提取具体的、可被证伪的声明（数字、日期、公司行为、临床结论、交易条款）
- 跳过观点性判断（"我们认为"、"市场前景广阔"等）
- 每条声明不超过60字
- 最多提取15条最重要的声明

输出严格JSON（不要任何其他文字）：
{
  "claims": [
    {
      "text": "声明原文摘录",
      "entity": "涉及的公司/资产/药物名（没有则留空）",
      "source_hint": "crm|web|model",
      "priority": "high|medium"
    }
  ]
}

source_hint含义：
- crm: 声明明确引用了公司/资产数据库中的信息
- web: 声明后面有URL或"据XX报道"等引用
- model: 其他情况（模型直接生成，无明确出处）
"""

_QC_SUMMARY_PROMPT = """你是医疗BD情报审核员。根据以下核查结果，写一段简短的QC审核摘要（100字内，中文）。

核查结果：
{findings}

摘要要求：
- 说明整体可信度（高/中/低）
- 指出最需要人工核实的1-2个具体声明
- 不要重复列出所有条目，只做总体判断
- 语气专业客观
"""


# ─── Data types ─────────────────────────────────────────────────────────────


@dataclass
class QCClaim:
    text: str
    entity: str
    source_hint: str  # "crm" | "web" | "model"
    priority: str  # "high" | "medium"
    tier: str = "unverified"  # "verified" | "sourced" | "unverified" | "suspicious"
    evidence: str = ""  # brief reason / found URL


@dataclass
class QCResult:
    claims: list[QCClaim] = field(default_factory=list)
    summary: str = ""
    badge_md: str = ""  # full markdown block to append to report

    @property
    def verified_count(self) -> int:
        return sum(1 for c in self.claims if c.tier == "verified")

    @property
    def sourced_count(self) -> int:
        return sum(1 for c in self.claims if c.tier == "sourced")

    @property
    def warned_count(self) -> int:
        return sum(1 for c in self.claims if c.tier == "unverified")

    @property
    def suspicious_count(self) -> int:
        return sum(1 for c in self.claims if c.tier == "suspicious")


# ─── Tier icons ─────────────────────────────────────────────────────────────

_TIER_ICON = {
    "verified": "✅",
    "sourced": "🔍",
    "unverified": "⚠️",
    "suspicious": "❌",
}

_TIER_LABEL = {
    "verified": "已核实（CRM）",
    "sourced": "有引用来源",
    "unverified": "待核实",
    "suspicious": "疑似幻觉",
}


# ─── Main entry point ────────────────────────────────────────────────────────


def run_qc(markdown: str, ctx: ReportContext) -> QCResult:  # noqa: F821
    """Run QC on a report markdown. Returns QCResult with badge_md appended."""
    result = QCResult()

    # Step 1: extract claims
    ctx.log("QC: 提取事实声明…")
    claims = _extract_claims(markdown, ctx)
    if not claims:
        result.badge_md = _build_badge(result, "无可核查声明，请人工审核。")
        return result

    result.claims = claims
    ctx.log(f"QC: 提取到 {len(claims)} 条声明，开始核查…")

    # Step 2: verify each claim
    for claim in claims:
        _verify_claim(claim, ctx)

    # Step 3: compile summary via LLM
    ctx.log("QC: 生成审核摘要…")
    result.summary = _build_summary(result.claims, ctx)

    # Step 4: build badge block
    result.badge_md = _build_badge(result, result.summary)
    ctx.log(
        f"QC完成: ✅{result.verified_count} 🔍{result.sourced_count} "
        f"⚠️{result.warned_count} ❌{result.suspicious_count}"
    )
    return result


# ─── Internal helpers ────────────────────────────────────────────────────────


def _extract_claims(markdown: str, ctx: ReportContext) -> list[QCClaim]:  # noqa: F821
    # Truncate to 6000 chars to keep token cost low
    text = markdown[:6000]
    raw = ctx.llm(
        system=_EXTRACT_PROMPT,
        messages=[{"role": "user", "content": text}],
        max_tokens=1200,
    )
    try:
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```\s*$", "", raw)
        data = json.loads(raw)
        claims = []
        for item in data.get("claims", []):
            if not isinstance(item, dict) or not item.get("text"):
                continue
            claims.append(
                QCClaim(
                    text=str(item["text"])[:120],
                    entity=str(item.get("entity", "")),
                    source_hint=str(item.get("source_hint", "model")),
                    priority=str(item.get("priority", "medium")),
                )
            )
        return claims
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("QC claim extraction failed: %s | raw: %s", e, raw[:300])
        return []


def _verify_claim(claim: QCClaim, ctx: ReportContext) -> None:  # noqa: F821
    # Web-cited claims: trust the citation, mark as sourced
    if claim.source_hint == "web":
        claim.tier = "sourced"
        claim.evidence = "报告中含引用来源"
        return

    # CRM claims: try to match entity in database
    if claim.source_hint == "crm" and claim.entity:
        hit = _crm_lookup(claim.entity, ctx)
        if hit:
            claim.tier = "verified"
            claim.evidence = f"CRM命中：{hit}"
            return
        # Entity not found in CRM — downgrade to model and let Tavily check
        claim.source_hint = "model"

    # Model-generated claims: Tavily spot-check (high priority only)
    if claim.priority == "high":
        evidence = _tavily_check(claim.text, claim.entity)
        if evidence:
            claim.tier = "unverified"
            claim.evidence = f"网络检索有相关结果：{evidence[:100]}"
        else:
            claim.tier = "suspicious"
            claim.evidence = "网络检索无佐证，请人工核实"
    else:
        # Medium priority model claims: mark unverified without burning Tavily quota
        claim.tier = "unverified"
        claim.evidence = "模型生成，未检索核实"


def _crm_lookup(entity: str, ctx: ReportContext) -> str:
    """Return a short description if entity is found in CRM, else empty string."""
    if not entity.strip():
        return ""
    try:
        from crm_store import like_contains

        pat = like_contains(entity)
        row = ctx.crm_query_one(
            r"""SELECT name_cn, name_en, type FROM companies
                WHERE name_cn ILIKE %s ESCAPE '\' OR name_en ILIKE %s ESCAPE '\'
                LIMIT 1""",
            (pat, pat),
        )
        if row:
            return f"{row.get('name_cn') or row.get('name_en')} ({row.get('type', '')})"

        row = ctx.crm_query_one(
            r"""SELECT name_cn, name_en FROM assets
                WHERE name_cn ILIKE %s ESCAPE '\' OR name_en ILIKE %s ESCAPE '\'
                LIMIT 1""",
            (pat, pat),
        )
        if row:
            return f"资产: {row.get('name_cn') or row.get('name_en')}"
    except Exception as e:
        logger.warning("QC CRM lookup failed for %r: %s", entity, e)
    return ""


def _tavily_check(claim_text: str, entity: str) -> str:
    """Return snippet if Tavily finds relevant results, else empty string."""
    try:
        from services.helpers.search import search_web

        query = f"{entity} {claim_text[:80]}" if entity else claim_text[:100]
        results = search_web(query, max_results=2)
        if results:
            return results[0].get("snippet", "") or results[0].get("title", "")
    except Exception as e:
        logger.warning("QC Tavily check failed: %s", e)
    return ""


def _build_summary(claims: list[QCClaim], ctx: ReportContext) -> str:
    """Ask LLM to write a concise QC summary paragraph."""
    lines = []
    for c in claims:
        icon = _TIER_ICON.get(c.tier, "?")
        lines.append(f"{icon} [{c.priority}] {c.text} — {c.evidence}")
    findings = "\n".join(lines)

    try:
        return ctx.llm(
            system=_QC_SUMMARY_PROMPT.format(findings=findings),
            messages=[{"role": "user", "content": "请输出QC审核摘要。"}],
            max_tokens=300,
        )
    except Exception as e:
        logger.warning("QC summary LLM failed: %s", e)
        return "QC摘要生成失败，请参考下方明细。"


def _build_badge(result: QCResult, summary: str) -> str:
    """Build the markdown QC badge block."""
    lines = [
        "\n\n---",
        "## 🔎 QC 审核报告",
        "",
        f"> {summary}",
        "",
        "| 状态 | 数量 |",
        "|------|------|",
        f"| ✅ 已核实（CRM） | {result.verified_count} |",
        f"| 🔍 有引用来源 | {result.sourced_count} |",
        f"| ⚠️ 待核实 | {result.warned_count} |",
        f"| ❌ 疑似幻觉 | {result.suspicious_count} |",
    ]

    high_risk = [c for c in result.claims if c.tier == "suspicious"]
    if high_risk:
        lines += ["", "**需优先人工核实：**"]
        for c in high_risk[:5]:
            lines.append(f"- ❌ {c.text}")

    warn_claims = [c for c in result.claims if c.tier == "unverified" and c.priority == "high"]
    if warn_claims:
        lines += ["", "**建议核实：**"]
        for c in warn_claims[:5]:
            lines.append(f"- ⚠️ {c.text}")

    lines.append("\n*QC 由 AI 自动生成，仅供参考，不构成最终判断。*")
    return "\n".join(lines)
