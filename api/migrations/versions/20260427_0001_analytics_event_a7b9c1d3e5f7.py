"""analytics_event: event tracking table (P1-9)

Revision ID: a7b9c1d3e5f7
Revises: ef83ab2c9d14
Create Date: 2026-04-27 00:01:00 UTC

Adds ``analytics_event`` for baseline funnel measurement.
Append-only; admin-readable, any-user writable at the API layer.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b9c1d3e5f7"
down_revision: Union[str, None] = "ef83ab2c9d14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS analytics_event (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            event_name VARCHAR(100) NOT NULL,
            properties_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_analytics_event_user_created
            ON analytics_event (user_id, created_at DESC);
        """)
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS analytics_event CASCADE;"))
