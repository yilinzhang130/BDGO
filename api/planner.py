"""
planner.py — Claude-Code-style plan generation for long BD tasks.

Before executing a long analytical request, the planner LLM produces a
structured JSON plan of 2–6 steps. The user can uncheck steps they don't
want; then the execution LLM runs only the approved steps.

Design:
  - Planner uses the same MiniMax Anthropic-compat endpoint, but with a
    different system prompt, *no tools*, and `max_tokens=1500`.
  - Returns JSON matching `PlanProposal` (see below). If the model
    returns invalid JSON, caller falls back to normal execution.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import httpx

from models import ModelSpec

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """你是 BD Go 的规划专家。用户请求的是一个需要多步执行的复杂 BD 任务。

你的工作是：根据用户请求，输出一个 JSON 格式的执行计划，**不要直接执行任务**、**不要调用任何工具**。

**输出要求**（严格）：
- 只输出 JSON，不要任何其他文字、解释、markdown 围栏
- JSON schema：
```
{
  "title": "简洁的任务标题（10-20字）",
  "summary": "一句话概括计划将做什么（30字内）",
  "steps": [
    {
      "id": "s1",
      "title": "步骤标题（10字内）",
      "description": "这一步具体做什么（1-2句话）",
      "tools_expected": ["search_companies", "search_assets"],
      "required": false,
      "default_selected": true,
      "estimated_seconds": 30
    }
  ]
}
```

**规划原则**：
- 2–6 个步骤，多于6个通常说明没想清楚
- 每个步骤必须**独立可取消**——取消后其他步骤仍然有意义
- `required: true` 只用于没有它任务就做不成的步骤（通常是数据收集类）
- `tools_expected` 列出这步大概率会用到的 tool 名称（仅用于 UI 图标，不是硬约束）
  - 可用 tool：search_companies, search_assets, search_clinical, search_deals,
    query_treatment_guidelines, tavily_search, crm_aggregate, skill_mnc_buyer_profile,
    skill_biotech_deal_asset_evaluator, skill_company_analysis
- `estimated_seconds` 是粗估（30 = 一次搜索，60 = 需要多次检索+对比，120+ = 需要综合分析）

**常见场景的参考模板**：
- "分析 AbbVie 的 BD 机会"：[扫描管线, 识别空缺领域, 匹配中国资产, 提交建议]
- "生成 MNC 买方画像"：[获取基础信息, 分析交易历史, 识别 BD 偏好, 生成报告]
- "找出最近适合 X 的破产者"：[澄清筛选条件, 查询候选, 对比评分, 输出清单]
- "BP 分析"（用户上传文件）：[提取关键实体, 查 CRM 交叉验证, 查临床格局, 评估机会]

