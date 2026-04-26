"""
auth_db.py — Postgres connection pool for the auth / users / sessions database.

Owns: users, sessions, messages, context_entities, report_history, credits,
invite_codes. CRM data lives in ``crm_store`` (different database).

Uses psycopg2 ThreadedConnectionPool for efficient connection reuse.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

import config
import psycopg2
import psycopg2.extras
import psycopg2.pool

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
    last_login TIMESTAMP DEFAULT NOW(),
    company VARCHAR(255),
    title VARCHAR(255),
    phone VARCHAR(50),
    bio TEXT,
    preferences_json TEXT,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    google_sub VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_google_sub ON users (google_sub)
    WHERE google_sub IS NOT NULL;

CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(12) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    -- Context compaction cache: brief summary of messages with created_at <= brief_ts
    brief TEXT,
    brief_ts TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(12) PRIMARY KEY,
    session_id VARCHAR(12) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tools_json TEXT,
    attachments_json TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_session_created ON messages(session_id, created_at DESC);

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
    created_at TIMESTAMP DEFAULT NOW(),
    -- State machine + retry support. Without these, in-flight tasks are
    -- invisible to any worker other than the one that spawned them.
    params_json TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    error TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    CONSTRAINT uq_report_history_task_id UNIQUE (task_id)
);
CREATE INDEX IF NOT EXISTS idx_report_history_user ON report_history(user_id);
CREATE INDEX IF NOT EXISTS idx_report_history_status_created
    ON report_history(status, created_at DESC);

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

-- API keys for external consumers (see api_keys.py + migration 442676e3bb8e)
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
CREATE INDEX IF NOT EXISTS idx_api_keys_user_active
    ON api_keys(user_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_api_keys_hash_active
    ON api_keys(key_hash) WHERE revoked_at IS NULL;

-- API request logs (per-key usage ledger; see api_request_log.py + migration a7eceb4cad87)
CREATE TABLE IF NOT EXISTS api_request_logs (
    id BIGSERIAL PRIMARY KEY,
    key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(255) NOT NULL,
    status INTEGER NOT NULL,
    latency_ms INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_request_logs_key_created
    ON api_request_logs(key_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_request_logs_user_created
    ON api_request_logs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS inbox_messages (
    id BIGSERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL,          -- 'data_report' | 'feedback'
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    user_email TEXT,
    user_name TEXT,
    entity_type VARCHAR(50),            -- '公司' | '资产' | '临床' | '交易' etc.
    entity_key TEXT,                    -- entity name / id
    entity_url TEXT,                    -- deep-link back to the entity
    message TEXT NOT NULL,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_inbox_messages_created
    ON inbox_messages(created_at DESC);

-- BD outreach event log (per-user). Append-only event stream — each row is
-- one outreach action / status update at a point in time. To "update" a
-- thread, insert a new event with the new status, not an UPDATE. This
-- keeps a faithful timeline + simpler logic. See services/reports/
-- outreach_log.py and outreach_list.py for the chat-facing /log + /outreach
-- commands.
CREATE TABLE IF NOT EXISTS outreach_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(12),                     -- optional link to chat session
    to_company VARCHAR(255) NOT NULL,
    to_contact VARCHAR(255),                    -- 'Sarah Chen, Head of External Innovation'
    purpose VARCHAR(40) NOT NULL,               -- cold_outreach / cda_followup / data_room / ts_send / meeting / follow_up
    channel VARCHAR(20) NOT NULL DEFAULT 'email',  -- email / linkedin / phone / in_person / other
    status VARCHAR(30) NOT NULL DEFAULT 'sent',    -- sent / replied / meeting / cda_signed / ts_signed / passed / dead
    asset_context VARCHAR(255),                 -- 'PEG-001 — NSCLC'
    perspective VARCHAR(10),                    -- 'buyer' / 'seller' (whose POV)
    subject TEXT,                               -- email subject if applicable
    notes TEXT,                                 -- free-form notes
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_outreach_user_company
    ON outreach_log(user_id, to_company);
CREATE INDEX IF NOT EXISTS idx_outreach_user_status
    ON outreach_log(user_id, status);
CREATE INDEX IF NOT EXISTS idx_outreach_user_created
    ON outreach_log(user_id, created_at DESC);

-- plan_templates: user-saved plan templates (X-18, 2026-04-26)
-- Users can save any planner-generated plan as a named template for instant
-- reuse (bypasses the planner LLM call). Built-in templates are Python
-- constants in plan_templates.py; this table stores user-created custom ones.
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
"""

# ---------------------------------------------------------------------------
# NOTE on schema management
# ---------------------------------------------------------------------------
# The DDL above is the bootstrap for fresh databases — every statement is
# idempotent (``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT
# EXISTS``). Incremental schema changes live in Alembic revisions under
# ``migrations/versions/``; the Dockerfile runs ``alembic upgrade head``
# before uvicorn so existing DBs catch up on every deploy.
#
# When adding a column to an existing table, also inline it into the
# ``CREATE TABLE`` above so fresh databases get it on first boot —
# otherwise the bootstrap + migrations would diverge for new deploys.
# See migrations/README.md.

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
            raise RuntimeError("DATABASE_URL is not set — cannot connect to auth database")

        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=config.AUTH_DB_POOL_MIN,
            maxconn=config.AUTH_DB_POOL_MAX,
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
