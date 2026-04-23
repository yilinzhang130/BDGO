# ADR 0004: Report task state machine backed by report_history

- **Status**: Accepted
- **Date**: 2026-04-24 (retrospective)

## Context

Report services (`services/reports/*.py`) take 60 – 600 seconds end-to-end: LLM calls, web search, CRM lookups, optional QC, docx/xlsx rendering. During that window:

- The HTTP request must return in seconds, not wait for the task.
- The frontend needs to poll for status, preview, and download links.
- Status polling must keep working across **uvicorn process restarts** (deploy) and across **workers** (if we ever horizontally scale).
- Users should see their own report history after reopening the tab a day later.

## Decision

Every report run creates a `report_history` row with `task_id` (UUID4 prefix), `user_id`, `slug`, `params_json`, and `status`. Status transitions through a fixed set (`services/report_builder.py`):

```
queued → running → completed
                \→ failed
```

`create_task()` writes the queued row before returning. `execute_task()` updates to `running` on start, then to `completed` (with `files_json`, `meta_json`, `markdown_preview`) or `failed` (with `error`) on finish. The HTTP response is always generated from the DB row, not from in-process state — there's a per-worker cache (`_task_cache`) but it's strictly an optimisation; the DB is authoritative.

Sync-mode services (rare, e.g. lightweight parse-args) skip the queued state by running inline before the response returns.

## Consequences

- **Good**: A uvicorn restart mid-task leaves the row as `running` indefinitely — the frontend sees a stuck task and the user can retry via `POST /api/reports/retry/{task_id}`, which creates a new row with the original `params_json`. The original row is preserved for audit.
- **Good**: `/api/reports/status/{task_id}` works from any worker. Horizontal scaling is a config change, not a code change.
- **Good**: Users see their history (`/api/reports/tasks`) permanently, which is the expected product behavior.
- **Bad**: No liveness signal on `running` rows — a crashed task looks the same as a genuinely long-running one. Revisit if task crashes become common (add a `heartbeat_at` column).
- **Bad**: The status values are string literals duplicated in the code (`STATUS_QUEUED = "queued"` constants) and in the DB column. Changing either in isolation silently desyncs — kept in lockstep by convention.

## Alternatives considered

- **Celery / RQ**: rejected at current scale — adds a Redis dependency and operational surface for a workload of a few dozen tasks per day. Revisit when concurrent task count routinely exceeds 4.
- **Keep everything in-process (`_task_cache` as source of truth)**: rejected because uvicorn restarts lose running state and users pay the price. The in-process cache stays, but as a hot-path optimisation, not source of truth.
- **Streaming progress via WebSocket / SSE instead of polling**: considered for UX. Deferred because polling is simpler to reason about across worker boundaries, and tasks are slow enough that 2 s polling interval is fine.
