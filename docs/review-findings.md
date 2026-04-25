# Review Findings — BDGO

四个 review skill 的**共用台账**，是本仓库 Schema / 状态词汇 / Severity 口径的单一真源。Skill 在审查前读此文件，跳过已标 `done` / `wontfix` / `false-positive` 的条目。

---

## 使用方式

1. Skill 跑完会把新 finding 追加到 `Open` 节。
2. 你人工判断每条 finding 的真伪和优先级。
3. 状态流转：
   - `open` → `in-progress`（开始修）
   - `in-progress` → `done`（修完合并）
   - `open` → `wontfix`（确认不修，留原因）
   - `open` → `false-positive`（LLM 误报，删也行但留着教训更好）
4. 修完的 finding **保留在文件里**（移到 `Done` 节），不要删 —— 这是你的"审查记忆"。

---

## Schema

| 列 | 说明 |
|---|---|
| **ID** | 形如 `S-001` (structure) / `P-001` (performance) / `M-001` (maintainability) / `A-001` (api-design)，递增不复用 |
| **Date** | 首次发现日期 (YYYY-MM-DD) |
| **Scope** | `structure` / `performance` / `maintainability` / `api-design` |
| **Rubric** | 对应 skill 的 rubric 编号 (A1 / B3 / ...) |
| **Severity** | `critical` / `high` / `medium` / `low` |
| **Status** | `open` / `in-progress` / `done` / `wontfix` / `false-positive` |
| **Effort** | `S` (<1h) / `M` (半天~1天) / `L` (>1天) |
| **BreaksClient** | 仅 api-design：`yes` / `no` / `n/a` (修复会不会影响已部署客户端) |
| **File:Line** | 主要证据位置 |
| **Summary** | 一句话描述 |
| **Notes** | 状态变更原因、关联 PR / issue、修复思路 |

---

## Severity 统一口径

- **critical**: 财务 / 安全 / 数据损坏 / 上线即炸 → 立即处理
- **high**: 会在目标负载下出问题 / 误导当前开发 / 契约硬错
- **medium**: 增加成本、风险可控，但该修
- **low**: 卫生问题、微优化

---

## Open

