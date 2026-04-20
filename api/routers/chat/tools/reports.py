"""Auto-register report services as Chat tools.

Each ReportService in ``services.REPORT_SERVICES`` becomes a MiniMax
tool. Async services kick off a background task and return ``task_id``
immediately; sync services run inline and return the markdown preview.

Adding a new report in ``services/__init__.py`` automatically exposes
it here — no edits needed to this file.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _make_report_tool(_svc):
    """Build a tool implementation closure for a single ReportService.

    execute_task persists to report_history, so this closure only
    orchestrates sync vs. async dispatch and shapes the chat-tool reply.
    """
    from services.report_builder import (
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_QUEUED,
        create_task,
        execute_task,
        get_task,
    )

    def _impl(_user_id=None, **kwargs):
        task_id = create_task(_svc.slug, kwargs, user_id=_user_id)

        if _svc.mode == "sync":
            execute_task(task_id, _svc, kwargs)
            t = get_task(task_id) or {}
            if t.get("status") == STATUS_COMPLETED:
                result = t.get("result") or {}
                return {
                    "task_id": task_id,
                    "status": STATUS_COMPLETED,
                    "markdown_preview": (result.get("markdown") or "")[:3000],
                    "files": result.get("files", []),
                    "message": (
                        "Report generated. Download: "
                        + ", ".join(f["download_url"] for f in result.get("files", []))
                    ),
                }
            return {
                "task_id": task_id,
                "status": t.get("status", STATUS_FAILED),
                "error": t.get("error"),
            }

        # Async: spawn thread, return immediately. execute_task writes its
        # own state transitions to the DB.
        threading.Thread(
            target=execute_task, args=(task_id, _svc, kwargs), daemon=True,
        ).start()
        return {
            "task_id": task_id,
            "status": STATUS_QUEUED,
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
