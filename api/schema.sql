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
