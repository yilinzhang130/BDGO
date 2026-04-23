# ADR 0002: Two-Postgres split — auth DB separate from CRM DB

- **Status**: Accepted
- **Date**: 2026-04-24 (retrospective)

## Context

The app serves two very different data shapes:

1. **Auth / sessions / credits / report history**: write-heavy, user-scoped, strict consistency (no lost billing rows).
2. **CRM data** (公司 / 资产 / 临床 / 交易 / IP / MNC画像): read-heavy, ETL'd from external biotech sources via `workspace/scripts/*`, refreshed nightly by analysts.

They have different backup cadences, different schema-change frequencies, different sensitivity profiles (auth contains PII, CRM is business data), and different scaling needs (auth is hot + small, CRM is warm + getting large).

A local-dev CRM copy exists as `workspace/crm-database/crm.db` — a read-only SQLite snapshot of production Postgres, used so developers don't need a local Postgres to work on CRM views.

## Decision

Run two Postgres databases:

- `bdgo` (accessed via `auth_db.py`): users / sessions / messages / context_entities / report_history / credits / usage_logs / invite_codes / api_keys / api_request_logs.
- The CRM database (accessed via `crm_store.py` → `workspace/scripts/crm_db.py`): the four business tables plus IP / MNC画像 / LOE / guidelines.

Never cross-import: `auth_db` and `crm_store` never touch each other's tables. `crm_store` supports SQLite locally and Postgres in prod via the same query interface.

## Consequences

- **Good**: Backup and restore are independent — an auth-side incident can't lose CRM work and vice versa. Schema migrations on one don't coordinate with the other.
- **Good**: The read-only SQLite snapshot lets new developers run the frontend and read-path end-to-end without provisioning Postgres.
- **Good**: Blast radius of a SQL bug is contained: a bad CRM query can't corrupt auth.
- **Bad**: No FK possible between users and CRM rows (e.g. "who wrote this asset's note"). We live with it — the surrogate is the `watchlist` / `inbox_messages` tables in auth DB which reference CRM rows by string key.
- **Bad**: Duplicates the connection-pool boilerplate (`ThreadedConnectionPool` lives in both files with independent sizing).

## Alternatives considered

- **Single Postgres with schema separation (`auth.users`, `crm.公司`)**: rejected because migrations become coupled and we'd lose the SQLite-snapshot story for local dev.
- **CRM-only SQLite (no Postgres in prod)**: rejected — the nightly ETL from `workspace/scripts/` expects a multi-writer backend. SQLite can't serve concurrent writes.
