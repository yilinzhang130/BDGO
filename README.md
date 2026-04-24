# BD Go — CRM Dashboard

Biotech BD intelligence platform. FastAPI backend + Next.js frontend, deployed behind Vercel → uvicorn on a VM.

## Stack

- **Backend** (`api/`): FastAPI, PostgreSQL, MiniMax LLM (Anthropic-compat API).
  Auth/sessions/credits DB is separate from the CRM DB; see [docs/review-findings.md](docs/review-findings.md) for module layout.
- **Frontend** (`frontend/`): Next.js 16 App Router, React 19, Recharts.
- **Data**: four master tables live in PostgreSQL (`公司` / `资产` / `临床` / `交易`). Read path is `api/crm_store.py` → `~/.openclaw/workspace/scripts/crm_db.py`. A local read-only SQLite snapshot lives in `workspace/crm-database/crm.db`.

## Local dev

```bash
# Backend
cp .env.example .env   # fill JWT_SECRET + MINIMAX_API_KEY at minimum
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload          # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

The API runs without `DATABASE_URL` (dev mode, random JWT on restart). Set it to enable real auth + chat persistence.

## Tests / lint

```bash
# Backend — unit tests (fast, no DB required)
cd api && pytest -q && ruff check .

# Backend — integration tests (optional; requires a writable Postgres)
TEST_DATABASE_URL=postgresql://user@localhost/bdgo_test pytest -q

# Frontend
cd frontend && npm run lint && npx tsc --noEmit
```

Integration tests in `api/tests/integration/` silently skip when `TEST_DATABASE_URL` is unset. CI provisions a Postgres service container and sets it automatically — see [docs/adr/0005-integration-test-postgres.md](docs/adr/0005-integration-test-postgres.md).

## Env vars

See [.env.example](.env.example) for the full list with inline docs. Most-needed for local dev:

| Var | Why |
|-----|-----|
| `DATABASE_URL` | Auth/sessions Postgres (skip for CRM-only dev) |
| `JWT_SECRET` | Required in production; random dev fallback |
| `MINIMAX_API_KEY` or `MINIMAX_KEYS` | All LLM features |
| `TAVILY_API_KEY` | Web-search in reports / quick-search |
| `ADMIN_SECRET` | `X-Admin-Key` header for admin CLI endpoints |
| `CRM_PG_DSN` | CRM Postgres (defaults to `dbname=bdgo`) |

Full list in [api/config.py](api/config.py).

## Reference

- **Deploy**: [DEPLOY.md](DEPLOY.md) — VM / systemd / Vercel pipeline
- **Review findings** (structure / perf / maintainability / api-design): [docs/review-findings.md](docs/review-findings.md)
- **TODO** (feature backlog): [TODO.md](TODO.md)
