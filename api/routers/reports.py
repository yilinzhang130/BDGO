"""
Reports API router.

Endpoints:
  POST /api/reports/generate       — run a report (sync or async based on service.mode)
  GET  /api/reports/status/{id}    — poll async task status
  GET  /api/reports/download/{id}/{format}  — download generated file
  GET  /api/reports/list           — list all available report services
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import transaction
from auth import get_current_user
from config import REPORTS_DIR, safe_path_within
from services import REPORT_SERVICES, get_service, list_services
from services.helpers.llm import extract_params_from_text
from services.report_builder import (
    ReportContext,
    create_task,
    execute_task,
    get_task,
    list_tasks,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MEDIA_TYPE_MAP = {
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _parse_files_json(raw) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []


def _save_report_history(user_id: str, task_id: str, slug: str, task: dict) -> None:
    """Save a completed report to the report_history table."""
    result = task.get("result") or {}
    title = result.get("meta", {}).get("title") or slug
    markdown_preview = (result.get("markdown") or "")[:2000]
    files_json = json.dumps(result.get("files", []), ensure_ascii=False, default=str)
    meta_json = json.dumps(result.get("meta", {}), ensure_ascii=False, default=str)

    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO report_history (user_id, task_id, slug, title, markdown_preview, files_json, meta_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, task_id, slug, title, markdown_preview, files_json, meta_json),
            )
    except Exception:
        logger.exception("Failed to save report history for task %s", task_id)


class GenerateRequest(BaseModel):
    slug: str
    params: dict = {}


def _execute_and_persist(task_id: str, service, params: dict, user_id: str | None) -> None:
    """Execute a report task and save to history on success."""
    execute_task(task_id, service, params)
    task = get_task(task_id)
    if task and task["status"] == "completed" and user_id:
        _save_report_history(user_id, task_id, task.get("slug", ""), task)


@router.post("/generate")
def generate_report(req: GenerateRequest, user: dict = Depends(get_current_user)):
    """Run a report service.

    - sync services: runs inline in the request thread, returns result in response
    - async services: creates a task, spawns a daemon thread, returns {task_id}
    """
    service = get_service(req.slug)
    if not service:
        raise HTTPException(status_code=404, detail=f"Unknown service: {req.slug}")

    # Validate params using the service's input model
    try:
        service.input_model(**req.params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid params: {e}")

    task_id = create_task(req.slug, req.params)
    user_id = user["id"]

    if service.mode == "sync":
        _execute_and_persist(task_id, service, req.params, user_id)
        return get_task(task_id)
    else:
        thread = threading.Thread(
            target=_execute_and_persist,
            args=(task_id, service, req.params, user_id),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": task_id,
            "status": "queued",
            "slug": req.slug,
            "estimated_seconds": service.estimated_seconds,
        }


@router.get("/status/{task_id}")
def get_report_status(task_id: str):
    """Check task status. Falls back to report_history DB after container restart."""
    task = get_task(task_id)
    if task:
        return task

    # In-memory miss — try persistent report_history
    try:
        with transaction() as cur:
            cur.execute(
                "SELECT task_id, slug, title, markdown_preview, files_json, created_at "
                "FROM report_history WHERE task_id = %s LIMIT 1",
                (task_id,),
            )
            row = cur.fetchone()
    except Exception:
        row = None

    if not row:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": row["task_id"],
        "slug": row["slug"],
        "status": "completed",
        "result": {
            "meta": {"title": row["title"]},
            "markdown": row["markdown_preview"] or "",
            "files": _parse_files_json(row.get("files_json") or "[]"),
        },
        "created_at": row["created_at"].timestamp() if row.get("created_at") else None,
    }


@router.post("/retry/{task_id}")
def retry_report(task_id: str, user: dict = Depends(get_current_user)):
    """Re-run a failed (or completed) task with its original params.

    Returns a new task_id; the original task row is preserved for audit.
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found (may have expired)")
    slug = task.get("slug")
    params = task.get("params") or {}
    service = get_service(slug)
    if not service:
        raise HTTPException(status_code=404, detail=f"Unknown service: {slug}")

    new_task_id = create_task(slug, params)
    user_id = user["id"]

    if service.mode == "sync":
        _execute_and_persist(new_task_id, service, params, user_id)
        return get_task(new_task_id)
    thread = threading.Thread(
        target=_execute_and_persist,
        args=(new_task_id, service, params, user_id),
        daemon=True,
    )
    thread.start()
    return {
        "task_id": new_task_id,
        "status": "queued",
        "slug": slug,
        "estimated_seconds": service.estimated_seconds,
    }


@router.get("/list")
def list_report_services():
    return {
        "services": [svc.to_api_dict() for svc in list_services()],
    }


class ParseArgsRequest(BaseModel):
    slug: str
    text: str  # freeform user text, e.g. "辉瑞 focus on oncology"


@router.post("/parse-args")
def parse_report_args(req: ParseArgsRequest, user: dict = Depends(get_current_user)):
    """Use the LLM to extract structured params from freeform text for a given report.

    Returns:
        params: extracted params (may be partial)
        missing: list of required field names that were not extracted
        complete: True iff all required fields are present AND input_model validates
    """
    service = get_service(req.slug)
    if not service:
        raise HTTPException(status_code=404, detail=f"Unknown service: {req.slug}")

    params = extract_params_from_text(
        req.text,
        service.chat_tool_input_schema,
        service.display_name,
    )

    required = service.chat_tool_input_schema.get("required", [])
    missing = [name for name in required if not params.get(name)]

    complete = False
    if not missing:
        try:
            service.input_model(**params)
            complete = True
        except Exception as e:
            logger.info("parse_args: params failed model validation for %s: %s", req.slug, e)
            missing = missing or ["__validation_failed__"]

    return {"params": params, "missing": missing, "complete": complete}


