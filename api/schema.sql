-- Auth database schema (Postgres)
-- Run against the auth database specified by DATABASE_URL.

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    hashed_password TEXT,          -- NULL for OAuth-only users
    provider VARCHAR(50) NOT NULL DEFAULT 'email',  -- 'email' | 'google'
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- Session / message / entity persistence
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(12) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
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
