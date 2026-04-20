"""Auto-register report services as Chat tools.

Each ReportService in ``services.REPORT_SERVICES`` becomes a MiniMax
tool. Async services kick off a background task and return ``task_id``
immediately; sync services run inline and return the markdown preview.

Adding a new report in ``services/__init__.py`` automatically exposes
it here — no edits needed to this file.
"""

from __future__ import annotations

import json
import logging
import threading

from database import transaction

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Persistence helper
# ─────────────────────────────────────────────────────────────

def _persist_report(task_id: str, slug: str, user_id: str) -> None:
    """Save completed report to report_history so it shows up in My Reports."""
    from services.report_builder import get_task

    task = get_task(task_id)
    if not (task and task.get("status") == "completed"):
        return
    result = task.get("result") or {}
    title = result.get("meta", {}).get("title") or slug
    markdown_preview = (result.get("markdown") or "")[:2000]
    files_json = json.dumps(result.get("files", []), ensure_ascii=False, default=str)
    meta_json = json.dumps(result.get("meta", {}), ensure_ascii=False, default=str)
    params_json = json.dumps(task.get("params") or {}, ensure_ascii=False, default=str)
    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO report_history "
                "(user_id, task_id, slug, title, markdown_preview, files_json, meta_json, params_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (task_id) DO NOTHING",
                (user_id, task_id, slug, title, markdown_preview, files_json, meta_json, params_json),
            )
    except Exception:
        logger.exception("Failed to persist report history for task %s", task_id)


def _make_report_tool(_svc):
    """Build a tool implementation closure for a single ReportService."""
    from services.report_builder import create_task, execute_task, get_task

    def _impl(_user_id=None, **kwargs):
        task_id = create_task(_svc.slug, kwargs, user_id=_user_id)

        if _svc.mode == "sync":
            execute_task(task_id, _svc, kwargs)
            t = get_task(task_id)
            if t["status"] == "completed":
                if _user_id:
                    _persist_report(task_id, _svc.slug, _user_id)
                result = t.get("result") or {}
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "markdown_preview": (result.get("markdown") or "")[:3000],
                    "files": result.get("files", []),
                    "message": (
                        "Report generated. Download: "
                        + ", ".join(f["download_url"] for f in result.get("files", []))
                    ),
                }
            return {
                "task_id": task_id,
                "status": t["status"],
                "error": t.get("error"),
            }

        # Async: spawn thread, return immediately
        def _run():
            execute_task(task_id, _svc, kwargs)
            if _user_id:
                _persist_report(task_id, _svc.slug, _user_id)

        threading.Thread(target=_run, daemon=True).start()
        return {
            "task_id": task_id,
            "status": "queued",
            "estimated_seconds": _svc.estimated_seconds,
            "display_message": (
                f"已开始 {_svc.display_name}。预计 {_svc.estimated_seconds} 秒完成，"
                f"完成后可直接在本对话中下载。"
            ),
        }

    return _impl


# ─────────────────────────────────────────────────────────────
# Build schemas + impls at import time
# ─────────────────────────────────────────────────────────────

SCHEMAS: list[dict] = []
IMPLS: dict = {}
# Maps chat tool name (e.g. "analyze_ip") → canonical service slug
# (e.g. "ip-landscape"). Consumed by the streaming dispatcher so it can
# emit report_task SSE events for any report tool, regardless of name.
TOOL_NAME_TO_SLUG: dict[str, str] = {}

try:
    from services import REPORT_SERVICES

    for _svc in REPORT_SERVICES.values():
        SCHEMAS.append({
            "name": _svc.chat_tool_name,
            "description": _svc.chat_tool_description,
            "input_schema": _svc.chat_tool_input_schema,
        })
        IMPLS[_svc.chat_tool_name] = _make_report_tool(_svc)
        TOOL_NAME_TO_SLUG[_svc.chat_tool_name] = _svc.slug

    logger.info("Registered %d report services as Chat tools", len(REPORT_SERVICES))
except Exception:
    logger.exception("Failed to register report services as Chat tools")

# ── Tool-registry metadata ────────────────────────────────────────────────
# Every report tool needs the caller's user_id so the completed report can
# be persisted to report_history under the right user.
NEEDS_USER_ID: set[str] = set(TOOL_NAME_TO_SLUG.keys())
