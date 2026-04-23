"""add api_request_logs table

Revision ID: a7eceb4cad87
Revises: 442676e3bb8e
Create Date: 2026-04-23 10:00:00 UTC

Per-request log for external (X-API-Key) traffic — powers per-key quota
enforcement and a future usage dashboard. JWT/browser traffic is
*intentionally* not logged here; it flows through ``usage_logs`` when it
hits the chat path, and is otherwise not metered.

Columns:
  * ``key_id``      → ``api_keys.id`` (CASCADE on revoke is fine; we keep
    ``user_id`` denormalised so reports survive a key's deletion)
  * ``status``      HTTP status code (200 on success; keep 4xx/5xx here so
    error-rate dashboards don't need a separate source)
  * ``latency_ms``  request duration for perf investigation
  * ``created_at``  partitioning / retention cutoff

Retention policy (operational, not enforced in schema): keep 90 days,
then drop partitions. We intentionally do NOT keep request bodies or
response payloads — this is a quota ledger, not an audit log.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a7eceb4cad87"
down_revision: Union[str, None] = "442676e3bb8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_request_logs (
            id BIGSERIAL PRIMARY KEY,
            key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            method VARCHAR(10) NOT NULL,
            path VARCHAR(255) NOT NULL,
            status INTEGER NOT NULL,
            latency_ms INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )
    # Hot path: "how many calls has key X made today?"
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_api_request_logs_key_created
            ON api_request_logs(key_id, created_at DESC);
        """
    )
    # Per-user aggregate view
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_api_request_logs_user_created
            ON api_request_logs(user_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_request_logs_user_created;")
    op.execute("DROP INDEX IF EXISTS idx_api_request_logs_key_created;")
    op.execute("DROP TABLE IF EXISTS api_request_logs;")
