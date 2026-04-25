"""messages: replace session index with composite (session_id, created_at DESC)

Revision ID: bc71de8f0467
Revises: ab60cd7f9356
Create Date: 2026-04-25 00:01:00 UTC

``load_history`` queries:
    SELECT ... FROM messages
    WHERE session_id = %s ORDER BY created_at DESC LIMIT 100

The current ``idx_messages_session(session_id)`` satisfies the WHERE
clause but forces a post-filter sort on every chat turn. With 1000+
messages in a session, Postgres fetches all matching rows then sorts in
memory. The composite index drives both the equality filter and the
sort in a single index scan.

``CREATE / DROP INDEX CONCURRENTLY`` cannot run inside a transaction, so
the connection is switched to AUTOCOMMIT for both operations. Alembic's
own transaction wrapper is bypassed — this is the standard pattern for
concurrent index operations.
"""

import sqlalchemy as sa
from alembic import op
from typing import Sequence, Union

revision: str = "bc71de8f0467"
down_revision: Union[str, None] = "ab60cd7f9356"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execution_options(isolation_level="AUTOCOMMIT")
    conn.execute(sa.text(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "idx_messages_session_created "
        "ON messages(session_id, created_at DESC)"
    ))
    conn.execute(sa.text(
        "DROP INDEX CONCURRENTLY IF EXISTS idx_messages_session"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execution_options(isolation_level="AUTOCOMMIT")
    conn.execute(sa.text(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "idx_messages_session "
        "ON messages(session_id)"
    ))
    conn.execute(sa.text(
        "DROP INDEX CONCURRENTLY IF EXISTS idx_messages_session_created"
    ))
