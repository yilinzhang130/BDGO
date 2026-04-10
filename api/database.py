"""
database.py — Postgres connection for the auth/users database.

Separate from db.py which handles CRM SQLite (read-only).
Uses psycopg2 with a simple connection helper and auto-creates
the users table on first call.
"""

import logging
import psycopg2
import psycopg2.extras

import config

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL — executed once on startup
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    hashed_password TEXT,
    provider VARCHAR(50) NOT NULL DEFAULT 'email',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
"""

_tables_initialised = False


def get_connection():
    """Return a new Postgres connection (caller must close it).

    Uses RealDictCursor so rows come back as plain dicts.
    Auto-creates tables on the very first call.
    """
    global _tables_initialised

    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set — cannot connect to auth database"
        )

    conn = psycopg2.connect(
        config.DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = False

    if not _tables_initialised:
        try:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA_SQL)
            conn.commit()
            _tables_initialised = True
            _logger.info("Auth database tables initialised")
        except Exception:
            conn.rollback()
            _logger.exception("Failed to initialise auth tables")
            raise

    return conn