<!-- Skill 追加区。示例：
| S-001 | 2026-04-23 | structure | A3 | high | open | M | n/a | api/crm_db.py:42 | crm_db 与 crm_store 职责重叠 | 两处都定义 get_company，签名不同语义相同 |
-->

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------|
| S-001 | 2026-04-24 | structure | A3/E2 | high | open | M | n/a | api/crm_db.py vs workspace/scripts/crm_db.py | `crm_db.py` exists in two places as a near-duplicate (34963 vs 32411 bytes, diverged CHANGELOGs); api version is loaded when sys.path hits api first | `crm_store.py:29` uses `sys.path.insert(0, scripts_dir)` to force the scripts copy. Any other `import crm_db` gets the api copy. Delete api/crm_db.py or make it a pure re-export |
| S-002 | 2026-04-24 | structure | A2/A4 | high | open | L | n/a | api/routers/*.py (20 files) | No service layer for CRUD — routers call `crm_store` SQL helpers and `database.transaction` directly (67 raw SQL hits across 20 router files) | Service layer exists only for reports (`services/reports/`). CRUD routers (companies/assets/clinical/deals/ip/buyers/stats/catalysts/watchlist/write/search/inbox/sessions/tasks/admin/auth/upload/aidd_sso) bypass it entirely. Extract per-domain service modules |
| S-003 | 2026-04-24 | structure | C2 | high | open | M | n/a | api/database.py, api/db.py, api/crm_db.py, api/crm_store.py | Four DB-ish modules with near-identical names and overlapping scope. Reader cannot distinguish roles at a glance | `database.py`=auth/users PG pool; `db.py`=deprecated shim (zero callers); `crm_db.py`=CSV/SQLite/PG abstraction (+duplicate in workspace/scripts); `crm_store.py`=crm_db wrapper. Rename to `auth_db.py` / `crm_low.py` / `crm_repo.py` (or similar) and delete `db.py` |
| S-004 | 2026-04-24 | structure | A1/E1 | high | open | M | n/a | api/routers/{assets,buyers,clinical,companies,deals,ip}.py | Same list-endpoint pattern duplicated 6× — `allowed_sorts={...}` + LIKE filter building + `paginate(...)` + `strip_hidden(...)` | Extract a `list_table_view(table, filters, sort_whitelist, user)` helper. Sort whitelist is per-table business rule — belongs in a service, not the router |
| S-005 | 2026-04-24 | structure | A1/A4 | high | open | L | n/a | api/routers/tasks.py | Router contains MiniMax HTTP calls, subprocess invocation, prompt strings, CRM column allowlists, JSON parsing, and direct `update_row` writes | 340 lines of business logic in a router. Extract to `services/enrich/` (task runner + minimax client + column policy) |
| S-006 | 2026-04-24 | structure | B1 | medium | open | S | n/a | api/routers/credits.py:9 | `routers/credits.py` imports private `_check_admin` from `routers/admin.py` (router→router, private function) | Lift `_check_admin` to a dependency module (e.g. `auth.py` or `field_policy.py`) or make it public |
| S-007 | 2026-04-24 | structure | B1 | medium | open | S | n/a | api/routers/chat/tools/crm.py:229 | `routers/chat/tools/crm.py` imports private `_load_report_data` from `routers/conference.py` inside a function body | Same fix as S-006 — extract conference data loader to a service module both routers can share |
| S-008 | 2026-04-24 | structure | D4 | medium | open | M | n/a | api/services/helpers/ | `helpers/` is a junk drawer spanning 5+ domains: DB lookup (crm_lookup), file building (docx_builder, pptx_builder, rnpv_excel=2489 lines), external APIs (pubmed, search), LLM (llm), data (enums, resolve, qc, text) | Split by domain: `services/document/` (docx/pptx/xlsx), `services/external/` (pubmed/search/llm), `services/crm/` (lookup/resolve) |
| S-009 | 2026-04-24 | structure | D2 | medium | open | S | n/a | api/conferences/ | Directory named like a subpackage but contains only `AACR-2026/report_data.json` — no Python code | Either rename to `api/data/conferences/` to reflect its role as a data store, or move JSON into `workspace/` per the output-path convention. Conference logic actually lives in `routers/conference.py` |
| S-010 | 2026-04-24 | structure | C4 | medium | open | S | n/a | frontend/src/lib/utils.ts | `utils.ts` mixes 5 unrelated responsibilities: SSR guard, fire-and-forget promise helper, number formatting, 4 badge-class helpers, safe JSON parse, chart color palette | Split into `browser.ts` (isBrowser, bg), `format.ts` (formatNumber, parseNum, safeJsonParse), `badges.ts` (4 badge helpers), `chart-colors.ts` (COLORS). Currently imported by auth/reports/sessions |
| S-011 | 2026-04-24 | structure | F1/F2 | medium | open | L | n/a | api/tests/ | Test tree does not mirror source. Only 4 unit tests (auth_helpers, credits, field_policy, tool_registry) + 1 security test. Zero tests for `services/` (11 report services), `routers/` (24 routers), or `crm_store.py`. `tests/integration/` empty | Mirror source layout: `tests/unit/services/reports/test_<each>.py`, `tests/unit/routers/test_<each>.py`, `tests/integration/test_crud_flow.py` |
| S-012 | 2026-04-24 | structure | A1 | low | open | S | n/a | api/db.py | Deprecation shim with zero callers (no file imports `from db import` or `import db`) | Delete the file; the shim has served its purpose |
| S-013 | 2026-04-24 | structure | C4 | low | open | S | n/a | frontend/src/components/charts/ | Empty directory | Delete it, or add a README noting it's reserved |
| P-001 | 2026-04-24 | performance | B1/B2 | critical | open | M | n/a | api/routers/chat/llm_stream.py:42-52, api/routers/chat/system_prompt.py (107L) | No prompt caching + no result caching on the MiniMax path. SYSTEM_PROMPT (~107 lines) + TOOLS array are re-tokenized and charged on every chat turn; `grep cache_control` across api/ → 0 hits. For a 20-concurrent deployment with 5–8 turns per session, the stable prefix (system + tools) is paid N×T times per day | Add `cache_control: {type: "ephemeral"}` to SYSTEM_PROMPT and TOOLS in `_build_request`; inspect `cache_read_input_tokens` in message_start to verify hit rate. Separately, consider a short-TTL response cache keyed on (model, prompt_hash) for the planner LLM in particular — planner runs on every "should_plan" user turn |
| P-002 | 2026-04-24 | performance | B9/E2 | high | open | M | n/a | api/services/external/llm.py:22-71, api/services/report_builder.py:96-105 | Report path bypasses `llm_pool`. `_call_one_sync` uses `model.api_key` (single static key) and creates a fresh `httpx.Client` per call. Every chapter in `buyer_profile` (8 calls), `dd_checklist` (3 batches), `target_radar`, `commercial_assessment`, etc. goes through the single key — multi-key fair scheduling isn't applied, and TCP+TLS handshake is paid per call. Under concurrent report load, one MiniMax plan saturates while the others sit idle | Route sync LLM calls through `llm_pool.acquire_for` (add a sync variant or wrap via `asyncio.run_coroutine_threadsafe`). Reuse a module-level `httpx.Client(limits=...)` instead of constructing one per call |
| P-003 | 2026-04-24 | performance | B3/B6 | high | open | M | n/a | api/services/reports/buyer_profile.py:395-433 | 8 buyer-profile chapters run fully sequentially via `ctx.llm` → ~2 min wall-clock. Each chapter's `running_summary` only uses the last 1000 chars of prior output, so the true dependency chain is 1 → (2..8 parallel). `dd_checklist.py:494` already demonstrates the 3-batch ThreadPoolExecutor pattern. No streaming either — user sees only log lines in `/status/{task_id}` until all 8 complete | Refactor chapters 2–8 into 2–3 parallel batches (matching `dd_checklist`). Bonus: stream partial markdown to the client as each batch returns |
| P-004 | 2026-04-24 | performance | G1/G2 | high | open | S | n/a | api/routers/chat/streaming.py:235-242, api/main.py:160-176 | No LLM-call observability. `usage_accum` is committed to `usage_logs` only at chat-turn completion (for billing); no latency histogram, no per-model token rate, no cache-hit ratio. `main.py:log_api_key_requests` records `latency_ms` only for X-API-Key traffic — JWT (the 99% path) gets none. Without this, perf review is guesswork and MiniMax quota runway is unknowable | Emit a structured log line per LLM call with `{model_id, key_suffix, input_tokens, output_tokens, cache_read_tokens, latency_ms, status}` from `call_minimax_stream` + `_call_one_sync`. That alone unlocks grep-based p95 analysis; promote to prometheus later |
| P-005 | 2026-04-24 | performance | A5/H2 | high | done | S | n/a | api/routers/reports.py:107-111 | Unbounded `threading.Thread(daemon=True)` spawn for async reports. A burst of 20 users each kicking off a deal_teaser / dd_checklist immediately spawns 20 threads, each holding an auth-DB connection + one-or-more MiniMax keys + running rnpv_excel builders that can allocate tens of MB. No semaphore, no queue. `daemon=True` also means abrupt shutdown → `report_history` rows stuck at `running` forever | PR #67: module-level `ThreadPoolExecutor(max_workers=REPORT_MAX_WORKERS, thread_name_prefix="report")` replaces per-request `Thread(daemon=True)`. `REPORT_MAX_WORKERS` env var (default 6) added to config.py. Lifespan shutdown reclaims running tasks then calls `shutdown_executor(wait=False, cancel_futures=True)`. |
| P-006 | 2026-04-24 | performance | C3 | medium | open | S | n/a | api/auth_db.py:73, api/routers/chat/chat_store.py:63-69 | `load_history` runs `WHERE session_id=%s ORDER BY created_at DESC LIMIT 100` on every chat turn, but `messages` only has `idx_messages_session(session_id)` — not the composite `(session_id, created_at DESC)` this query wants. With 1000+ messages in a session, PG fetches all session rows then sorts in memory | New Alembic migration: `CREATE INDEX idx_messages_session_created ON messages(session_id, created_at DESC);` and drop the single-column one |
| P-007 | 2026-04-24 | performance | E2 | medium | open | S | n/a | api/services/external/pubmed.py:55/90/112/189, api/services/external/search.py:98 | `httpx.Client` constructed per call in Tavily (`search_web`) and PubMed (`search_articles`, `get_article_metadata`, `fetch_single`). Both are hot paths — Tavily is called from the chat tool loop via `asyncio.to_thread` and from every buyer-profile / deal-evaluator report (3–6 queries per run). Each call pays a fresh TCP+TLS handshake | Hoist a module-level `httpx.Client(timeout=..., limits=httpx.Limits(max_keepalive_connections=10))` and reuse. Same pattern as `llm_pool._http_client` |
| P-008 | 2026-04-24 | performance | F1/F2 | medium | open | L | n/a | frontend/src/app/**/page.tsx (26/30 pages `'use client'`) | Almost the entire app is client-rendered: `companies`, `assets`, `clinical`, `deals`, `ip`, `buyers`, `catalysts`, `conference`, `dashboard`, `chat`, `reports`, `watchlist`, `admin`, etc. Every page pays the TTI waterfall: HTML shell → JS bundle → `useEffect` fires → 1..5 API calls. App Router Server Components + streaming would eliminate the JS-wait-then-fetch gap for data-heavy list/detail pages | Convert CRM list pages (`/companies`, `/assets`, `/clinical`, `/deals`, `/buyers`, `/ip`) to Server Components with server-side data fetch + streaming. Keep `EditableField` + `WatchlistButton` as client islands. Chat/upload stay fully client-side |
| P-009 | 2026-04-24 | performance | B4 | medium | done | S | n/a | api/routers/chat/llm_stream.py:241-248, api/services/external/llm.py:54-64 | MiniMax 529 retry uses fixed `2**attempt` (1s, 2s, 4s) with no jitter in either the streaming or sync path. Under correlated bursts (many users hit 529 together because one MiniMax plan saturates), retries synchronise and amplify load on the provider → longer outage | PR #67: both retry loops now use `wait = (2**attempt) * (0.5 + random.random())` — uniform jitter in [0.5×, 1.5×] of base delay. |
| P-010 | 2026-04-24 | performance | D3 | medium | open | S | n/a | api/routers/conference.py:79-314 | `/api/conference/sessions`, `/{session_id}/stats`, `/{session_id}/companies`, `/{session_id}/abstracts` all serve pre-processed JSON that only changes on deploy. `load_report_data` is `@lru_cache`d (good) but responses carry no `Cache-Control` or `ETag`, so browsers and the nginx reverse proxy re-fetch on every navigation. 460KB `report_data.json` is filtered-and-re-serialised on every call | Add `Cache-Control: public, max-age=300` + ETag (hash of session dir mtime) to the 4 conference endpoints |

