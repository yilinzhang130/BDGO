"""
Reports API router.

Endpoints:
  POST /api/reports/generate       — run a report (sync or async based on service.mode)
  GET  /api/reports/status/{id}    — poll async task status
  GET  /api/reports/download/{id}/{format}  — download generated file
  GET  /api/reports/list           — list all available report services
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

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


class GenerateRequest(BaseModel):
    slug: str
    params: dict = {}


@router.post("/generate")
def generate_report(req: GenerateRequest):
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

    if service.mode == "sync":
        execute_task(task_id, service, req.params)
        return get_task(task_id)
    else:
        thread = threading.Thread(
            target=execute_task,
            args=(task_id, service, req.params),
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
