"""
Report service framework.

Each report skill (paper-analyst, mnc-buyer-profile, ip-analyst, etc.)
becomes a subclass of ReportService. The framework provides:

1. REST dispatch — routers/reports.py looks up services by slug
2. Chat tool auto-registration — chat.py iterates REPORT_SERVICES to build tools
3. Sync/async execution — services declare mode, framework routes accordingly
4. Shared helpers via ReportContext (LLM, CRM, file I/O, progress logs)

To add a new report:
    1. Create `services/reports/my_report.py` subclassing ReportService
    2. Register it in `services/__init__.py:REPORT_SERVICES`
    3. That's it — REST + Chat tool + frontend card all pick it up automatically.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from config import REPORTS_DIR

logger = logging.getLogger(__name__)

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Cap in-memory task history to prevent unbounded growth
MAX_STORED_TASKS = 500


# ─────────────────────────────────────────────────────────────
# Result + Context types
# ─────────────────────────────────────────────────────────────

@dataclass
class GeneratedFile:
    filename: str  # basename only, e.g. "paper_analysis_abc123.md"
    format: str    # "md" | "docx" | "xlsx" | "pdf"
    size: int      # bytes
    download_url: str  # e.g. "/api/reports/download/{task_id}/md"


@dataclass
class ReportResult:
    """What a ReportService.run() returns on success."""
    markdown: str = ""  # Primary output for inline display
    files: list[GeneratedFile] = field(default_factory=list)
    meta: dict = field(default_factory=dict)  # Free-form metadata (pmid, paper count, etc)


class ReportContext:
    """Helpers passed to every ReportService.run() call.

    Centralises:
      - LLM access (MiniMax)
      - CRM read access (db.query/query_one)
      - File persistence under REPORTS_DIR/{task_id}/
      - Progress logging visible to users via status endpoint
    """

    def __init__(self, task_id: str, progress_log: list[str]):
        self.task_id = task_id
        self._progress_log = progress_log
        self._output_dir = REPORTS_DIR / task_id
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._files: list[GeneratedFile] = []

    # ── logging ─────────────────────────────────────────────
    def log(self, msg: str) -> None:
        """Append progress line. Visible via /api/reports/status/{task_id}."""
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self._progress_log.append(entry)
        logger.info("report[%s]: %s", self.task_id, msg)

    # ── LLM ─────────────────────────────────────────────────
    def llm(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> str:
        """Call MiniMax and return final assistant text (non-streaming).

        messages = [{"role": "user"|"assistant", "content": str}]
        """
        from services.helpers.llm import call_llm_sync
        return call_llm_sync(system=system, messages=messages, max_tokens=max_tokens)

    # ── CRM ─────────────────────────────────────────────────
    def crm_query(self, sql: str, params: tuple = ()) -> list[dict]:
        from db import query as _q
        return _q(sql, params)

    def crm_query_one(self, sql: str, params: tuple = ()) -> dict | None:
        from db import query_one as _q
        return _q(sql, params)

    def crm_count(self, sql: str, params: tuple = ()) -> int:
        from db import count as _c
        return _c(sql, params)

    # ── File I/O ────────────────────────────────────────────
    def save_file(self, filename: str, content: str | bytes, format: str) -> GeneratedFile:
        """Save a file under the task's output dir and register it in result.files."""
        # Sanitize filename to just basename
        safe_name = Path(filename).name
        filepath = self._output_dir / safe_name
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with open(filepath, mode, encoding=encoding) as f:
            f.write(content)
        size = filepath.stat().st_size
        gf = GeneratedFile(
            filename=safe_name,
            format=format,
            size=size,
            download_url=f"/api/reports/download/{self.task_id}/{format}",
        )
        self._files.append(gf)
        return gf

    @property
    def files(self) -> list[GeneratedFile]:
        return list(self._files)

    @property
    def output_dir(self) -> Path:
        return self._output_dir


