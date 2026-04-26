"""plan_templates: user-saved plan templates (X-18)

Revision ID: ef83ab2c9d14
Revises: cd82ef9a1578
Create Date: 2026-04-26 00:02:00 UTC

Adds the ``plan_templates`` table for user-saved plan templates.

Users can save any plan produced by the planner LLM as a named template
for instant reuse — the saved plan bypasses the LLM call and returns
directly to the plan-confirm UI.

Built-in templates are Python constants (no DB row needed). This table
stores only user-created custom templates.

Column notes:
  - plan_json: full PlanProposal JSON (title + summary + steps array)
  - is_builtin: reserved for future admin-seeded templates; currently
    always FALSE for user-created rows
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ef83ab2c9d14"
down_revision: Union[str, None] = "cd82ef9a1578"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS plan_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            plan_json JSONB NOT NULL,
            is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_plan_templates_user_id
            ON plan_templates (user_id, created_at DESC);
        """)
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS plan_templates CASCADE;"))
