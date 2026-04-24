"""Orchestration for the enrichment task:
  1. OpenClaw agent (fast path, subprocess)
  2. MiniMax / fallback LLM (slow path, writes structured output back to CRM)

In-memory task state lives here; routers/tasks.py is pure HTTP plumbing
around ``start_task`` / ``get_task`` / ``list_tasks``.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
import uuid

from crm_store import query, update_row

from services.external.llm import _extract_json_object, call_llm_sync

from .prompts import (
    EMPTY_MARKERS,
    ENRICH_ASSET_PROMPT,
    ENRICH_COMPANY_PROMPT,
    SYSTEM_PROMPT,
    VALID_ASSET_COLS,
    VALID_COMPANY_COLS,
)

logger = logging.getLogger(__name__)

# Hardcoded because the CLI lives at a predictable install path on the
# VM. If we ever Dockerise the deploy, lift this to config.
OPENCLAW_BIN = "/usr/local/bin/openclaw"

# In-process task state. Tasks don't survive uvicorn restarts — acceptable
# for an enrichment job (restart ⇒ retry), bad for report_history
# (hence that one uses the auth DB).
_tasks: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────
# Parsing + CRM helpers (pure)
# ─────────────────────────────────────────────────────────────


def _extract_entity(message: str) -> tuple[str, str, str]:
    """Extract (entity_type, name, company) from a free-text task message."""
    msg = message.replace("@分析", "").replace("分析", "").strip()

    if "临床试验" in message or "clinical" in message.lower():
        return ("clinical", msg.split("(")[0].strip(), "")

    if "交易" in message or "deal" in message.lower():
        return ("deal", msg, "")

    # Asset pattern: "name (company)" or "对资产 name (company) ..."
    cleaned = re.sub(r"^(对资产|资产|评估|进行四象限评估|四象限评估)\s*", "", msg).strip()
    m = re.match(r"(.+?)\s*\((.+?)\)", cleaned)
    if m:
        return ("asset", m.group(1).strip(), m.group(2).strip())

    # Default: company
    return ("company", msg, "")


def _get_crm_context(entity_type: str, name: str, company: str) -> str:
    """Format existing CRM row as a readable block for prompt injection."""
    parts: list[str] = []
    if entity_type == "company":
        rows = query('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))
    elif entity_type == "asset":
        rows = query(
            'SELECT * FROM "资产" WHERE "文本" = ? AND "所属客户" = ?',
            (name, company),
        )
    else:
        rows = []

    if rows:
        for k, v in rows[0].items():
            if v and str(v).strip():
                parts.append(f"  {k}: {v}")
    return "\n".join(parts) if parts else "（无现有数据）"


def _build_enrich_prompt(entity_type: str, name: str, company: str, message: str) -> str:
    """Compose the per-entity prompt with the current CRM data merged in."""
    crm_data = _get_crm_context(entity_type, name, company)
    if entity_type == "company":
        return ENRICH_COMPANY_PROMPT.format(name=name, crm_data=crm_data)
    if entity_type == "asset":
        return ENRICH_ASSET_PROMPT.format(name=name, company=company, crm_data=crm_data)
    # Clinical / deals: no structured write, just a text analysis prompt.
    return f"分析 {message}\n\n现有数据:\n{crm_data}\n\n请提供简洁的BD分析。"


def _write_enriched_fields(entity_type: str, name: str, company: str, parsed: dict) -> int:
    """Apply allowlisted LLM output to the CRM. Returns number of fields written.

    Safety rules:
      - Only columns in VALID_{COMPANY,ASSET}_COLS are written.
      - Empty / placeholder values ("-", "N/A", "无", etc.) are dropped.
      - Only empty existing fields are overwritten — never clobber.
    """
    if entity_type not in ("company", "asset"):
        return 0

    existing = query(
        'SELECT * FROM "公司" WHERE "客户名称" = ?'
        if entity_type == "company"
        else 'SELECT * FROM "资产" WHERE "文本" = ? AND "所属客户" = ?',
        (name,) if entity_type == "company" else (name, company),
    )
    existing_row = existing[0] if existing else {}

    valid_cols = VALID_COMPANY_COLS if entity_type == "company" else VALID_ASSET_COLS
    updates: dict[str, str] = {}
    for k, v in parsed.items():
        if k not in valid_cols:
            logger.warning("Skipping invalid column: %s", k)
            continue
        v_str = str(v).strip()
        if not v_str or v_str in EMPTY_MARKERS:
            continue
        old_val = str(existing_row.get(k, "") or "").strip()
        if not old_val or old_val == "-":  # Only fill empty fields
            updates[k] = v_str

    if not updates:
        return 0

    try:
        if entity_type == "company":
            update_row("公司", name, updates)
        else:
            update_row("资产", {"pk1": name, "pk2": company}, updates)
        logger.info("Wrote %d fields for %s %s", len(updates), entity_type, name)
        return len(updates)
    except Exception as e:
        logger.warning("DB write failed: %s", e)
        return 0


# ─────────────────────────────────────────────────────────────
# External calls (subprocess + LLM)
# ─────────────────────────────────────────────────────────────


def _run_openclaw_agent(agent: str, message: str, task_id: str, timeout: int) -> str | None:
    """Fast path: dispatch to the openclaw CLI. Returns stdout on success, None on failure.

    Caps at 120s regardless of caller timeout — the agent is
    effectively interactive; longer runs should go through the LLM
    fallback instead.
    """
    try:
        env = os.environ.copy()
        env["PATH"] = f"/usr/local/bin:/opt/homebrew/bin:{env.get('PATH', '')}"
        result = subprocess.run(
            [
                OPENCLAW_BIN,
                "agent",
                "--agent",
                agent,
                "--message",
                message,
                "--session-id",
                f"crm-dashboard-{task_id}",
                "--timeout",
                str(min(timeout, 120)),
            ],
            capture_output=True,
            text=True,
            timeout=130,
            env=env,
        )
    except Exception as e:
        logger.warning("openclaw error: %s, falling back to LLM", e)
        return None

    if result.returncode != 0 or "error" in (result.stderr or "").lower()[:200]:
        logger.warning(
            "openclaw failed (code=%d), falling back to LLM", result.returncode
        )
        return None
    return (result.stdout or "")[:5000]


def _call_enrich_llm(prompt: str) -> str | None:
    """Slow path: structured LLM call. Returns text or None on failure."""
    try:
        return call_llm_sync(SYSTEM_PROMPT, [{"role": "user", "content": prompt}])
    except Exception:
        logger.exception("Enrich LLM call failed")
        return None


# ─────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────


def _run_task(task_id: str, agent: str, message: str, timeout: int) -> None:
    """Run an enrich task: try openclaw first, fall back to LLM + DB write."""
    _tasks[task_id]["status"] = "running"
    _tasks[task_id]["started_at"] = time.time()

    entity_type, name, company = _extract_entity(message)

    # Fast path
    agent_output = _run_openclaw_agent(agent, message, task_id, timeout)
    if agent_output is not None:
        _tasks[task_id]["status"] = "completed"
        _tasks[task_id]["output"] = agent_output
        _tasks[task_id]["finished_at"] = time.time()
        return

    # Slow path: LLM + structured write
    prompt = _build_enrich_prompt(entity_type, name, company, message)
    ai_text = _call_enrich_llm(prompt)
    if not ai_text:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = "Enrichment LLM call failed"
        _tasks[task_id]["finished_at"] = time.time()
        return

    fields_written = 0
    parsed = _extract_json_object(ai_text)
    if parsed and isinstance(parsed, dict):
        fields_written = _write_enriched_fields(entity_type, name, company, parsed)

    _tasks[task_id]["status"] = "completed"
    _tasks[task_id]["output"] = ai_text[:3000]
    _tasks[task_id]["fields_written"] = fields_written
    _tasks[task_id]["finished_at"] = time.time()


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────


def start_task(agent: str, message: str, timeout: int) -> str:
    """Queue a new enrich task. Returns its task_id; caller polls status."""
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {
        "id": task_id,
        "agent": agent,
        "message": message,
        "status": "queued",
        "created_at": time.time(),
    }
    threading.Thread(
        target=_run_task, args=(task_id, agent, message, timeout), daemon=True
    ).start()
    return task_id


def get_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


def list_tasks(limit: int = 50) -> list[dict]:
    sorted_tasks = sorted(_tasks.values(), key=lambda t: t.get("created_at", 0), reverse=True)
    return sorted_tasks[:limit]
