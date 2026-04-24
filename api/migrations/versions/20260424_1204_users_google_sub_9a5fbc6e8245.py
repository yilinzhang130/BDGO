"""users: add google_sub for OAuth stable identifier

Revision ID: 9a5fbc6e8245
Revises: 8f4eab5d7134
Create Date: 2026-04-24 12:04:00 UTC

``sub`` is Google's immutable user identifier (the ``sub`` claim in the
ID token). Storing it lets us detect if a Google account's email
changes — without it, an attacker who takes over an email address
could impersonate the original user on next sign-in. Partial index
(``WHERE google_sub IS NOT NULL``) because email-registered users
don't have one and shouldn't bloat the index.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "9a5fbc6e8245"
down_revision: Union[str, None] = "8f4eab5d7134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub VARCHAR(50);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_google_sub "
        "ON users (google_sub) WHERE google_sub IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_google_sub;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS google_sub;")
