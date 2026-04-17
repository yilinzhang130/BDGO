"""
database.py — Postgres connection pool for the auth/users database.

Separate from db.py which handles CRM SQLite (read-only).
Uses psycopg2 ThreadedConnectionPool for efficient connection reuse.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

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

CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(12) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
-- Context compaction cache: brief summary of messages with created_at <= brief_ts
DO $$ BEGIN
    ALTER TABLE sessions ADD COLUMN brief TEXT;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE sessions ADD COLUMN brief_ts TIMESTAMP;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(12) PRIMARY KEY,
    session_id VARCHAR(12) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tools_json TEXT,
    attachments_json TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);

CREATE TABLE IF NOT EXISTS context_entities (
    id VARCHAR(100) PRIMARY KEY,
    session_id VARCHAR(12) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(255),
    fields_json TEXT,
    href VARCHAR(255),
    added_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_context_entities_session ON context_entities(session_id);

CREATE TABLE IF NOT EXISTS report_history (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id VARCHAR(12) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    title VARCHAR(255),
    markdown_preview TEXT,
    files_json TEXT,
    meta_json TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_report_history_user ON report_history(user_id);

-- Profile fields (added via ALTER TABLE for compatibility with existing DBs)
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN company VARCHAR(255);
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN title VARCHAR(255);
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN phone VARCHAR(50);
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN bio TEXT;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN preferences_json TEXT;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN is_internal BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS report_shares (
    id SERIAL PRIMARY KEY,
    token VARCHAR(32) UNIQUE NOT NULL,
    task_id VARCHAR(12) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    files_json TEXT,
    markdown_preview TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_report_shares_token ON report_shares(token);

CREATE TABLE IF NOT EXISTS user_watchlists (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL,
    entity_key VARCHAR(255) NOT NULL,
    notes TEXT,
    added_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, entity_type, entity_key)
);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlists(user_id);

-- Invite codes (required for registration)
CREATE TABLE IF NOT EXISTS invite_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    note VARCHAR(255),
    max_uses INTEGER NOT NULL DEFAULT 1,
    use_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_invite_codes_code ON invite_codes(code);
DO $$ BEGIN
    ALTER TABLE invite_codes ADD COLUMN note VARCHAR(255);
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Credits + usage logging (see credits.py)
CREATE TABLE IF NOT EXISTS credits (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_granted NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_spent NUMERIC(14, 2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(12),
    model_id VARCHAR(64) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    credits_charged NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_created
    ON usage_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_session
    ON usage_logs(session_id);
"""

# ---------------------------------------------------------------------------
# Connection pool (lazy-initialised, thread-safe)
# ---------------------------------------------------------------------------

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()
_tables_initialised = False


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Lazy-init the connection pool on first use."""
    global _pool, _tables_initialised

    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool

        if not config.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set — cannot connect to auth database"
            )

        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=config.DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )

        if not _tables_initialised:
            conn = _pool.getconn()
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
            finally:
                _pool.putconn(conn)

        return _pool


def get_connection():
    """Borrow a connection from the pool (caller must return it via close or use transaction())."""
    pool = _get_pool()
    conn = pool.getconn()
    conn.autocommit = False
    return conn


def put_connection(conn):
    """Return a connection to the pool."""
    pool = _get_pool()
    pool.putconn(conn)


@contextmanager
def transaction():
    """Context manager that borrows a connection, yields a cursor, and auto-commits/rollbacks.

    Usage:
        with transaction() as cur:
            cur.execute("INSERT INTO ...")
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_connection(conn)
