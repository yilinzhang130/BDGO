"""
Fixtures for real-DB integration tests.

Contract (see docs/adr/0005-integration-test-postgres.md):
    TEST_DATABASE_URL env var must point at a writable Postgres for any
    test that uses the ``integration_client`` fixture. Without it, those
    tests individually skip; other tests in this directory that stick
    with mocks (e.g. the existing api_keys router tests) keep working
    unchanged — the skip is scoped to the fixture, not the whole module.

In CI, the `pytest` job in .github/workflows/checks.yml provisions a
fresh postgres service container per run and sets TEST_DATABASE_URL
automatically.

Locally:
    export TEST_DATABASE_URL=postgresql://user@localhost/bdgo_test
    pytest api/tests/integration/
"""

from __future__ import annotations

import os

import pytest


def _require_test_db() -> str:
    """Return TEST_DATABASE_URL or skip the test.

    Both the env var AND the cached ``config.DATABASE_URL`` module
    attribute must be updated: the parent unit-test conftest sets
    DATABASE_URL="" before any test collection, and by the time unit
    tests import ``auth``/``config`` that empty string has been frozen
    as ``config.DATABASE_URL``. Changing just the env var later is a
    no-op because ``auth_db._get_pool()`` reads ``config.DATABASE_URL``
    (not ``os.environ``).
    """
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL not set — real-DB integration test skipped. "
            "See docs/adr/0005-integration-test-postgres.md."
        )
    os.environ["DATABASE_URL"] = url
    # Override the already-cached module constant so any
    # ``config.DATABASE_URL`` read in auth_db / main sees the test DB.
    import config

    config.DATABASE_URL = url
    return url


@pytest.fixture
def integration_client():
    """Real TestClient, real auth, real DB. No dependency overrides.

    Skips the test if TEST_DATABASE_URL isn't set. Schema creation is
    handled by ``auth_db._get_pool()`` on first pool use — it runs
    ``_SCHEMA_SQL`` exactly once per process, so we don't duplicate
    that here (running it twice hits non-idempotent ADD CONSTRAINT
    blocks that only catch ``duplicate_object`` not ``duplicate_table``).

    Contrast with the unit-test ``client`` fixture in the parent
    conftest, which stubs ``get_current_user`` via
    ``app.dependency_overrides`` so routers are exercised without a
    live DB.

    Rate-limit reset: ``routers.auth._rl_store`` is a process-local
    sliding-window counter (10 attempts / 60 s / IP). Every integration
    test calls _register_user from the same TestClient IP, so without
    a per-test reset the 5th sessions test trips a documented 429
    flake on CI (see #X-67). We clear the store at fixture entry —
    cheap, surgical, and doesn't touch production code.
    """
    _require_test_db()

    # Reset auth rate-limit store before each integration test so
    # cumulative register/login attempts across tests don't trip the
    # 10-per-minute per-IP cap (TestClient always uses one IP).
    from routers import auth as auth_router

    with auth_router._rl_lock:
        auth_router._rl_store.clear()

    # Touch the pool once — triggers _SCHEMA_SQL on a fresh DB.
    import auth_db

    with auth_db.transaction() as cur:
        cur.execute("SELECT 1")

    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    # Make sure no unit-test overrides leaked into the app instance.
    fastapi_app.dependency_overrides.clear()

    with TestClient(fastapi_app, raise_server_exceptions=False) as c:
        yield c

    fastapi_app.dependency_overrides.clear()