---

## In-Progress

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------|
| S-001 | 2026-04-24 | structure | A3/E2 | high | in-progress | M | n/a | api/crm_db.py vs workspace/scripts/crm_db.py | `crm_db.py` exists in two places as a near-duplicate (34963 vs 32411 bytes, diverged CHANGELOGs); api version is loaded when sys.path hits api first | PR #17: deleted `api/crm_db.py`; both importers (`crm_store.py`, `services/reports/buyer_profile.py`) already prepend `scripts_dir` to sys.path |
| S-012 | 2026-04-24 | structure | A1 | low | in-progress | S | n/a | api/db.py | Deprecation shim with zero callers (no file imports `from db import` or `import db`) | PR #17: deleted — grep confirmed zero static or dynamic importers |
| S-003 | 2026-04-24 | structure | C2 | high | in-progress | M | n/a | api/database.py → api/auth_db.py | Four DB-ish modules with near-identical names. Already removed `db.py` (S-012) and api-side `crm_db.py` (S-001) | PR #17: renamed `database.py` → `auth_db.py` (clearer role: auth/users PG pool). 17 files updated: 10 import sites + 6 doc/comment references + test patch target |
| S-006 | 2026-04-24 | structure | B1 | medium | in-progress | S | n/a | api/routers/credits.py:9 | `routers/credits.py` imports private `_check_admin` from `routers/admin.py` (router→router, private function) | PR #17: lifted to `auth.require_admin_header` (public). `ADMIN_SECRET` env read now lives in auth.py too. admin.py and credits.py both import from auth — no more router→router private import |
| S-007 | 2026-04-24 | structure | B1 | medium | in-progress | S | n/a | api/routers/chat/tools/crm.py:229 | `routers/chat/tools/crm.py` imports private `_load_report_data` from `routers/conference.py` inside a function body | PR #17: extracted to new `services/conference.py` (`load_report_data`, still @lru_cached). Both routers import from services — no more router→router private import, no function-body lazy import |
| S-009 | 2026-04-24 | structure | D2 | medium | in-progress | S | n/a | api/conferences/ → api/data/conferences/ | Directory named like a subpackage but contains only `AACR-2026/report_data.json` — no Python code | PR #17: moved to `api/data/conferences/`. Now unambiguously a data directory, not a Python subpackage. `CONFERENCES_DIR` default in config.py updated; env var override path unchanged |
| S-010 | 2026-04-24 | structure | C4 | medium | in-progress | S | n/a | frontend/src/lib/utils.ts | `utils.ts` mixes 5 unrelated responsibilities | PR #17: split into `browser.ts` (isBrowser, bg), `format.ts` (formatNumber, parseNum, safeJsonParse), `badges.ts` (4 phase/priority/result/status helpers), `chart-colors.ts` (COLORS). 14 importers updated across lib/ and app/ pages. Old `utils.ts` deleted |

