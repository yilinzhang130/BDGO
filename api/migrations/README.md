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

## Why no autogenerate?

The app uses raw psycopg2 cursors, not SQLAlchemy ORM. Without a
declarative model layer, autogenerate would see an empty `MetaData()`
and generate drop-everything migrations. Hand-writing DDL is the
correct path here until we add an ORM.
