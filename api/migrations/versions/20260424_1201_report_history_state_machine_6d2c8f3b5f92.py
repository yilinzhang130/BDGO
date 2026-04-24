"""report_history: unique(task_id) + retry params + execution state machine

Revision ID: 6d2c8f3b5f92
Revises: 5c1b7e2a4e81
Create Date: 2026-04-24 12:01:00 UTC

Report generation was a fire-and-forget in-process thread; survival
across restarts required persisting the job's intent + state to
Postgres. This migration packages every column that makes that work:

- ``UNIQUE(task_id)`` so the enqueue path can ``INSERT ... ON CONFLICT
  (task_id) DO UPDATE`` when a user retries.
- ``params_json`` stores the original request payload so retry doesn't
  need to reconstruct it from the UI.
- ``status / error / started_at / finished_at`` are the state-machine
  columns — without them, in-flight tasks were only visible to the
  worker that spawned them (a polling client hitting a different
  uvicorn worker saw 'not found' and the UI spun forever).
- The ``(status, created_at)`` composite index backs the polling list.

Idempotent against the legacy DO/EXCEPTION bootstrap.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "6d2c8f3b5f92"
down_revision: Union[str, None] = "5c1b7e2a4e81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD CONSTRAINT has no IF NOT EXISTS in PG — use a DO block so the
    # migration is idempotent against DBs already bootstrapped with the
    # legacy _SCHEMA_SQL.
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE report_history ADD CONSTRAINT uq_report_history_task_id
                UNIQUE (task_id);
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
        """
    )
    op.execute("ALTER TABLE report_history ADD COLUMN IF NOT EXISTS params_json TEXT;")
    op.execute(
        "ALTER TABLE report_history ADD COLUMN IF NOT EXISTS status VARCHAR(20) "
        "NOT NULL DEFAULT 'completed';"
    )
    op.execute("ALTER TABLE report_history ADD COLUMN IF NOT EXISTS error TEXT;")
    op.execute("ALTER TABLE report_history ADD COLUMN IF NOT EXISTS started_at TIMESTAMP;")
    op.execute("ALTER TABLE report_history ADD COLUMN IF NOT EXISTS finished_at TIMESTAMP;")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_report_history_status_created "
        "ON report_history(status, created_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_report_history_status_created;")
    op.execute("ALTER TABLE report_history DROP COLUMN IF EXISTS finished_at;")
    op.execute("ALTER TABLE report_history DROP COLUMN IF EXISTS started_at;")
    op.execute("ALTER TABLE report_history DROP COLUMN IF EXISTS error;")
    op.execute("ALTER TABLE report_history DROP COLUMN IF EXISTS status;")
    op.execute("ALTER TABLE report_history DROP COLUMN IF EXISTS params_json;")
    op.execute(
        "ALTER TABLE report_history DROP CONSTRAINT IF EXISTS uq_report_history_task_id;"
    )
