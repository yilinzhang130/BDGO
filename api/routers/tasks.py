"""HTTP plumbing for enrichment tasks.

Business logic (entity parsing, openclaw / LLM dispatch, DB writes)
lives in services.enrich — this file owns HTTP contracts only.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services import enrich

router = APIRouter()


class TaskRequest(BaseModel):
    agent: str = "company_analyst"
    message: str
    timeout: int = 1200


@router.post("/run")
def run_task(req: TaskRequest):
    task_id = enrich.start_task(req.agent, req.message, req.timeout)
    return {"task_id": task_id, "status": "queued"}


@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    task = enrich.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/list")
def list_tasks():
    return {"tasks": enrich.list_tasks(limit=50)}
