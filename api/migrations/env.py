"""Alembic runtime environment.

Reads the database URL straight from ``$DATABASE_URL`` rather than
through the app's ``config`` module — importing ``config`` enforces
JWT_SECRET and other runtime invariants that are irrelevant to
migrations, and we want ``alembic upgrade head`` to work during CI or
container image builds where those aren't set.

We intentionally don't wire up ``target_metadata`` to a SQLAlchemy
declarative model — the codebase uses raw psycopg2 cursors and has no
ORM classes. Autogenerate is therefore disabled; migrations are
hand-written ``op.execute('ALTER TABLE ...')`` style.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

_db_url = os.environ.get("DATABASE_URL")
if not _db_url:
    raise RuntimeError(
        "DATABASE_URL is not set — Alembic cannot connect to the auth DB. "
        "Export DATABASE_URL before running migrations."
    )
alembic_config.set_main_option("sqlalchemy.url", _db_url)

# No declarative metadata — migrations are written by hand.
target_metadata = None


def run_migrations_offline() -> None:
    """Generate SQL to stdout without connecting to the database.

    Useful for inspecting what ``upgrade`` would run in prod.
    """
    context.configure(
        url=alembic_config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the DB and apply migrations."""
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
