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
| **ID** | 形如 `S-001` (structure) / `P-001` (performance) / `M-001` (maintainability) / `A-001` (api-design) / `SEC-001` (security)，递增不复用 |
| **Date** | 首次发现日期 (YYYY-MM-DD) |
| **Scope** | `structure` / `performance` / `maintainability` / `api-design` / `security` |
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
| A-001 | 2026-04-25 | api-design | A1/C1 | high | done | S | yes | api/routers/reports.py:384-442 | GET /api/reports/share/{token} 和 download 端点挂在带 `_auth` 依赖的 reports router 下，unauthenticated 接收者收到 401；share 功能完全失效 | PR #74: 新增 `public_router = APIRouter()`，两个 share 端点移至 public_router；main.py 不带 _auth 单独挂载 `/api/reports` prefix |
| P-011 | 2026-04-25 | performance | B1/C3 | medium | done | S | n/a | api/routers/conference.py:83-93 | `_sessions_etag()` 每次非 304 请求都对 CONFERENCES_DIR 下每个 session 做 os.stat()，O(N) 磁盘 I/O，随会议数增长线性劣化 | PR #76: 增加 `_sessions_etag_cache: tuple[str, float] | None` + 30s TTL，避免重复 stat() |
| P-012 | 2026-04-25 | performance | B3/B6 | medium | done | S | n/a | api/services/reports/buyer_profile.py:362-431 | buyer_profile 在 _report_executor(max_workers=6) 内嵌套 ThreadPoolExecutor(2+4)，满载时最多 36 LLM 线程，但 llm._http_client 连接池上限 20；线程争抢连接导致并行收益归零 | PR #76: `_http_client` max_connections 20→40，max_keepalive 10→20，匹配最坏情况并发 |
| M-021 | 2026-04-25 | maintainability | C2 | medium | done | S | n/a | api/routers/chat/system_prompt.py:10-21 | 系统提示硬编码数据量（"184家"、"79条"、"44,000+"等）随 DB 增长静默漂移，LLM 向用户报告过时数据 | PR #76: 替换为"数百家"、"数万条，持续入库"等描述性语言，不再绑定具体数字 |
| M-022 | 2026-04-25 | maintainability | A7 | medium | done | S | n/a | api/services/reports/buyer_profile.py:579-585 | `_enrich_and_save_to_crm` 在热路径执行 `sys.path.insert` + 延迟 `import crm_db`；两个并发的 enrichment 可能产生 path 竞争，静态分析工具也无法追踪此依赖 | PR #76: crm_db 移至模块顶层 `try/except ImportError`，函数内改为 `if _crm_db is None: return` |
| M-023 | 2026-04-25 | maintainability | E4 | medium | done | S | n/a | frontend/src/lib/api-server.ts:35-38 + frontend/src/app/companies/page.tsx | Server Component 抛 `throw new Error` 无对应 `error.tsx`，backend 不可用时 Next.js 直接向浏览器暴露内部堆栈 | PR #77: 新增 `frontend/src/app/error.tsx` 全局边界，捕获所有 RSC 异常，显示友好提示 + Retry 按钮 |
| S-014 | 2026-04-25 | structure | A1 | medium | done | M | n/a | frontend/src/app/deals/DealsClient.tsx:36-70 vs frontend/src/app/ip/IPClient.tsx:36-87 | DealsClient 和 IPClient 的 useCallback(load) + handleSort + handleQ + handlePage 逻辑逐行复制，任何 bug 修复或功能扩展都要改两处 | PR #77: 提取 `frontend/src/hooks/usePaginatedTable.ts`，DealsClient + IPClient 各删除 ~40 行样板代码，统一 debounce 在 hook 内处理 |
| M-024 | 2026-04-25 | maintainability | G4 | low | done | S | n/a | api/services/external/llm.py:92-99 | sync 路径的 `llm_call` log 无 task/chapter correlation ID；buyer_profile 并发跑多章时日志条目无法区分 | PR #77: `_call_one_sync` / `call_llm_sync` / `ctx.llm` 增加可选 `label` 参数；buyer_profile `_run_ch` 传入 `label=f"bp_ch{ch_num}"` |
| M-025 | 2026-04-25 | maintainability | C2 | low | done | S | n/a | frontend/src/lib/auth.ts:47 | `bdgo_token` cookie 设置时无 `Secure` flag；HTTPS 部署下 JWT 可能经由 HTTP 明文传输 | PR #76: `setAuth` 中检查 `window.location.protocol === 'https:'`，按需追加 `; Secure` |
| P-013 | 2026-04-25 | performance | F1 | low | done | S | n/a | frontend/src/app/deals/DealsClient.tsx:98 + frontend/src/app/ip/IPClient.tsx:100 | 搜索框 onChange 无 debounce，用户每次按键触发一次 API 请求；输入"Pfizer"发出 6 个竞态请求 | PR #77: DealsClient + IPClient 增加 `searchDebounce` useRef，300ms 防抖后再触发 load |
| SEC-001 | 2026-04-25 | security | B1/D1 | high | open | S | n/a | api/routers/chat/tools/crm.py:296-308 | `count_by` 用 `PRAGMA table_info()` 做列名校验，在 Postgres 上永远返回空列表 → 列名守卫永远触发，工具在 PG 上完全失效；若守卫被绕过则 `group_by` 直接 f-string 插入 SQL，存在列名注入风险 | Fix: `_is_pg()` 分支：PG 用 `information_schema.columns`，SQLite 保留 PRAGMA；空 cols 时返回错误而非允许任意列 |
| SEC-002 | 2026-04-25 | security | A2/D3 | high | open | S | n/a | api/routers/auth.py:88-142 | POST /login 和 /register 无速率限制；允许暴力破解密码及 bcrypt CPU 耗尽型 DoS | Fix: 模块级简单 IP 滑动窗口计数器（10次/60s），超限返回 429；注释说明多 worker 局限性 |
| SEC-003 | 2026-04-25 | security | A2 | medium | open | S | n/a | api/routers/auth.py:100 + api/auth.py:36 | register/login 在调用 bcrypt 前无密码长度上限；虽 bcrypt 截断 72 字节，但超长字符串的 encode() 开销在并发时仍构成放大攻击面 | Fix: Pydantic `Field(max_length=128)` 限制 RegisterRequest.password；LoginRequest 同样在 bcrypt 前检查 |
| SEC-004 | 2026-04-25 | security | C1/D1 | medium | open | M | n/a | api/credits.py:93-104 + 123-178 | TOCTOU：`ensure_balance` 在事务1读余额，LLM 运行期间不持锁，`record_usage` 在事务2扣款；并发请求均通过检查后同时扣款，导致超额消费；`GREATEST(balance-%s,0)` 防负但不防超用 | Fix: `record_usage` 内 `SELECT balance FOR UPDATE` 序列化扣款；扣款前余额 < credits_charged 时写 CREDIT_RACE_DETECTED 警告 |
| SEC-005 | 2026-04-25 | security | A1/B2 | medium | open | S | n/a | api/routers/upload.py:24-67 | `upload_bp` 无 `Depends(get_current_user)` → 无法记录上传者身份；`serve_bp` / `list_bp_files` 向所有已认证用户开放全部 BP 文件，无用户维度隔离 | Fix: upload_bp 注入 user 参数用于审计日志；serve/list 文档说明共享意图，或视需求加 user_id 过滤 |
| SEC-006 | 2026-04-25 | security | A2/D3 | medium | open | S | n/a | api/routers/upload.py:43-46 | `upload_bp` 流式写入磁盘无总大小限制；攻击者可上传数 GB 文件耗尽磁盘空间 | Fix: 累计 size 超过阈值（建议 50 MB）时 raise HTTPException(413) 并删除已写入的临时文件 |
| P-014 | 2026-04-25 | performance | B1 | medium | open | S | n/a | api/routers/sessions.py:203-208 | `GET /api/sessions/{session_id}` 无 LIMIT 拉取全部消息；长期活跃 session 可积累数千条消息，单次查询返回全量数据，内存和传输无界 | Fix: 加 `LIMIT 200 ORDER BY created_at DESC`（客户端已有前序消息缓存）或提供 `?after=` 分页参数 |
| A-002 | 2026-04-25 | api-design | A3/C1 | low | open | S | n/a | api/routers/watchlist.py:47 | `GET /watchlist?type=invalid_type` 静默忽略无效 type 并返回全量数据，而非 400；与 POST /watchlist 对 entity_type 的严格校验不一致 | Fix: `type` 有值但不在 VALID_ENTITY_TYPES 时 raise HTTPException(400) |
| M-026 | 2026-04-25 | maintainability | G2 | medium | open | S | n/a | api/main.py:117 + api/services/report_builder.py:430 | `reclaim_stale_tasks` 仅在启动时调用一次；启动后挂起的任务直到下次重启前永远停留 running 状态，长期运行的部署会积累僵尸报告行 | Fix: lifespan 中启动 asyncio 后台循环（每 15 分钟调用一次 reclaim_stale_tasks） |
| M-027 | 2026-04-25 | maintainability | A4 | low | open | S | n/a | api/routers/watchlist.py:19-21 | `WatchlistAdd` 的 `entity_key` 和 `notes` 无 `max_length` 约束；LLM 工具调用可能传入任意长字符串导致 DB 列溢出或内存激增 | Fix: `entity_key = Field(..., max_length=500)`，`notes = Field(None, max_length=2000)` |
| M-028 | 2026-04-25 | maintainability | E2 | low | open | S | n/a | frontend/src/hooks/usePaginatedTable.ts:57 | `load` useCallback 的 deps 数组加了 `eslint-disable-next-line` 注释屏蔽警告；若调用方传入不稳定的 `fetchFn`（每次渲染新建函数引用），hook 会在每次渲染时重新创建 load 并无限触发请求 | Fix: 在 hook JSDoc Usage 注释中明确要求 `fetchFn` 必须稳定（useMemo/useCallback 包裹），去掉或缩小 disable 范围 |

