"""Extract asset metadata from a BP file (PDF / DOCX / PPTX).

Used by the upload router to suggest a follow-up `/teaser` command after
a BP lands. Returns a best-effort dict — every field is optional and
empty strings mean "not found", not failure.

Pipeline:
  1. Plain-text extraction (PDF/DOCX via contract_extract; PPTX inline)
  2. Single LLM call with a strict JSON schema asking for company, asset,
     indication, target, phase, moa.

Failures are returned as ``{"error": "..."}`` — caller is expected to
fall through gracefully (the upload itself must always succeed).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from services.document.contract_extract import extract_contract_text

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 12_000  # cap LLM input for speed/cost
_ASSET_FIELDS = ("company_name", "asset_name", "indication", "target", "phase", "moa")

_EXTRACT_SYSTEM = """你是 BD 文档解析助手。任务：从 BP（业务计划书 / 资产介绍）文本里抽取 6 个字段。

硬规则：
- 只输出 JSON 对象，键为 company_name / asset_name / indication / target / phase / moa
- 找不到的字段写空字符串 ""，不要编造
- asset_name 优先用药物代号或商品名（如 "ABC-1234"、"PD-1单抗"）
- phase 必须是这几个之一：Preclinical / Phase 1 / Phase 2 / Phase 3 / Approved，找不到留空
- target 是分子靶点（如 "PD-1"、"BRAF"），不是治疗领域
- moa 是机制描述（如 "Anti-PD-1 monoclonal antibody"），可留空
"""

_EXTRACT_USER = """以下是 BP 文档前 {n_chars} 字：

═══════════════════════════════
{text}
═══════════════════════════════

输出严格 JSON（不要 markdown 代码块、不要解释）：
"""


def extract_asset_metadata(filepath: Path, llm_fn) -> dict:
    """Extract asset metadata from ``filepath``.

    ``llm_fn`` is a callable matching ``ReportContext.llm`` style:
    ``llm_fn(system: str, messages: list[dict], max_tokens: int) -> str``.
    Injected so we don't take a hard dependency on the report context.
    """
    try:
        text = _extract_text(filepath)
    except Exception as e:
        logger.warning("asset_extract: text extraction failed for %s: %s", filepath, e)
        return {"error": "text_extraction_failed"}

    if not text or len(text.strip()) < 200:
        return {"error": "text_too_short"}

    text = text[:_MAX_TEXT_CHARS]
    try:
        raw = llm_fn(
            system=_EXTRACT_SYSTEM,
            messages=[
                {"role": "user", "content": _EXTRACT_USER.format(n_chars=len(text), text=text)}
            ],
            max_tokens=400,
        )
    except Exception as e:
        logger.warning("asset_extract: LLM call failed: %s", e)
        return {"error": "llm_call_failed"}

    parsed = _parse_json_loosely(raw)
    if not parsed:
        return {"error": "json_parse_failed", "raw": raw[:200]}

    return {field: str(parsed.get(field) or "").strip() for field in _ASSET_FIELDS}


def build_teaser_command(asset: dict) -> str | None:
    """Build a slash-command string from an extracted asset dict.

    Returns ``None`` when too few required fields are present to make a
    useful suggestion. DealTeaserService requires company_name, asset_name,
    indication, target, phase — we ask for at least 3 of those.
    """
    required = ["company_name", "asset_name", "indication", "target", "phase"]
    present = [k for k in required if asset.get(k)]
    if len(present) < 3:
        return None
    parts = ["/teaser"]
    for k in required + ["moa"]:
        v = asset.get(k)
        if v:
            parts.append(f'{k}="{v}"')
    return " ".join(parts)


def _extract_text(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix in (".pdf", ".docx"):
        return extract_contract_text(filepath)
    if suffix in (".pptx", ".ppt"):
        return _extract_pptx(filepath)
    if suffix == ".doc":
        # python-docx doesn't read legacy .doc; skip extraction
        return ""
    return ""


def _extract_pptx(filepath: Path) -> str:
    from pptx import Presentation

    prs = Presentation(str(filepath))
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs).strip()
                    if line:
                        parts.append(line)
    return "\n".join(parts)


def _parse_json_loosely(raw: str) -> dict | None:
    """Parse JSON from an LLM response that may have leading/trailing prose."""
    if not raw:
        return None
    raw = raw.strip()
    # Strip markdown code fences if present.
    if raw.startswith("```"):
        raw = raw.strip("`")
        first_nl = raw.find("\n")
        if first_nl != -1:
            raw = raw[first_nl + 1 :]
        if raw.endswith("```"):
            raw = raw[:-3]
    # Find first {...} balanced block.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
