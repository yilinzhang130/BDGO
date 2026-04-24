# Tests

Layout mirrors `api/` so finding a test for a source module is a predictable
path translation — `api/services/crm/list_view.py` ↔
`api/tests/unit/services/crm/test_list_view.py`.

## Three tiers

```
tests/
├── conftest.py          # shared fixtures (fake users, JWT tokens, stubbed
│                        # external deps like crm_match / crm_db — see
│                        # inline notes for why the stubs are needed)
├── unit/                # pure logic + mocked-DB tests; no network, no
│   │                    # Postgres, runs in < 3s for the whole tree
│   ├── test_crm_store.py          ← api/crm_store.py
│   ├── test_auth_helpers.py       ← api/auth.py
│   ├── test_credits.py            ← api/credits.py
│   ├── test_field_policy.py       ← api/field_policy.py
│   ├── test_api_keys.py           ← api/api_keys.py
│   ├── test_tool_registry.py      ← api/routers/chat/tools/registry.py
│   ├── test_request_id.py         ← api/request_id.py
│   └── services/
│       ├── crm/
│       │   ├── test_list_view.py  ← api/services/crm/list_view.py
│       │   └── test_companies.py  ← api/services/crm/companies.py
│       └── enrich/
│           └── test_runner.py     ← api/services/enrich/runner.py
│
├── integration/         # real HTTP + real Postgres (gated on TEST_DATABASE_URL;
│                        # see docs/adr/0005-integration-test-postgres.md)
│
└── security/            # cross-cutting permission / boundary checks
    ├── test_permissions.py
    └── test_public_api_boundary.py
```

## When to write what

- **Unit**: pure functions and service-layer logic with mocked I/O. Most
  new business logic lands here. Fast, deterministic, local-dev-friendly.
- **Integration**: the wiring a unit test can't see — real SQL, real
  auth flow, real FastAPI dispatch. Slow (needs Postgres), opt-in via
  `TEST_DATABASE_URL`.
- **Security**: regressions of the auth/field-visibility boundary —
  "token=garbage → 401", "external user → /admin → 403", etc. These
  are written to stay green even as the implementations behind them
  change.

## Patterns worth imitating

**Import inside the test, not at module top.** `from services.crm.list_view
import list_table_view` at the function scope means conftest's stubs
(crm_db, crm_match) get installed before the app code loads. Top-level
imports break when pytest collects tests in unusual orders.

**Mock at the call site, not at the symbol.** `patch("services.crm.
companies.query_one")` — patch where the service looks the name up,
not where it's defined. This is why the S-004 router-refactor silently
broke PR #19's tests: those patched `routers.buyers.paginate`, which
had been removed as an unused import. Patch the actual call target.

**One assertion per concept.** Each test name should map to one
invariant; if you need three assertions to verify it, that's the
invariant. Don't stack unrelated invariants into one test — a failure
message should tell you which invariant broke.