---

## Done

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes (PR/commit) |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------------------|
| M-001 | 2026-04-24 | maintainability | E4 | high | done | L | n/a | api/{planner,llm_pool,rate_limit}.py | Critical modules had zero tests | PR #33 `test(m-001): cover planner + llm_pool + rate_limit` — 0 → 54 tests added |
| M-002 | 2026-04-24 | maintainability | H4 | high | done | M | n/a | api/schema.sql | Two sources of truth for auth schema (schema.sql vs auth_db._SCHEMA_SQL) | PR #23 (commit 656979f) `chore: delete orphaned api/schema.sql`. auth_db.py is now the only runtime truth |
| M-003 | 2026-04-24 | maintainability | A1/F4 | high | done | S | n/a | api/credits.py | Dead `credits.SCHEMA_SQL` with misleading "appended at import time" docstring | PR #21 (commit 90413a1) `refactor(credits): delete dead SCHEMA_SQL`. Dead code + misleading comments removed |
| M-005 | 2026-04-24 | maintainability | G1 | high | done | S | n/a | api/credits.py | `record_usage` swallowed DB errors silently → possible credit leak with no signal | PR #26 (commit 0523624) `feat(credits): add BILLING_LEAK signal when record_usage fails silently`. Swallow-and-continue preserved for UX; warning logged + counter for ops reconciliation |
| M-006 | 2026-04-24 | maintainability | F5 | medium | done | M | n/a | api/routers/*.py | OpenAPI `/docs` nearly empty — only 5 `response_model=` across 98 routes | PR #27 (02b8a15) + PR #40 (8ad510c). 23+ frontend-facing endpoints now declare `response_model` |
| M-007 | 2026-04-24 | maintainability | C4 | medium | done | S | n/a | api/{auth,models,main,rate_limit,...}.py | 10 `os.environ.get` calls scattered across 7+ files | PR #25 (commit b01e02e) `refactor(config): centralize 10 env-var reads into config.py`. All reads now flow through `config.py` constants |
| M-009 | 2026-04-24 | maintainability | A7 | medium | done | S | n/a | requirements.txt, package.json | 4 unused dependencies (aiofiles, respx, pytest-mock, @tanstack/react-table) | PR #24 (commit 60cb4c2) `chore(deps): drop 4 unused packages` |
| M-010 | 2026-04-24 | maintainability | A3 | medium | done | S | n/a | 15 ruff ERA001 hits | First dismissed as false-positive (all 15 were legitimate comments that ruff mistook for dead code); later rewritten to re-enable the rule in CI | PR #24 noted the FP; PR #39 (2efd06d) `cleanup(m-010): reword ERA001 false-positives + enable rule in CI` dropped the parens/JSON/tuple syntax so comments read as prose, kept the `# nosemgrep:` directives with `# noqa: ERA001` |
| M-011 | 2026-04-24 | maintainability | H3 | medium | done | L | n/a | api/auth_db.py | 19 `ALTER TABLE ... DO/EXCEPTION` idempotent blocks in `_SCHEMA_SQL` instead of Alembic revisions | PR #34 (commit b205b1f) `refactor(m-011): convert _SCHEMA_SQL DO/EXCEPTION blocks to Alembic migrations`. Convention now: new column = new Alembic revision |
| M-012 | 2026-04-24 | maintainability | E5 | medium | done | M | n/a | api/tests/integration/ | Integration test dir contained only `__init__.py` — unit/integration/security split never followed through | PR #28 (3c671ea) `test(integration): real register → login → /me flow against Postgres` + PR #44 (8b18f5a) `test(m-012): integration tests for /api/sessions CRUD`. Real-DB test infra + coverage landed |
| M-013 | 2026-04-24 | maintainability | E1 | medium | done | S | n/a | api/tests/unit/test_credits.py | `TestCreditFormula._calc` re-implemented the formula and tested its own copy | PR #25 (commit 967693e) `refactor(credits): extract calc_credits pure function + test real impl`. Formula now a pure fn tested directly |
| M-014 | 2026-04-24 | maintainability | G5 | medium | done | M | n/a | api/main.py + routers | Zero `request_id` / correlation id anywhere; structured JSON logs couldn't be stitched across LLM+DB+tool calls | PR #25 (commit 9a26522) `feat(observability): request_id middleware + tagged JSON logs`. uuid4 per request, contextvar, `_JSONFormatter` emits it |
| M-015 | 2026-04-24 | maintainability | C2/C3 | medium | done | S | n/a | api/credits.py, planner.py, auth_db.py | Business thresholds + infra knobs hardcoded (`DEFAULT_GRANT_CREDITS`, MiniMax `timeout=60`, pool minconn/maxconn, etc.) | PR #26 (commit fa43182) `refactor(config): lift 5 hardcoded thresholds to env-overridable config` |
| M-016 | 2026-04-24 | maintainability | F2 | low | done | S | n/a | / (repo root) | No root `README.md` — fresh cloner saw no stack/run orientation | PR #26 (commit 7f0052c) `docs: add root README.md` |
| M-017 | 2026-04-24 | maintainability | F4 | low | done | S | n/a | api/main.py:2 | Module docstring still referenced deleted `api/crm_db.py` — toxic comment | PR #24 (commit 847cb39) `docs(api): fix stale main.py docstring — crm_db is no longer in api/` |
| M-018 | 2026-04-24 | maintainability | A1 | low | done | S | n/a | ruff.toml | Dead `api/crm_db.py` per-file-ignore entry (file had been deleted in S-001) | Commit 208efa4 (part of S-008 PR) removed the line along with helpers/ path updates |
| M-019 | 2026-04-24 | maintainability | F6 | low | done | M | n/a | docs/adr/ | No ADR dir — major decisions (MiniMax primary, split DBs, field_policy bifurcation, report state machine) unrecorded | PR #27 (commit ae66d1e) `docs(adr): retrospective ADRs for 4 non-obvious decisions`. 5 ADRs under `docs/adr/` |
| M-020 | 2026-04-24 | maintainability | G4 | low | done | S | n/a | api/services/document/rnpv_excel.py | `generate()` printed 8+ status lines directly to stdout while invoked from the FastAPI report pipeline — unstructured logs leaked into the JSON stream, no level, no request_id | PR #45 (commit 6ec5632) `fix(m-020): replace print() with logger in rnpv_excel`. `print(...)` → `logger.info(...)` with structured extras; CLI `main()` keeps interactive feedback via `logging.basicConfig` |
| M-008 | 2026-04-24 | maintainability | B1/B2/B4 | medium | done | L | n/a | api/services/document/rnpv_excel.py, api/routers/chat/llm_stream.py | 24 C901 > 10 originally. `call_minimax_stream` split in PR #35. All 10 rNPV sheet builders split into `api/services/document/rnpv/*.py` (assumptions/patient_funnel/revenue/cost/pl/rnpv_sheet/sensitivity/qc/references; build_summary stays in rnpv_excel.py — already C<10) | PRs #48 (assumptions 32→<10), #50 (cost 26→<10), #51 (rnpv 24→<10, w/ Python-mirror), #55 (pl 17→<10), #56 (qc 15→<10), #57 (references 12→<10), #59 (sensitivity 12→<10), #60 (patient_funnel 13→<10), #61 (revenue 13→<10). rnpv_excel.py **2491 → 282 lines, zero C901 > 10**. Shared `rnpv/_styles.py` (palette + fonts + fills) + `rnpv/_helpers.py` (apply_header_row / write_input_cell / s_curve). Every sheet verified byte-identical NPV through full smoke test. `markdown_to_docx=19` in docx_builder.py is now the only C901 in services/document/ — unrelated to rNPV, belongs to a separate finding |
| M-004 | 2026-04-24 | maintainability | D5/D6 | high | done | L | n/a | frontend/src | Started at 120 `no-explicit-any` + 111 literal `any` across page components, api shims, report polling, catch handlers | Multi-PR sweep landed: #36 (lib/api.ts 13→0), #37 (dashboard/admin/report-polling 103→79), #38 (companies/catalysts/report-form 79→56), #41 (CRM list+detail 50→29), #42 (`catch (err: any)` → `unknown` + errorMessage helper), #43 (sessions/search/report-done -13), #47 (dialogs + bg helper 6→2). Final 2 `safeJsonParse` warnings closed by typing it generic — `safeJsonParse<T>(val: unknown): T \| null` — plus explicit generics at the 4 buyer-page callsites and nullable-ok prop types for `CapabilityMap` / `DealTypePref`. `eslint src` now reports **0 `no-explicit-any` warnings**. The ~33 remaining eslint warnings are unrelated (unused vars, set-state-in-effect, empty catch) |

---

## Wontfix

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes (why not fixing) |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|------------------------|

---

## False-Positive

（保留误报记录，便于识别 LLM 的系统性误判模式。）

| ID | Date | Scope | Rubric | File:Line | Why False-Positive |
|----|------|-------|--------|-----------|---------------------|
| S-013 | 2026-04-24 | structure | C4 | frontend/src/components/charts/ | `ls` showed an empty directory locally, but git doesn't track empty dirs — `git ls-files` returned nothing. No repo-level fix needed; the dir never existed for anyone cloning the repo. Systematic lesson: structure review must distinguish "on disk" from "in git" before flagging empty dirs. |
