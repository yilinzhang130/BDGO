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

from config import REPORTS_DIR
from pydantic import BaseModel

logger = logging.getLogger(__name__)

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Cap in-memory task history to prevent unbounded growth
MAX_STORED_TASKS = 500


# Task status values — mirrored in the report_history.status column.
# Anything else would be a bug; keep tests and state-machine code in sync
# with this tuple.
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


# ─────────────────────────────────────────────────────────────
# Result + Context types
# ─────────────────────────────────────────────────────────────


@dataclass
class GeneratedFile:
    filename: str  # basename only, e.g. "paper_analysis_abc123.md"
    format: str  # "md" | "docx" | "xlsx" | "pdf"
    size: int  # bytes
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
        """Call LLM and return final assistant text (non-streaming)."""
        from services.helpers.llm import call_llm_sync

        return call_llm_sync(system=system, messages=messages, max_tokens=max_tokens)

    # ── QC ──────────────────────────────────────────────────
    def qc(self, markdown: str) -> QCResult:  # noqa: F821
        """Run QC on a markdown string and return QCResult (with .badge_md)."""
        from services.helpers.qc import QCResult, run_qc

        try:
            return run_qc(markdown, self)
        except Exception as e:
            logger.warning("QC failed: %s", e)
            result = QCResult()
            result.badge_md = "\n\n---\n## 🔎 QC 审核报告\n\n> QC 执行失败，请人工审核。\n"
            return result

    # ── CRM ─────────────────────────────────────────────────
    def crm_query(self, sql: str, params: tuple = ()) -> list[dict]:
        from crm_store import query as _q

        return _q(sql, params)

    def crm_query_one(self, sql: str, params: tuple = ()) -> dict | None:
        from crm_store import query_one as _q

        return _q(sql, params)

    def crm_count(self, sql: str, params: tuple = ()) -> int:
        from crm_store import count as _c

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

    def register_file(self, filename: str, format: str) -> GeneratedFile:
        """Register a file already written into ``output_dir`` (by an external
        generator that writes to disk directly, e.g. the rNPV Excel builder).
        Use ``save_file`` when you have bytes/text in-hand instead."""
        safe_name = Path(filename).name
        filepath = self._output_dir / safe_name
        gf = GeneratedFile(
            filename=safe_name,
            format=format,
            size=filepath.stat().st_size,
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
    enable_qc: bool = False  # set True to append QC badge after run()

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
# Task store (DB-backed queue + in-memory progress cache)
#
# DB is the source of truth for state: status, params, result, error,
# timestamps. This makes the queue visible across workers and survives
# restarts — a multi-worker deployment where requests hit different
# workers no longer loses in-flight tasks.
#
# The in-memory ``_task_cache`` only carries the live ``progress_log``
# so the UI can show streaming progress without a DB hit per log line.
# If a poll lands on a different worker the log is empty but status is
# always correct; a small, acceptable UX cost for multi-worker safety.
# ─────────────────────────────────────────────────────────────

import json as _json
from datetime import datetime

_task_cache: dict[
    str, dict
] = {}  # task_id → {"progress_log": list[str], "user_id": ..., "slug": ...}


def _cache_put(task_id: str, user_id: str | None, slug: str) -> list[str]:
    log: list[str] = []
    _task_cache[task_id] = {
        "progress_log": log,
        "user_id": user_id,
        "slug": slug,
    }
    # Bound cache size — oldest entries evicted first
    if len(_task_cache) > MAX_STORED_TASKS:
        excess = len(_task_cache) - MAX_STORED_TASKS
        for tid in list(_task_cache.keys())[:excess]:
            _task_cache.pop(tid, None)
    return log


def _epoch(dt) -> float | None:
    """Convert a DB timestamp to epoch float, or pass through a float."""
    if dt is None:
        return None
    if isinstance(dt, (int, float)):
        return float(dt)
    if isinstance(dt, datetime):
        return dt.timestamp()
    return None


def _row_to_task(row: dict, progress_log: list[str] | None = None) -> dict:
    """Reshape a report_history row into the legacy task-dict contract.

    Callers (routers/reports.py, chat) rely on the old dict shape; rather
    than touch all sites, we translate at the boundary.
    """
    try:
        files = _json.loads(row.get("files_json") or "[]")
    except (_json.JSONDecodeError, TypeError):
        files = []
    try:
        meta = _json.loads(row.get("meta_json") or "{}")
    except (_json.JSONDecodeError, TypeError):
        meta = {}
    try:
        params = _json.loads(row.get("params_json") or "{}")
    except (_json.JSONDecodeError, TypeError):
        params = {}

    return {
        "id": row["task_id"],
        "slug": row["slug"],
        "params": params,
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        "status": row.get("status") or STATUS_COMPLETED,
        "progress_log": progress_log if progress_log is not None else [],
        "created_at": _epoch(row.get("created_at")),
        "started_at": _epoch(row.get("started_at")),
        "finished_at": _epoch(row.get("finished_at")),
        "result": {
            "markdown": row.get("markdown_preview") or "",
            "files": files,
            "meta": meta,
        }
        if row.get("status") == STATUS_COMPLETED
        else None,
        "error": row.get("error"),
    }


def create_task(slug: str, params: dict, user_id: str | None = None) -> str:
    """Queue a task. Writes the queue row immediately so any worker can see it."""
    from database import transaction

    task_id = uuid.uuid4().hex[:12]
    _cache_put(task_id, user_id, slug)

    params_json = _json.dumps(params or {}, ensure_ascii=False, default=str)
    try:
        with transaction() as cur:
            cur.execute(
                "INSERT INTO report_history "
                "(user_id, task_id, slug, params_json, status) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (task_id) DO NOTHING",
                (user_id, task_id, slug, params_json, STATUS_QUEUED),
            )
    except Exception:
        # DB write failure shouldn't block task execution — the in-memory
        # cache still lets this worker track and serve the task. Multi-worker
        # visibility is degraded but not lost.
        logger.exception("Failed to persist queued task %s", task_id)

    return task_id


def _update_state(task_id: str, **fields) -> None:
    """Patch the task's report_history row. Silent on DB error."""
    if not fields:
        return
    from database import transaction

    cols = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [task_id]
    try:
        with transaction() as cur:
            cur.execute(
                f"UPDATE report_history SET {cols} WHERE task_id = %s",
                tuple(values),
            )
    except Exception:
        logger.exception("Failed to update task %s state", task_id)


def get_task(task_id: str) -> dict | None:
    """Return the task dict for polling. DB is authoritative; hot log comes
    from the in-memory cache when the task is on this worker."""
    from database import transaction

    try:
        with transaction() as cur:
            cur.execute(
                "SELECT user_id, task_id, slug, title, markdown_preview, "
                "files_json, meta_json, params_json, status, error, "
                "created_at, started_at, finished_at "
                "FROM report_history WHERE task_id = %s LIMIT 1",
                (task_id,),
            )
            row = cur.fetchone()
    except Exception:
        row = None

    if not row:
        return None

    cached = _task_cache.get(task_id)
    return _row_to_task(dict(row), progress_log=cached["progress_log"] if cached else [])


def list_tasks(limit: int = 50, user_id: str | None = None) -> list[dict]:
    """Recent tasks, DB-ordered. ``user_id=None`` returns everyone (admin)."""
    from database import transaction

    try:
        with transaction() as cur:
            if user_id:
                cur.execute(
                    "SELECT user_id, task_id, slug, title, markdown_preview, "
                    "files_json, meta_json, params_json, status, error, "
                    "created_at, started_at, finished_at "
                    "FROM report_history WHERE user_id = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit),
                )
            else:
                cur.execute(
                    "SELECT user_id, task_id, slug, title, markdown_preview, "
                    "files_json, meta_json, params_json, status, error, "
                    "created_at, started_at, finished_at "
                    "FROM report_history "
                    "ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
    except Exception:
        logger.exception("Failed to list tasks")
        return []

    out = []
    for row in rows:
        d = dict(row)
        cached = _task_cache.get(d["task_id"])
        out.append(_row_to_task(d, progress_log=cached["progress_log"] if cached else []))
    return out


def execute_task(task_id: str, service: ReportService, params: dict) -> None:
    """Run a service synchronously within the current thread.

    Called either directly (sync mode) or inside threading.Thread (async mode).
    Updates report_history in place through state transitions.
    """
    cached = _task_cache.get(task_id)
    progress_log: list[str] = cached["progress_log"] if cached else _cache_put(task_id, None, "")

    _update_state(task_id, status=STATUS_RUNNING, started_at=datetime.utcnow())

    try:
        ctx = ReportContext(task_id, progress_log)
        result = service.run(params, ctx)
        if not result.files and ctx.files:
            result.files = ctx.files

        if service.enable_qc and result.markdown:
            qc_result = ctx.qc(result.markdown)
            result.markdown += qc_result.badge_md

        title = (result.meta or {}).get("title") or service.slug
        markdown_preview = (result.markdown or "")[:2000]
        files_payload = [
            {
                "filename": f.filename,
                "format": f.format,
                "size": f.size,
                "download_url": f.download_url,
            }
            for f in result.files
        ]
        _update_state(
            task_id,
            status=STATUS_COMPLETED,
            title=title,
            markdown_preview=markdown_preview,
            files_json=_json.dumps(files_payload, ensure_ascii=False, default=str),
            meta_json=_json.dumps(result.meta, ensure_ascii=False, default=str),
            finished_at=datetime.utcnow(),
        )
    except Exception as e:
        logger.exception("Report task %s failed", task_id)
        tail = "\n".join(progress_log[-6:]) if progress_log else ""
        error_msg = f"{type(e).__name__}: {str(e)[:400]}" + (
            f"\n\n最近进度：\n{tail}" if tail else ""
        )
        _update_state(
            task_id,
            status=STATUS_FAILED,
            error=error_msg,
            finished_at=datetime.utcnow(),
        )
