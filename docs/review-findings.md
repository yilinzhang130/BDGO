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

---

## In-Progress

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------|

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
