# Alembic migrations — auth DB

Managed schema for the Postgres auth / sessions database (everything in
`auth_db.py:_SCHEMA_SQL`). The CRM database lives elsewhere and is NOT
managed by Alembic.

## First rollout to an existing prod DB

The DB already has the full schema because `auth_db.py` auto-runs
`CREATE TABLE IF NOT EXISTS` on startup. Before Alembic takes over,
tell it the DB is already caught up:

```
cd api
alembic stamp head
```

That writes an `alembic_version` row without running any upgrade DDL.

## Day-to-day

### Adding a new column / table

1. Write the migration by hand (autogenerate is OFF — we have no ORM
   model to diff against):
   ```
   alembic revision -m "add X to users"
   ```
   Edit the generated file's `upgrade()` / `downgrade()` with
   `op.execute("ALTER TABLE ...")`.

2. Apply locally:
   ```
   alembic upgrade head
   ```

3. Commit the migration file. Deploy runs `alembic upgrade head` on
   startup (see scripts/deploy.sh).

### Inspecting without touching the DB

```
alembic upgrade head --sql     # print SQL to stdout, run nothing
alembic history                # list revisions
alembic current                # which revision the DB is on
```

### Rolling back

```
alembic downgrade -1           # one revision back
alembic downgrade <revision>   # to a specific point
```

Always pair `upgrade()` with a working `downgrade()` — even "drop
column" migrations, unless the data is truly irrecoverable.

## Keeping the bootstrap in sync

The `_SCHEMA_SQL` in `auth_db.py` is the bootstrap for fresh databases —
it runs once on startup if `alembic_version` isn't populated yet. When
you add a column via an Alembic migration, also inline that column into
the matching `CREATE TABLE` in `_SCHEMA_SQL`. Otherwise:

- Fresh deploy → bootstrap creates the table without the column →
  migration runs next, idempotently adds it. Works, but the bootstrap
  no longer tells you the current schema truthfully.
- New contributor reads `_SCHEMA_SQL` and thinks the column doesn't
  exist, because it isn't there.

The `DO $$ ALTER TABLE … EXCEPTION WHEN duplicate_column $$` pattern
that used to live in `_SCHEMA_SQL` was retired in M-011 — those
columns are now either inlined into their `CREATE TABLE` above, or
added by a numbered migration here (or both). Don't bring them back.

## Why no autogenerate?

The app uses raw psycopg2 cursors, not SQLAlchemy ORM. Without a
declarative model layer, autogenerate would see an empty `MetaData()`
and generate drop-everything migrations. Hand-writing DDL is the
correct path here until we add an ORM.
