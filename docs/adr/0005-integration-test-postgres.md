# ADR 0005: Integration tests run against a real Postgres provided via env var

- **Status**: Accepted
- **Date**: 2026-04-24

## Context

Before this ADR, `api/tests/` had only unit tests with mocked `auth_db.transaction()`. `tests/integration/` existed with only `__init__.py` (M-012). Two real-world bugs it would have caught:

- S-004 regression: test fixtures monkeypatched `routers.buyers.paginate`, which disappeared after ruff trimmed the import. Unit-level mocking didn't catch the live wiring break.
- PR #19's new integration tests also used the stale patch path (fixed in PR #23).

We need tests that exercise the real wiring: `auth_db` pool, real SQL, the actual FastAPI dispatch.

Constraints:
- CI (GitHub Actions) runs on ephemeral runners — fine, we can spin up Postgres as a service container.
- Local dev shouldn't be forced to install Postgres just to run `pytest`. Unit tests must stay fast and DB-free.
- We already use Postgres in prod and locally (per `docker-compose.yml`, `DEPLOY.md`). Using real Postgres in tests mirrors reality.

## Decision

Integration tests live in `api/tests/integration/` and require a real Postgres URL via the `TEST_DATABASE_URL` env var:

- **If `TEST_DATABASE_URL` is unset, all integration tests are skipped** (the directory's `conftest.py` calls `pytest.skip(allow_module_level=True)`). Unit tests still run, `pytest` exits 0, no friction.
- **If set**, tests run against that DB. The fixture calls `auth_db._SCHEMA_SQL` (already idempotent via `CREATE TABLE IF NOT EXISTS`) at session start; per-test cleanup is each test's responsibility (MVP — revisit with transaction rollback if test count grows).

In CI:
- A new `pytest` job in `.github/workflows/checks.yml` spins up `postgres:16` as a service container and exports `TEST_DATABASE_URL` before running `pytest`.
- Unit tests run in the same job (fast first, integration follows).

Locally:
- Developers who want to run integration tests set `TEST_DATABASE_URL=postgresql://user@localhost/bdgo_test` and run `pytest`. Otherwise integration tests silently skip, unit tests pass.

## Consequences

- **Good**: Tests exercise real SQL — regressions like S-004's import disappearance or schema drift surface at integration-test time, not in production.
- **Good**: CI is self-contained (no external DB dependency, no shared state).
- **Good**: Local dev stays fast by default; opt-in integration testing when you need it.
- **Good**: Documents the test-DB contract in one place (this ADR), so new integration tests know the fixture shape.
- **Bad**: Per-test cleanup responsibility falls on the test author. Easy to miss and leaks between tests if schema fills with fixtures. Revisit with transaction-rollback isolation (or `testcontainers-python` with fresh DB per test) when test count crosses ~20.
- **Bad**: CI runtime grows by ~15s (postgres startup + migration). Acceptable at current scale.

## Alternatives considered

- **Mock `auth_db.transaction()` at a lower level**: rejected — that's what unit tests already do, and it's what let S-004 regress. The whole point of integration tests is to NOT mock the DB.
- **`pytest-postgresql` / `testing.postgresql`**: rejected — needs system-level Postgres binary on the runner; more brittle than GH Actions' service container.
- **`testcontainers-python`**: viable; adds a Docker dependency. Overkill for MVP. Revisit when we need fresh-DB-per-test isolation.
- **Shared Postgres DB for CI jobs**: rejected — order-dependent failures and concurrent-PR collisions. Ephemeral-per-job is cleaner.