现在根据用户请求输出计划 JSON。"""


async def generate_plan(
    message: str,
    history: list[dict],
    model: ModelSpec,
    file_context: str = "",
) -> dict | None:
    """Call the planner LLM once and return a parsed plan dict, or None on failure.

    `history` is the conversation history (chronological). We pass only the last
    4 turns to keep planner input small; full history stays in the execution phase.
    """
    # Build planner messages: last 2 exchanges + current user message
    short_hist = _recent_text_only(history, turns=2)
    current_user = message
    if file_context:
        current_user = f"{message}\n\n[用户还上传了以下文件摘要]\n{file_context[:2000]}"

    messages = short_hist + [{"role": "user", "content": current_user}]

    body = {
        "model": model.api_model,
        "system": PLANNER_SYSTEM_PROMPT,
        "messages": messages,
        "max_tokens": 1500,
        "stream": False,
        # NO tools — planner must not execute, only plan
    }
    headers = {
        "x-api-key": model.api_key,
        "Content-Type": "application/json",
    }
    if model.anthropic_version:
        headers["anthropic-version"] = model.anthropic_version

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(model.api_url, json=body, headers=headers)
            if resp.status_code != 200:
                logger.warning("Planner LLM returned %d: %s", resp.status_code, resp.text[:300])
                return None
            data = resp.json()
    except Exception:
        logger.exception("Planner LLM call failed")
        return None

    # Extract text from Anthropic-compat response shape
    # {"content": [{"type": "text", "text": "..."}]}
    raw_text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            raw_text += block.get("text", "")

    if not raw_text.strip():
        return None

    plan = _parse_plan_json(raw_text)
    if plan is None:
        logger.warning("Planner returned unparseable JSON: %s", raw_text[:500])
        return None

    # Collect input/output token usage for billing
    usage = data.get("usage", {}) or {}
    plan["_usage"] = {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
    }
    return plan


def _parse_plan_json(text: str) -> dict | None:
    """Extract and validate a plan JSON from the planner output.

    Planners sometimes wrap JSON in markdown fences despite instructions. Strip those.
    """
    text = text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)

    # Extract the first top-level {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    json_text = text[start : end + 1]

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    if "steps" not in parsed or not isinstance(parsed["steps"], list):
        return None
    if not parsed["steps"]:
        return None

    # Normalize steps + attach a stable plan_id
    normalized_steps = []
    for idx, step in enumerate(parsed["steps"]):
        if not isinstance(step, dict):
            continue
        sid = str(step.get("id") or f"s{idx + 1}")
        normalized_steps.append({
            "id": sid,
            "title": str(step.get("title") or f"步骤 {idx + 1}"),
            "description": str(step.get("description") or ""),
            "tools_expected": [str(t) for t in (step.get("tools_expected") or []) if t],
            "required": bool(step.get("required", False)),
            "default_selected": bool(step.get("default_selected", True)),
            "estimated_seconds": int(step.get("estimated_seconds") or 30),
        })

    if not normalized_steps:
        return None

    return {
        "plan_id": uuid.uuid4().hex[:16],
        "title": str(parsed.get("title") or "执行计划"),
        "summary": str(parsed.get("summary") or ""),
        "steps": normalized_steps,
        "_usage": parsed.get("_usage", {}),
    }


def _recent_text_only(history: list[dict], turns: int = 2) -> list[dict]:
    """Return the last `turns` user/assistant pairs as plain text.

    Strips tool_use/tool_result blocks so the planner sees a clean conversation.
    """
    simplified = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if role not in ("user", "assistant"):
            continue
        # Extract plain text from structured content
        if isinstance(content, list):
            text = " ".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ).strip()
        else:
            text = str(content or "").strip()
        if not text:
            continue
        simplified.append({"role": role, "content": text})

    # Keep only last `turns` user+assistant pairs = `turns*2` messages
    return simplified[-(turns * 2):]


def build_plan_constraint(plan_title: str, selected_steps: list[dict]) -> str:
    """Build the system-prompt suffix to inject when executing an approved plan."""
    lines = [f"{s['id']}: {s['title']}" for s in selected_steps]
    return (
        "\n\n[用户已批准的执行计划]\n"
        f"任务: {plan_title}\n"
        "请严格按以下步骤执行，不要偏离方向：\n  - "
        + "\n  - ".join(lines)
        + "\n完成所有步骤后综合输出最终结论。"
    )


# ─────────────────────────────────────────────────────────────
# Context compaction (layer 2) — LLM summary of old turns
# ─────────────────────────────────────────────────────────────

SUMMARIZER_SYSTEM_PROMPT = """你是会话摘要专家。用户和 BD AI 助手的对话已经很长，需要把**较旧的轮次**压缩成一段精简的会话摘要，供后续对话继续参考。

**输出要求**：
- 只输出一段中文纯文本（不要 JSON、不要 markdown 标题）
- 80–250 字，信息密度高
- 覆盖：用户关心的核心问题、已查询过的公司/资产/试验/交易、重要结论、用户的明确偏好
- 省略：客套话、已被后续回答覆盖的中间推理、工具调用细节
- 如果已存在一段"此前摘要"（会提供），请基于它 **增量更新**，不要遗忘原有要点

输出格式示例：
"用户聚焦 AbbVie 神经免疫 BD 机会。已查过 AbbVie 管线（23 个活跃资产）、近 3 年交易（8 笔，平均首付 4.5 亿）、买方偏好（偏好 II 期及以上）。核心结论：AbbVie 在 MS 和 ALS 管线薄弱，中国有 3 家 biotech 值得推荐。用户下一步想看具体靶点匹配。"
"""


async def summarize_history(
    old_turns: list[dict],
    existing_brief: str | None,
    model: ModelSpec,
) -> str | None:
    """Call the summarizer LLM on old turns (+ any existing brief).

    Returns the new brief text, or None if the call fails.
    """
    # Serialize old turns as readable text for the summarizer
    lines: list[str] = []
    if existing_brief:
        lines.append(f"[此前摘要]\n{existing_brief}\n")
    for m in old_turns:
        role = "用户" if m.get("role") == "user" else "助手"
        content = m.get("content")
        if isinstance(content, list):
            text = " ".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ).strip()
        else:
            text = str(content or "").strip()
        if not text:
            continue
        # Cap each turn at 800 chars to keep summarizer input manageable
        if len(text) > 800:
            text = text[:800] + "…"
        lines.append(f"{role}: {text}")

    payload = "\n\n".join(lines)
    if not payload.strip():
        return existing_brief

    body = {
        "model": model.api_model,
        "system": SUMMARIZER_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": payload}],
        "max_tokens": 600,
        "stream": False,
    }
    headers = {
        "x-api-key": model.api_key,
        "Content-Type": "application/json",
    }
    if model.anthropic_version:
        headers["anthropic-version"] = model.anthropic_version

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(model.api_url, json=body, headers=headers)
            if resp.status_code != 200:
                logger.warning("Summarizer LLM returned %d: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
    except Exception:
        logger.exception("Summarizer LLM call failed")
        return None

    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
    text = text.strip()
    return text or None
