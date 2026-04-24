"""invite_codes: add note label

Revision ID: ab60cd7f9356
Revises: 9a5fbc6e8245
Create Date: 2026-04-24 12:05:00 UTC

Free-text label on an invite code so admins can remember why they
issued one (e.g. ``"conference 2026"`` or ``"partner onboarding
batch"``). Pure metadata — the code value + use count are what
actually gate registration.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "ab60cd7f9356"
down_revision: Union[str, None] = "9a5fbc6e8245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE invite_codes ADD COLUMN IF NOT EXISTS note VARCHAR(255);")


def downgrade() -> None:
    op.execute("ALTER TABLE invite_codes DROP COLUMN IF EXISTS note;")