# ─────────────────────────────────────────────────────────────
# Base class
# ─────────────────────────────────────────────────────────────

class ReportService(ABC):
    """Base class for all report-generating services."""

    # Each subclass MUST override these class attributes:
    slug: str = ""
    display_name: str = ""
    description: str = ""
    chat_tool_name: str = ""
    chat_tool_description: str = ""
    chat_tool_input_schema: dict = {}
    input_model: type[BaseModel] = BaseModel
    mode: Literal["sync", "async"] = "async"
    output_formats: list[str] = ["md"]
    estimated_seconds: int = 30
    category: str = "report"  # "report" | "analysis" | "research"

    # Optional conditional visibility rules consumed by the frontend form.
    # Format: { field_name: { "visible_when": { discriminator_field: value_or_list } } }
    # Example: { "topic": { "visible_when": { "mode": "survey" } } }
    field_rules: dict = {}

    @abstractmethod
    def run(self, params: dict, ctx: ReportContext) -> ReportResult:
        """Execute the report logic. Subclass must implement."""
        raise NotImplementedError

    def to_api_dict(self) -> dict:
        """Serialise for /api/reports/list endpoint (frontend card rendering)."""
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "description": self.description,
            "mode": self.mode,
            "output_formats": self.output_formats,
            "estimated_seconds": self.estimated_seconds,
            "category": self.category,
            "input_schema": self.chat_tool_input_schema,
            "field_rules": self.field_rules,
        }


# ─────────────────────────────────────────────────────────────
# Async task store (shared by reports router)
# ─────────────────────────────────────────────────────────────

_report_tasks: dict[str, dict] = {}


def _evict_old_tasks() -> None:
    """Drop oldest tasks once the store exceeds MAX_STORED_TASKS."""
    if len(_report_tasks) <= MAX_STORED_TASKS:
        return
    ordered = sorted(_report_tasks.items(), key=lambda kv: kv[1].get("created_at", 0))
    to_drop = len(_report_tasks) - MAX_STORED_TASKS
    for tid, _ in ordered[:to_drop]:
        _report_tasks.pop(tid, None)


def create_task(slug: str, params: dict) -> str:
    task_id = uuid.uuid4().hex[:12]
    _report_tasks[task_id] = {
        "id": task_id,
        "slug": slug,
        "params": params,
        "status": "queued",
        "progress_log": [],
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    _evict_old_tasks()
    return task_id


def get_task(task_id: str) -> dict | None:
    return _report_tasks.get(task_id)


def list_tasks(limit: int = 50) -> list[dict]:
    tasks = sorted(_report_tasks.values(), key=lambda t: t.get("created_at", 0), reverse=True)
    return tasks[:limit]


def execute_task(task_id: str, service: ReportService, params: dict) -> None:
    """Run a service synchronously within the current thread.

    Called either directly (sync mode) or inside threading.Thread (async mode).
    Mutates _report_tasks[task_id] in place.
    """
    task = _report_tasks.get(task_id)
    if not task:
        return
    task["status"] = "running"
    task["started_at"] = time.time()
    progress_log = task["progress_log"]

    try:
        ctx = ReportContext(task_id, progress_log)
        result = service.run(params, ctx)
        # Ensure files list reflects what ctx collected (services can return new GeneratedFile list OR rely on ctx.save_file)
        if not result.files and ctx.files:
            result.files = ctx.files
        task["result"] = {
            "markdown": result.markdown,
            "files": [
                {
                    "filename": f.filename,
                    "format": f.format,
                    "size": f.size,
                    "download_url": f.download_url,
                }
                for f in result.files
            ],
            "meta": result.meta,
        }
        task["status"] = "completed"
    except Exception as e:
        logger.exception("Report task %s failed", task_id)
        task["status"] = "failed"
        task["error"] = str(e)[:500]
    finally:
        task["finished_at"] = time.time()