@router.get("/tasks")
def list_report_tasks(limit: int = 50):
    """List recent report tasks (for debugging / history UI)."""
    return {"tasks": list_tasks(limit=limit)}


@router.get("/download/{task_id}/{format}")
def download_report(task_id: str, format: str):
    """Serve the generated file for a completed task.

    Falls back to report_history DB when in-memory task is unavailable
    (e.g. after container restart).
    """
    files: list = []

    # 1. Try in-memory task store first
    task = get_task(task_id)
    if task and task.get("status") == "completed":
        files = _parse_files_json((task.get("result") or {}).get("files", []))

    # 2. Fall back to report_history DB
    if not files:
        try:
            with transaction() as cur:
                cur.execute(
                    "SELECT files_json FROM report_history WHERE task_id = %s LIMIT 1",
                    (task_id,),
                )
                row = cur.fetchone()
        except Exception:
            row = None
        if row:
            files = _parse_files_json(row.get("files_json") or "[]")

    if not files:
        raise HTTPException(status_code=404, detail="Task not found or has no files")

    match = next((f for f in files if f.get("format") == format), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"No {format} file in this report")

    task_dir = REPORTS_DIR / task_id
    filepath = safe_path_within(task_dir, match["filename"])
    if not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File missing on disk. The report may have been generated before the current deployment.",
        )

    return FileResponse(
        path=str(filepath),
        filename=match["filename"],
        media_type=MEDIA_TYPE_MAP.get(format, "application/octet-stream"),
    )


# ---------------------------------------------------------------------------
# Report history (Postgres-backed)
# ---------------------------------------------------------------------------

@router.get("/history")
def list_report_history(user: dict = Depends(get_current_user)):
    """List the user's completed reports from Postgres (limit 50, newest first)."""
    with transaction() as cur:
        cur.execute(
            "SELECT id, task_id, slug, title, markdown_preview, files_json, meta_json, created_at "
            "FROM report_history WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT 50",
            (user["id"],),
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        entry = dict(r)
        entry["created_at"] = str(entry["created_at"]) if entry.get("created_at") else None
        for jf in ("files_json", "meta_json"):
            if entry.get(jf):
                try:
                    entry[jf] = json.loads(entry[jf])
                except (json.JSONDecodeError, TypeError):
                    pass
        results.append(entry)
    return {"history": results}


@router.delete("/history/{task_id}")
def delete_report_history(task_id: str, user: dict = Depends(get_current_user)):
    """Delete a single report history entry by task_id (user-scoped)."""
    with transaction() as cur:
        cur.execute(
            "DELETE FROM report_history WHERE task_id = %s AND user_id = %s",
            (task_id, user["id"]),
        )
        deleted = cur.rowcount
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Report sharing (public links)
# ---------------------------------------------------------------------------

class ShareRequest(BaseModel):
    task_id: str


@router.post("/share")
def create_share_link(req: ShareRequest, request: Request, user: dict = Depends(get_current_user)):
    """Create a public share link for a completed report."""
    base_url = str(request.base_url).rstrip("/")

    with transaction() as cur:
        # Return existing share if one already exists
        cur.execute(
            "SELECT token FROM report_shares WHERE task_id = %s AND user_id = %s",
            (req.task_id, user["id"]),
        )
        existing = cur.fetchone()
        if existing:
            token = existing["token"]
            return {"token": token, "url": f"{base_url}/share/{token}"}

        # Look up report from history
        cur.execute(
            "SELECT title, files_json, markdown_preview FROM report_history "
            "WHERE task_id = %s AND user_id = %s",
            (req.task_id, user["id"]),
        )
        report = cur.fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found in history")

        token = secrets.token_hex(16)
        cur.execute(
            "INSERT INTO report_shares (token, task_id, user_id, title, files_json, markdown_preview) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (token, req.task_id, user["id"], report["title"], report["files_json"], report["markdown_preview"]),
        )

    return {"token": token, "url": f"{base_url}/share/{token}"}


@router.get("/share/{token}")
def get_shared_report(token: str):
    """Public endpoint — get report metadata by share token. No auth required."""
    with transaction() as cur:
        cur.execute(
            "SELECT task_id, title, files_json, markdown_preview, created_at "
            "FROM report_shares WHERE token = %s",
            (token,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    files = [
        {
            "filename": f["filename"],
            "format": f["format"],
            "size": f.get("size", 0),
            "download_url": f"/api/reports/share/{token}/download/{f['format']}",
        }
        for f in _parse_files_json(row["files_json"])
    ]

    return {
        "title": row["title"],
        "markdown_preview": row["markdown_preview"] or "",
        "files": files,
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
    }


@router.get("/share/{token}/download/{format}")
def download_shared_report(token: str, format: str):
    """Public endpoint — download a shared report file. No auth required."""
    with transaction() as cur:
        cur.execute(
            "SELECT task_id, files_json FROM report_shares WHERE token = %s",
            (token,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Share link not found")

    match = next((f for f in _parse_files_json(row["files_json"]) if f["format"] == format), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"No {format} file in this report")

    task_dir = REPORTS_DIR / row["task_id"]
    filepath = safe_path_within(task_dir, match["filename"])
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    media_type = MEDIA_TYPE_MAP.get(format, "application/octet-stream")

    return FileResponse(
        path=str(filepath),
        filename=match["filename"],
        media_type=media_type,
    )
