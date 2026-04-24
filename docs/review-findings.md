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
| M-001 | 2026-04-24 | maintainability | E4 | high | open | L | n/a | api/{planner,llm_pool,rate_limit}.py | Critical modules have zero tests. `planner.py` (337L, LLM plan/summarize), `llm_pool.py` (279L, key routing + concurrency), `rate_limit.py` (102L, per-user RPM caps) — none have a corresponding `test_*.py`. Regression risk for pricing/credits/quota is unvalidated | Add `test_planner.py` (parse_plan parsing + fallback chain), `test_llm_pool.py` (key drain + concurrency semaphore), `test_rate_limit.py` (RPM window reset + 429 boundary). Unblocks confident refactoring of the LLM hot path |
| M-002 | 2026-04-24 | maintainability | H4 | high | open | M | n/a | api/schema.sql vs api/auth_db.py:27 | Two sources of truth for auth schema. `schema.sql` has 62L / 5 tables (users, sessions, messages, context_entities, report_history); `auth_db.py:_SCHEMA_SQL` has 221L / 10 tables + 19 `ALTER TABLE` DO/EXCEPTION blocks. Baseline migration docstring even calls this out. Editing one will not update the other | Delete `api/schema.sql` (auth_db.py is the only runtime truth since baseline migration). Long-term: migrate DDL out of auth_db.py into numbered Alembic revisions (see M-011) |
| M-003 | 2026-04-24 | maintainability | A1/F4 | high | open | S | n/a | api/credits.py:21,45,48 | `credits.SCHEMA_SQL` (defined line 48) has zero references in the codebase; the module docstring + section comment both claim it's "appended to auth_db._SCHEMA_SQL at import time" but nothing does that. Real credits/usage_logs DDL lives duplicated in `auth_db.py:190-211`. Editing credits.SCHEMA_SQL would silently do nothing | Delete `credits.SCHEMA_SQL` and the misleading comments, or wire it up by concatenating into `auth_db._SCHEMA_SQL` at import. The wiring approach would also fix M-002's duplication for credits specifically |
| M-004 | 2026-04-24 | maintainability | D5/D6 | high | in-progress | L | n/a | frontend/src (2 any warnings remaining) | Started at 120 `no-explicit-any` + 111 literal `any`. Multi-PR sweep in progress | PRs #36 (lib/api.ts 13→0), #37 (dashboard/admin/report-polling 103→79), #38 (companies/catalysts/report-form 79→56), #41 (CRM list+detail 50→29), #42 (`catch (err: any)` → `unknown`), #43 (sessions/search/report-done -13), #47 (dialogs + bg helper 6→2). 2 `safeJsonParse` warnings remain in `lib/format.ts`; fixing them ripples into `app/buyers/[name]/page.tsx` component prop types |
| M-005 | 2026-04-24 | maintainability | G1 | high | open | S | n/a | api/credits.py:166-174 | Billing `record_usage` wraps its DB UPDATE in `except Exception: logger.exception(...); return 0.0`. Comment says "Don't surface billing errors to the user mid-chat" — ok for UX, but the user then gets the completed response *and* zero credits deducted. A DB hiccup ≈ free usage. No alerting hook | Keep the swallow-and-continue behavior, but add a metric (`credits.record_usage.failed`) or write a row to a `billing_errors` table so ops can reconcile. Current setup has no signal that money is leaking |
| M-006 | 2026-04-24 | maintainability | F5 | medium | open | M | n/a | api/routers/*.py (98 routes) | 98 `@router.{get,post,put,delete,patch}` decorators; only 5 occurrences of `summary=` or `response_model=` across the tree. OpenAPI `/docs` will be nearly empty — no per-endpoint description, no declared response shape. Frontend `lib/api.ts` hand-types the payloads (feeding into M-004) | Add `response_model=` for the top ~20 endpoints the frontend actually calls. Fold hand-written frontend types into generated OpenAPI types downstream |
| M-007 | 2026-04-24 | maintainability | C4 | medium | open | S | n/a | api/{auth.py:150,models.py:75/88,main.py:34/35/107,rate_limit.py:35/36,services/helpers/search.py:29/33,routers/aidd_sso.py:21/22,routers/chat/tools/edgar.py:28} | `os.environ.get` calls scattered across 7+ files instead of all in `config.py`. `ADMIN_SECRET`, `DEEPSEEK_API_KEY`, `CLAUDE_API_KEY`, `LOG_FORMAT`, `CORS_ORIGINS`, `MAX_CONCURRENT_CHAT_PER_USER`, `MAX_RPM_PER_USER`, `TAVILY_API_KEYS`, `AIDD_SSO_SECRET`, `SEC_USER_AGENT` all read inline. S-006 already lifted `ADMIN_SECRET` — use that as the precedent | Move remaining reads to `config.py`; import the constants. Rotation / audit currently requires grep across the codebase |
| M-008 | 2026-04-24 | maintainability | B1/B2/B4 | medium | open | L | n/a | api/services/helpers/rnpv_excel.py, api/routers/chat/llm_stream.py | 24 functions with C901 complexity > 10. Worst offenders: `rnpv_excel.build_assumptions_sheet` (complexity 32, 244 stmts, 33 branches), `llm_stream.call_minimax_stream` (35 / 102 / 35), `rnpv_excel.build_cost_sheet` (26 / 236 / 29), `rnpv_excel.build_rnpv_sheet` (24 / 216 / 26). `rnpv_excel.py` is a 2489-line single file. Overlaps with S-008 (helpers/ junk drawer split) | Split `rnpv_excel.py` by sheet (one module per `build_*_sheet`) as part of S-008's `services/document/` move. The `llm_stream.call_minimax_stream` split is more delicate — it mixes SSE parsing + fallback routing + tool-call accumulation; each deserves its own helper |
| M-009 | 2026-04-24 | maintainability | A7 | medium | open | S | n/a | api/requirements.txt, frontend/package.json | Unused dependencies. Backend: `aiofiles`, `respx`, `pytest-mock` (no import anywhere). Frontend: `@tanstack/react-table` (no import; the CRM tables are plain `<table>` markup in pages). `respx` suggests httpx mocking was planned but never adopted | Drop the 4 packages. Revisit when actually needed |
| M-010 | 2026-04-24 | maintainability | A3 | medium | open | S | n/a | 12 locations (ruff ERA001) | 12 blocks of commented-out code flagged by ERA001. Concentrated in `services/helpers/rnpv_excel.py` (5), `services/report_builder.py` (2), `routers/chat/compaction.py`, `routers/chat/tools/crm.py`, `routers/search.py`, `routers/tasks.py`, `planner.py` | Either delete or convert to ADR-style notes. Commented-out code rots and confuses reviewers about intent |
| M-011 | 2026-04-24 | maintainability | H3 | medium | open | L | n/a | api/auth_db.py:50-186 | 19 `ALTER TABLE ... DO/EXCEPTION WHEN duplicate` blocks embedded in `_SCHEMA_SQL` — a pre-Alembic idempotent-migration pattern. Baseline migration docstring already acknowledges this debt ("should be gradually retired as their columns are covered by proper migrations"). With baseline migration now in place, every ALTER still adds to this file instead of a new revision | Start a convention: any new column → new Alembic revision, not a new DO/EXCEPTION block. Backfill can be scheduled later |
| M-012 | 2026-04-24 | maintainability | E5 | medium | open | M | n/a | api/tests/integration/ | `tests/integration/` directory exists with only `__init__.py` — zero integration tests. The unit/integration/security split signals intent that was never followed through. `conftest.py` overrides `get_current_user` with a stub, so nothing currently exercises the real auth + DB path. Overlaps with S-011 (test-tree mirror) | Add `test_auth_flow.py` (real DB, full register → login → /me path) and `test_crud_flow.py` (list companies with filter/sort + paginate). Requires a test Postgres (docker-compose?) |
| M-013 | 2026-04-24 | maintainability | E1 | medium | open | S | n/a | api/tests/unit/test_credits.py:25-63 | `TestCreditFormula._calc` re-implements the production credit formula inline (`round(input_tokens * input_weight + output_tokens * output_weight, 2)`) and tests the re-implementation. If `credits.record_usage` drifts from this formula, the test will still pass. `TestEnsureBalance` does test the real function — only `TestCreditFormula` is pseudo | Extract the formula from `record_usage` into a pure function (e.g. `calc_credits(in_tok, out_tok, w_in, w_out)`) and test that directly. Also makes the formula testable across providers |
| M-014 | 2026-04-24 | maintainability | G5 | medium | open | M | n/a | api/main.py + all routers | Zero references to `request_id` / `correlation_id` / `trace_id` / `X-Request-ID` anywhere. Structured JSON logs (main.py:20) exist, but when a user reports "my report failed" there is no ID to stitch together the chat turn + LLM call + DB writes + tool invocations. Debug from a production bug report will require timestamp-grepping | Add a `request_id` middleware (FastAPI; uuid4 on entry, attached to `logging.contextvars`, emitted in `_JSONFormatter`). Propagate to LLM calls via a header so the MiniMax key gets tagged. Low effort, high ops value |
| M-015 | 2026-04-24 | maintainability | C2/C3 | medium | open | S | n/a | api/credits.py:39-41, api/planner.py:113/322, api/auth_db.py:266-267 | Business thresholds and infra knobs hardcoded. `DEFAULT_GRANT_CREDITS=10_000`, `MIN_CREDITS_PER_REQUEST=10` (no env override), `timeout=60` to MiniMax in planner (two places), `minconn=2, maxconn=20` for auth pool with archaeological comment "bumped from 10" | Move to `config.py` with env overrides. Pricing experiments otherwise need a code deploy |
| M-016 | 2026-04-24 | maintainability | F2 | low | open | S | n/a | / (repo root) | No `README.md` at the project root. `DEPLOY.md` + `TODO.md` exist but a fresh cloner sees no orientation: stack, how to run locally, env variables, where tests live. DEPLOY.md is production-focused, not local-dev | Add a 50-line README.md: stack summary, local-dev commands, env var list, pointer to DEPLOY.md and docs/review-findings.md |
| M-017 | 2026-04-24 | maintainability | F4 | low | open | S | n/a | api/main.py:2 | Module docstring reads `"CRM Dashboard API — FastAPI backend wrapping crm_db."` but `api/crm_db.py` was deleted (see S-001 In-Progress). The wrapping now goes through `crm_store.py` + the scripts/ `crm_db.py`. Toxic comment | Update to describe the actual architecture: FastAPI backend for BDGO (auth + chat + reports); CRM reads go through `crm_store.py` → `workspace/scripts/crm_db.py` |
| M-018 | 2026-04-24 | maintainability | A1 | low | open | S | n/a | ruff.toml:49 | `[lint.per-file-ignores]` contains `"api/crm_db.py" = ["B007"]` but that file has been deleted (S-001 in-progress). Dead config that will confuse future readers | Delete the line when S-001 lands. Also revisit the `resolve.py` F841 exemption + `rnpv_excel.py` blanket exemptions after M-008 |
| M-019 | 2026-04-24 | maintainability | F6 | low | open | M | n/a | docs/ | No ADR (Architecture Decision Record) directory. Non-obvious decisions with no captured rationale: (a) MiniMax as primary LLM with DeepSeek/Claude as fallback, (b) two separate Postgres databases (auth vs CRM) + SQLite read-only snapshot, (c) field_policy.py's internal/external bifurcation of BD columns, (d) report-history state machine (queued/running/completed/failed) | Create `docs/adr/` with 3-4 retrospective ADRs for the above. Future decisions use the same template. One-time 2-3h effort |

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
