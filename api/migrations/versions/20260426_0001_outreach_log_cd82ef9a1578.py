"""outreach_log: BD outreach event stream (per-user, append-only)

Revision ID: cd82ef9a1578
Revises: bc71de8f0467
Create Date: 2026-04-26 00:01:00 UTC

Adds the ``outreach_log`` table for tracking BD outreach events
(cold emails, CDA followups, meeting notes, status updates) per user.

Append-only model — each row is one event at a point in time. To
"update" a thread (e.g. recipient replied), insert a new event with
the new status; do NOT UPDATE the prior row. This keeps a faithful
timeline and avoids the lock contention of a mutable row.

Mirrors the bootstrap DDL in ``auth_db.py`` so a fresh DB and an
upgraded DB end up with identical schema.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "cd82ef9a1578"
down_revision: Union[str, None] = "bc71de8f0467"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS outreach_log (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_id VARCHAR(12),
            to_company VARCHAR(255) NOT NULL,
            to_contact VARCHAR(255),
            purpose VARCHAR(40) NOT NULL,
            channel VARCHAR(20) NOT NULL DEFAULT 'email',
            status VARCHAR(30) NOT NULL DEFAULT 'sent',
            asset_context VARCHAR(255),
            perspective VARCHAR(10),
            subject TEXT,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_outreach_user_company "
            "ON outreach_log(user_id, to_company)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_outreach_user_status "
            "ON outreach_log(user_id, status)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_outreach_user_created "
            "ON outreach_log(user_id, created_at DESC)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS outreach_log"))
