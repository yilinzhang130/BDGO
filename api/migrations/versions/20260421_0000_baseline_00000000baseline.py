"""baseline — schema established pre-Alembic

Revision ID: 00000000baseline
Revises:
Create Date: 2026-04-21 00:00:00 UTC

This is an empty baseline. The schema at this revision matches whatever
``database.py:_SCHEMA_SQL`` produced when you ran your last deploy
(``CREATE TABLE IF NOT EXISTS`` + idempotent ``ALTER TABLE`` blocks).

Existing deployments should be stamped at this revision once:
    alembic stamp head
Fresh deployments also land here because the auto-init in database.py
already ran every statement we would otherwise put in an ``upgrade()``.

All future schema changes should go in new Alembic revisions rather
than being added to ``_SCHEMA_SQL``. The DO-$$-EXCEPTION-WHEN-duplicate
blocks in that file should be gradually retired as their columns are
covered by proper migrations.
"""

from typing import Sequence, Union


revision: str = "00000000baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty — see module docstring.
    pass


def downgrade() -> None:
    # No-op: you can't "un-baseline" an existing schema.
    pass
