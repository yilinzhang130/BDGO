"""add api_keys table

Revision ID: 442676e3bb8e
Revises: 00000000baseline
Create Date: 2026-04-22 12:00:00 UTC

Introduces the ``api_keys`` table so external consumers can authenticate via
``X-API-Key`` instead of a JWT Bearer token. See ``api_keys.py`` for the
application-side create/verify/revoke logic.

Design notes:
  * ``key_hash`` stores sha256(full_key). Full keys are shown once at
    creation and never again — DB compromise must not leak live keys.
  * ``key_prefix`` is the first ~14 chars (e.g. ``bdgo_live_ab12``) so the
    UI can render a recognisable label without touching the hash.
  * ``revoked_at IS NULL`` is the canonical "active" predicate — partial
    indexes below keep lookups fast without hard-deleting rows (we want an
    audit trail of revoked keys).
  * ``quota_daily`` NULL = inherits the user's tier default. The per-request
    limit is enforced in ``rate_limit.py`` against ``api_request_logs``.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "442676e3bb8e"
down_revision: Union[str, None] = "00000000baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            key_prefix VARCHAR(20) NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            scopes TEXT[] NOT NULL DEFAULT '{}',
            quota_daily INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_used_at TIMESTAMP,
            last_used_ip VARCHAR(45),
            revoked_at TIMESTAMP,
            expires_at TIMESTAMP
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_api_keys_user_active
            ON api_keys(user_id)
            WHERE revoked_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash_active
            ON api_keys(key_hash)
            WHERE revoked_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_keys_hash_active;")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_user_active;")
    op.execute("DROP TABLE IF EXISTS api_keys;")
