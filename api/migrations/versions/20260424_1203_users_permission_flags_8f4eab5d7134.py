"""users: add permission flags (is_admin / is_active / is_internal)

Revision ID: 8f4eab5d7134
Revises: 7e3d9a4c6023
Create Date: 2026-04-24 12:03:00 UTC

The three-tier permission model the whole app depends on:

- ``is_admin``    — can see /admin, stamp invites, rotate API keys
- ``is_active``   — soft-disabled flag; False blocks login without
  deleting the account (audit-friendly)
- ``is_internal`` — can see hidden CRM fields (BD priority, internal
  notes, Q scores); external users get ``strip_hidden``-filtered rows

Defaults are conservative (non-admin, active, external) — a broken
migration or unexpected NULL must not accidentally grant privileges.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "8f4eab5d7134"
down_revision: Union[str, None] = "7e3d9a4c6023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN "
        "NOT NULL DEFAULT FALSE;"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN "
        "NOT NULL DEFAULT TRUE;"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_internal BOOLEAN "
        "NOT NULL DEFAULT FALSE;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_internal;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_admin;")
