"""sessions: add brief cache columns for context compaction

Revision ID: 5c1b7e2a4e81
Revises: a7eceb4cad87
Create Date: 2026-04-24 12:00:00 UTC

Context-compaction layer-2: older messages get summarised into a brief
that's carried forward so the LLM's context window doesn't balloon on
long chats. ``brief`` holds the rolling summary; ``brief_ts`` marks the
cutoff (messages with created_at <= brief_ts are already covered).

Idempotent: ADD COLUMN IF NOT EXISTS. Safe to run against an existing
database that was bootstrapped by the legacy ``auth_db._SCHEMA_SQL``
DO/EXCEPTION blocks.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "5c1b7e2a4e81"
down_revision: Union[str, None] = "a7eceb4cad87"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS brief TEXT;")
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS brief_ts TIMESTAMP;")


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS brief_ts;")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS brief;")
