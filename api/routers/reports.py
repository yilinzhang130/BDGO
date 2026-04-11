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
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import transaction
from auth import get_current_user
from config import REPORTS_DIR, safe_path_within
from services import REPORT_SERVICES, get_service, list_services
from services.report_builder import (
    ReportContext,
    create_task,
    execute_task,
    get_task,
    list_tasks,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/list")
def list_report_services():
    return {
        "services": [svc.to_api_dict() for svc in list_services()],
    }


@router.get("/tasks")
def list_report_tasks(limit: int = 50):
    """List recent report tasks (for debugging / history UI)."""
    return {"tasks": list_tasks(limit=limit)}


@router.get("/download/{task_id}/{format}")
def download_report(task_id: str, format: str):
    """Serve the generated file for a completed task."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Task not complete: {task['status']}")

    result = task.get("result") or {}
    files = result.get("files", [])
    match = next((f for f in files if f["format"] == format), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"No {format} file in this report")

    task_dir = REPORTS_DIR / task_id
    filepath = safe_path_within(task_dir, match["filename"])
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    media_type_map = {
        "md": "text/markdown; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    media_type = media_type_map.get(format, "application/octet-stream")

    return FileResponse(
        path=str(filepath),
        filename=match["filename"],
        media_type=media_type,
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