---

## In-Progress

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------|

---

## Done

| ID | Date | Scope | Rubric | Severity | Status | Effort | BreaksClient | File:Line | Summary | Notes (PR/commit) |
|----|------|-------|--------|----------|--------|--------|--------------|-----------|---------|-------------------|
| P-001 | 2026-04-24 | performance | B1/B2 | critical | done | M | n/a | api/routers/chat/llm_stream.py:42-52, api/routers/chat/system_prompt.py (107L) | No prompt caching + no result caching on the MiniMax path. SYSTEM_PROMPT (~107 lines) + TOOLS array are re-tokenized and charged on every chat turn; `grep cache_control` across api/ → 0 hits. For a 20-concurrent deployment with 5–8 turns per session, the stable prefix (system + tools) is paid N×T times per day | PR #66: `_build_request` wraps system prompt in list-of-blocks with `cache_control: {type: "ephemeral"}`; last tool entry gets same marker via shallow copy. `_accumulate_usage` tracks `cache_read_input_tokens` from `message_start`. 23/23 unit tests pass. |
| P-002 | 2026-04-24 | performance | B9/E2 | high | done | M | n/a | api/services/external/llm.py:22-71, api/services/report_builder.py:96-105 | Report path bypasses `llm_pool`. `_call_one_sync` creates a fresh `httpx.Client` per call — TCP+TLS handshake paid on every report chapter. | PR #69: module-level `_http_client = httpx.Client(limits=Limits(keepalive=10, max=20))` in `services/external/llm.py`; timeout passed per-request. `atexit.register(_http_client.close)` for clean shutdown. (Multi-key routing via llm_pool is deferred — more invasive, separate PR.) |
| P-003 | 2026-04-24 | performance | B3/B6 | high | done | M | n/a | api/services/reports/buyer_profile.py:395-433 | 8 buyer-profile chapters run fully sequentially via `ctx.llm` → ~2 min wall-clock. Each chapter's `running_summary` only uses the last 1000 chars of prior output, so the true dependency chain is 1 → (2..8 parallel). `dd_checklist.py:494` already demonstrates the 3-batch ThreadPoolExecutor pattern. No streaming either — user sees only log lines in `/status/{task_id}` until all 8 complete | PR #72: 3-batch layout — Seq Ch1 → Par(Ch2,Ch3) → Par(Ch4,Ch5,Ch6,Ch7) → Seq Ch8. Each batch snapshots `running_summary[-1000:]` before launching threads. `ThreadPoolExecutor(max_workers=2/4, thread_name_prefix="bp_ch")`. Reduces wall-clock from ~120s to ~40s. |
| P-004 | 2026-04-24 | performance | G1/G2 | high | done | S | n/a | api/routers/chat/streaming.py:235-242, api/main.py:160-176 | No LLM-call observability. `usage_accum` is committed to `usage_logs` only at chat-turn completion (for billing); no latency histogram, no per-model token rate, no cache-hit ratio. `main.py:log_api_key_requests` records `latency_ms` only for X-API-Key traffic — JWT (the 99% path) gets none. Without this, perf review is guesswork and MiniMax quota runway is unknowable | PR #71: `call_minimax_stream` snapshots `usage_before` + `t0 = time.monotonic()` per attempt; emits `logger.info("llm_call model=... key=...%s in=... out=... cache_read=... latency_ms=... status=ok")` after pool.mark_success. `_call_one_sync` gets the same log from the response `usage` field. Grep `llm_call` for instant p95 analysis. |
| P-005 | 2026-04-24 | performance | A5/H2 | high | done | S | n/a | api/routers/reports.py:107-111 | Unbounded `threading.Thread(daemon=True)` spawn for async reports. A burst of 20 users each kicking off a deal_teaser / dd_checklist immediately spawns 20 threads, each holding an auth-DB connection + one-or-more MiniMax keys + running rnpv_excel builders that can allocate tens of MB. No semaphore, no queue. `daemon=True` also means abrupt shutdown → `report_history` rows stuck at `running` forever | PR #67: module-level `ThreadPoolExecutor(max_workers=REPORT_MAX_WORKERS, thread_name_prefix="report")` replaces per-request `Thread(daemon=True)`. `REPORT_MAX_WORKERS` env var (default 6) added to config.py. Lifespan shutdown reclaims running tasks then calls `shutdown_executor(wait=False, cancel_futures=True)`. |
| P-006 | 2026-04-24 | performance | C3 | medium | done | S | n/a | api/auth_db.py:73, api/routers/chat/chat_store.py:63-69 | `load_history` runs `WHERE session_id=%s ORDER BY created_at DESC LIMIT 100` on every chat turn, but `messages` only has `idx_messages_session(session_id)` — not the composite `(session_id, created_at DESC)` this query wants. With 1000+ messages in a session, PG fetches all session rows then sorts in memory | PR #68: Alembic migration `bc71de8f0467` creates `idx_messages_session_created(session_id, created_at DESC)` via `CREATE INDEX CONCURRENTLY` (zero downtime), then drops old `idx_messages_session`. `auth_db.py` bootstrap index updated to match. |
| P-007 | 2026-04-24 | performance | E2 | medium | done | S | n/a | api/services/external/pubmed.py:55/90/112/189, api/services/external/search.py:98 | `httpx.Client` constructed per call in Tavily (`search_web`) and PubMed (`search_articles`, `get_article_metadata`, `fetch_single`). Both are hot paths — Tavily is called from the chat tool loop via `asyncio.to_thread` and from every buyer-profile / deal-evaluator report (3–6 queries per run). Each call pays a fresh TCP+TLS handshake | PR #69: module-level `_http_client` hoisted in `pubmed.py` (keepalive=3, max=5) and `search.py` (keepalive=5, max=10); all 4 call sites use per-request `timeout=`. `atexit.register(_http_client.close)` in both modules. |
| P-008 | 2026-04-24 | performance | F1/F2 | medium | done | L | n/a | frontend/src/app/**/page.tsx (26/30 pages `'use client'`) | Almost the entire app is client-rendered: `companies`, `assets`, `clinical`, `deals`, `ip`, `buyers`, `catalysts`, `conference`, `dashboard`, `chat`, `reports`, `watchlist`, `admin`, etc. Every page pays the TTI waterfall: HTML shell → JS bundle → `useEffect` fires → 1..5 API calls. App Router Server Components + streaming would eliminate the JS-wait-then-fetch gap for data-heavy list/detail pages | PR #73: `auth.ts` mirrors JWT to `bdgo_token` cookie for RSC auth. `api-server.ts` reads cookie + calls backend directly (no-store). `/companies`, `/assets`, `/clinical`, `/buyers` → full Server Components + client filter islands (`CompaniesFilters`, `AssetsFilters`, `ClinicalFilters`, `BuyersFilters`). `/deals` and `/ip` → RSC shell fetches `initialData` server-side, passes to `DealsClient` / `IPClient` (chart + delete require client). Sort via `<Link>` URL params; pagination via `<Link>`. |
| P-009 | 2026-04-24 | performance | B4 | medium | done | S | n/a | api/routers/chat/llm_stream.py:241-248, api/services/external/llm.py:54-64 | MiniMax 529 retry uses fixed `2**attempt` (1s, 2s, 4s) with no jitter in either the streaming or sync path. Under correlated bursts (many users hit 529 together because one MiniMax plan saturates), retries synchronise and amplify load on the provider → longer outage | PR #67: both retry loops now use `wait = (2**attempt) * (0.5 + random.random())` — uniform jitter in [0.5×, 1.5×] of base delay. |
| P-010 | 2026-04-24 | performance | D3 | medium | done | S | n/a | api/routers/conference.py:79-314 | `/api/conference/sessions`, `/{session_id}/stats`, `/{session_id}/companies`, `/{session_id}/abstracts` all serve pre-processed JSON that only changes on deploy. `load_report_data` is `@lru_cache`d (good) but responses carry no `Cache-Control` or `ETag`, so browsers and the nginx reverse proxy re-fetch on every navigation. 460KB `report_data.json` is filtered-and-re-serialised on every call | PR #70: ETag derived from `report_data.json` mtime (stable per deploy); `If-None-Match` → 304 short-circuits all filtering work. `Cache-Control: public, max-age=300` added to all 5 endpoints via `_set_cache_headers` / `_cache_hit` helpers. |
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
| S-001 | 2026-04-24 | structure | A3/E2 | high | done | M | n/a | api/crm_db.py vs workspace/scripts/crm_db.py | `crm_db.py` duplicated in api/ and workspace/scripts/ | PR #17: deleted `api/crm_db.py`; both importers (`crm_store.py`, `services/reports/buyer_profile.py`) already prepend `scripts_dir` to sys.path, so the workspace copy is always loaded |
| S-002 | 2026-04-24 | structure | A2/A4 | high | done | L | n/a | api/routers/*.py (20 files) | No service layer — 67 raw SQL hits directly in routers | PR #30 `refactor/s002-s005-service-extraction` (pilot: companies + enrich) + PR #32 `refactor/s002-extract-remaining-domains` (assets/clinical/deals/ip/buyers). Full per-domain service layer in `services/crm/`; routers now delegate to service modules |
| S-003 | 2026-04-24 | structure | C2 | high | done | M | n/a | api/database.py, api/db.py, api/crm_db.py, api/crm_store.py | Four DB-ish modules with overlapping names | PR #17: renamed `database.py` → `auth_db.py` (17 files updated: 10 import sites + 6 doc refs + test patch target); deleted `db.py` (S-012) and `api/crm_db.py` (S-001) in same sweep |
| S-004 | 2026-04-24 | structure | A1/E1 | high | done | M | n/a | api/routers/{assets,buyers,clinical,companies,deals,ip}.py | Same list-endpoint pattern duplicated 6× | PR #22 `refactor/list-table-view-helper`: extracted `list_table_view()` into `services/crm/list_view.py`; 6 routers thinned by removing duplicated filter/sort/paginate/strip_hidden logic |
| S-005 | 2026-04-24 | structure | A1/A4 | high | done | L | n/a | api/routers/tasks.py | 340 lines of business logic (MiniMax HTTP + subprocess + prompt + column allowlist + JSON parse + update_row) inside a router | PR #30 `refactor/s002-s005-service-extraction`: extracted `services/enrich/` (task runner, minimax client, column policy); tasks.py router reduced to a thin dispatcher |
| S-006 | 2026-04-24 | structure | B1 | medium | done | S | n/a | api/routers/credits.py:9 | `routers/credits.py` imported private `_check_admin` from `routers/admin.py` (router→router) | PR #17: lifted to `auth.require_admin_header` (public); `ADMIN_SECRET` env read centralized to `auth.py`; no more router→router private import |
| S-007 | 2026-04-24 | structure | B1 | medium | done | S | n/a | api/routers/chat/tools/crm.py:229 | `routers/chat/tools/crm.py` imported private `_load_report_data` from `routers/conference.py` inside a function body | PR #17: extracted to `services/conference.py` (`load_report_data`, `@lru_cache`d); both routers import from services — no more router→router private import or function-body lazy import |
| S-008 | 2026-04-24 | structure | D4 | medium | done | M | n/a | api/services/helpers/ | `helpers/` junk drawer spanning 5+ domains | Incremental across PRs #30+#32 (crm/ domain: crm_lookup/resolve/per-table), #30 (enrich/), and M-008 PRs (document/: docx/pptx/rnpv), with external/ (llm/pubmed/search) extracted alongside. `helpers/` is now fully empty — only `__pycache__` shell remains |
| S-009 | 2026-04-24 | structure | D2 | medium | done | S | n/a | api/conferences/ | Directory looked like a Python subpackage but contained only JSON data | PR #17: moved to `api/data/conferences/`; `CONFERENCES_DIR` default in `config.py` updated; env var override path unchanged |
| S-010 | 2026-04-24 | structure | C4 | medium | done | S | n/a | frontend/src/lib/utils.ts | `utils.ts` mixed 5 unrelated responsibilities | PR #17: split into `browser.ts` (isBrowser, bg), `format.ts` (formatNumber/parseNum/safeJsonParse), `badges.ts` (4 phase/priority/result/status helpers), `chart-colors.ts` (COLORS); 14 importers updated; `utils.ts` deleted |
| S-011 | 2026-04-24 | structure | F1/F2 | medium | done | L | n/a | api/tests/ | Test tree did not mirror source; zero tests for services/ or routers/ | PR #31 `test/s-011-service-unit-tests`: mirrored source layout; 51 new unit tests for recently-extracted services added |
| S-012 | 2026-04-24 | structure | A1 | low | done | S | n/a | api/db.py | Deprecation shim with zero callers | PR #17: deleted `api/db.py`; grep confirmed zero static or dynamic importers before deletion |

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
