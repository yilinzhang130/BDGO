"""users: add profile fields (company / title / phone / bio / preferences_json)

Revision ID: 7e3d9a4c6023
Revises: 6d2c8f3b5f92
Create Date: 2026-04-24 12:02:00 UTC

Added when the profile page went live so users could self-identify
(company + title for context routing) and save preferences
(preferences_json is a free-form JSON blob; not queried, only
round-tripped through the UI).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "7e3d9a4c6023"
down_revision: Union[str, None] = "6d2c8f3b5f92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR(255);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS title VARCHAR(255);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences_json TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS preferences_json;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS bio;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS phone;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS title;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS company;")
