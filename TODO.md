# BD Go — Next Steps Roadmap

## Current State (as of 2026-04-26)

### ✅ Done — Beta-ready
- **Auth + sessions persisted in Postgres** (Google OAuth + email/password + JWT; SEC-002 rate limit; #115 flake fix)
- **Deployed**: Vercel frontend + uvicorn VM + domain + HTTPS (see `DEPLOY.md`)
- **CRM sync** (daily cron: local SQLite → cloud Postgres; `scripts/sync_crm.sh`)
- **25 ReportServices** registered + Slash dispatch + Chat tools auto-registered:
  - **Analysis**: `paper`, `target`, `disease`, `ip`, `guidelines`, `commercial`, `mnc`, `dd`, `evaluate`, `rnpv`, `company`, `teaser`
  - **BD lifecycle**: `synthesize`, `email`, `log`, `outreach`, `import-reply`, `dataroom`, `timing`
  - **/draft-X family** (5): `draft-ts`, `draft-mta`, `draft-license`, `draft-codev`, `draft-spa`
- **Lifecycle chip orchestration** — every service emits `meta.suggested_commands`; AST audit (#125) prevents the "Draft X → /legal review" closed-loop bug from regressing
- **Schema-validated outputs (L0/L1)** — every report runs through `validate_markdown(mode=...)` + targeted gap-fill retry; YAML schemas in `api/services/quality/schemas/`
- **BP intake plan mode** — uploaded BPs trigger 7-step planner checklist (#97)
- **kv-pair pre-parser** for chip-style slash commands (#123) — chip clicks bypass LLM entirely
- **Dev experience**: `scripts/dev.sh` one-command launcher with pre-flight checks (#120)
- **Doc self-description**: 9 mirrored services have `# MIRROR OF:` headers (#116); SKILL_MIRROR.md is the sync truth

### 🔴 P0 — Pending
1. **Live closed-loop run-through** — bring up local with real MINIMAX_API_KEY + Postgres, walk a full BD chain (`/teaser` → `/email` → `/log` → `/import-reply ts_signed` → `/draft-license` → `/legal review`) and capture real friction points
2. **Frontend test coverage** — backend has 781 passing tests; frontend has zero unit tests for critical hooks (`useSlashCommand`, `useReportPolling`)

### 🟡 P1 — First 2 Weeks
3. ✅ **`/timing` ↔ conference-ingest MCP** — shipped in #128: reads `conferences_calendar.yml` (same YAML the MCP serves); falls back to hardcoded annual events when file absent. Produces abstract-release BD windows.
4. ✅ **Outreach pipeline UI** — `OutreachMiniTable` component wired in `ChatMessage.tsx`; backed by `meta.outreach_pipeline_rows` / `meta.outreach_thread_events` from `OutreachListService`.
5. ✅ **Watchlist** — `/watchlist` page + `WatchlistButton` + full CRUD backend in `routers/watchlist.py`. Status badges, type filter, pagination.
6. ✅ **Report history persistence** — `reports.ts` is server-backed via `/api/reports/history`; `addCompletedReport` triggers a re-fetch; `removeCompletedReport` calls `DELETE /history/{task_id}`.
7. **Anthropic Claude API as alternate LLM** — model spec wired (`claude-sonnet-4-5`, `auth_style=x-api-key`); all streaming infra already Anthropic-native. **Action needed**: set `CLAUDE_API_KEY` env var on VM to unlock. Model shows as `available: false` in picker until key is present.

### 🟢 P2 — Month 2
8. **Pricing / quota** — credit system + usage metering already in DB schema; needs Stripe wiring + dashboard
9. ✅ **Deeper planner heuristic** — `should_plan()` extended with 3-tier keyword check: 30 Chinese BD keywords, 50+ English planning phrases, 20 strong BD patterns; 51 tests (#147)
10. ✅ **ClinicalTrials.gov chat tool** — `search_clinicaltrials` chat tool + `services/external/clinicaltrials.py` client; 18 tests (#145)
11. ✅ **Multi-language** — English/Chinese toggle in Sidebar footer; `LocaleProvider` + `useLocale()` hook; 60+ keys in `en.ts`/`zh.ts`; Sidebar nav, login page, auth errors all translated; 12 tests (#148)
12. ✅ **Company/asset news chat tool** — `search_company_news` chat tool + `search_news()` in Tavily service (news mode, recency filter); 19 tests (#146)

### 🔵 P3 — Month 3+
13. **Mobile PWA** — responsive layout + offline report viewing
14. **Team features** — shared watchlists, report collaboration, @mentions
15. **Public REST API** — programmatic access to report generation (auth via API keys, infra already there)
16. **Conference tracker** — ASCO/ESMO/ASH/AACR abstract monitoring, integrates with /timing
17. **Advanced analytics** — deal comp heatmaps, sector trend charts (separate visualization layer)

## Recently shipped (last 30 days, this branch)

The April 2026 sprint took main from 6 services → 25 services + closed the BD lifecycle loop end-to-end. Key landmarks:

| PR range | Theme |
|---|---|
| #82 — #100 | Lifecycle services (`/company`, `/email`, `/timing`, `/log`, `/outreach`, `/import-reply`, BP intake plan mode) + `/dd` perspective flip |
| #101 — #109 | `/dataroom` + `/draft-ts` + L0/L1 schema validation across 5 services |
| #110 — #113 | `/draft-X` family complete (mta / license / codev / spa) |
| #115, #117, #118, #125 | CI hygiene: kill flake, drift tests for planner inventory + schema modes + chip routing |
| #119, #121, #122, #125 | Closed-loop chip routing — `source_task_id` handoff + 4 broken `/legal review` chips fixed + AST audit |
| #114, #116, #120 | Doc + dev tooling: SKILL_MIRROR sync, MIRROR-OF headers, `scripts/dev.sh` |
| #123, #124 | UX: kv-pair pre-parser bypasses LLM for chip clicks; missing-fields hint shows kv template |
| #128 | `/timing` wired to conference-ingest calendar YAML — abstract-release BD windows |
| #134 | Frontend test coverage: `useSlashCommand` hook-level unit tests |
| #135 — #136 | L0/L1 for `/evaluate` + `/dd`; `/buyers` reverse buyer-matching |
| #138 | L0/L1 for `/target` + `/disease` + `/ip`; S2-08 auto-log on `/email` |
| #139 | `/meeting` brief service (S3-03) |
| #140 | `/batch-email` — batch outreach to N buyers in one call (S2-09) |
| #141 | `/faq` — DD FAQ pre-generation, 6 meeting stages (S3-04) |
| #142 | X-18 plan template system — 5 built-ins + user-saved templates |
| #143 | S1-03 asset metadata 6 → 10 fields (modality, ip_timeline, funding, team) |
| #144 | P1-07 Anthropic Claude API wired (`claude-sonnet-4-5`, `auth_style=x-api-key`); 18 tests |
| #145 | P2-10 ClinicalTrials.gov chat tool + service client; 18 tests |
| #146 | P2-12 Company/asset news search chat tool (Tavily news mode); 19 tests |
| #147 | P2-09 `should_plan()` heuristic — English BD keywords + 51 tests |
| #148 | P2-11 English/Chinese UI toggle — LocaleProvider, 60+ keys, Sidebar + login + auth wired; 12 tests |

## Architecture Notes for Next Session

### Files to know
- Backend entry: `api/main.py` (routers mounted)
- Chat brain: `api/routers/chat/` (split into streaming / planning / tools / system_prompt)
- Planner: `api/planner.py` (LLM-driven multi-step plan generation; tool inventory must stay in sync — drift test in #117)
- Report framework: `api/services/report_builder.py` (`ReportService` ABC, `ReportContext`)
- Report services: `api/services/reports/*.py` (25 services, each ~300-700L; `# MIRROR OF:` header points to source SKILL.md if mirrored)
- Quality validation: `api/services/quality/schema_validator.py` + `schemas/*.yaml` (L0 schema check; modes registered in `_SCHEMA_BY_MODE`, drift test in #118)
- Slash UX: `frontend/src/components/ui/SlashCommandPopup.tsx` (alias→slug map) + `frontend/src/hooks/useSlashCommand.ts` (parseAndRun + missing-field hints)
- Args extractor: `api/services/external/llm.py:extract_params_from_text` (kv-parse fast path → LLM fallback for residual)
- Lifecycle truth: `docs/SKILL_MIRROR.md` (mirroring map + lifecycle接线图)

### Key decisions already made
- Layer 1 (local Claude Code + skills) ≠ Layer 2 (BD Go web). Don't mix.
- MiniMax M1-80k as LLM (Anthropic-compatible API; tool_use works)
- No dependency on openclaw.json / openclaw gateway for BD Go
- Adding a new ReportService = 1 new `.py` file + 2 lines registration in `services/__init__.py` + 1 line in `SlashCommandPopup.tsx` + (optional) 1 line in `_SCHEMA_BY_MODE` + 1 line in planner inventory. Drift tests catch the registrations you forget.
- Chip handoffs use `meta.suggested_commands: list[{label, command, slug}]`. Chip commands must use `/draft-X` slug for any "Draft X" labeled chip — `/legal` is review-mode only and the audit (#125) blocks misrouting at CI.
- `/draft-X → /legal review` handoff carries `source_task_id={task_id}` so `/legal` reads the just-generated markdown directly (no re-paste; #119).
- Tavily keys: sequential drain, never round-robin (see `feedback_tavily_key_rotation.md`)

### What NOT to touch
- `~/.openclaw/skills/*` (Layer 1, Claude Code only)
- `~/.openclaw/openclaw.json` (gateway config, breaks Feishu if changed)
- `~/.openclaw/agents/*` (agent sessions, not dashboard's concern)
- `workspace/scripts/*.py` (data pipeline scripts, shared read-only)
- `services/quality/schemas/*.yaml` directly without updating the corresponding service's `validate_markdown(mode=...)` call

### Adding a new ReportService — checklist
1. Create `api/services/reports/<name>.py` subclassing `ReportService` (mirror an existing one, e.g. `draft_spa.py` for a structured-input service or `disease_landscape.py` for a CRM+web analysis)
2. Register in `api/services/__init__.py` (alphabetical order)
3. Add slash alias in `frontend/src/components/ui/SlashCommandPopup.tsx`
4. Add chat tool name to `api/planner.py` PLANNER_SYSTEM_PROMPT inventory (drift test catches you if you forget)
5. (If you want L0 validation) drop a YAML in `api/services/quality/schemas/` and add to `_SCHEMA_BY_MODE`
6. (If mirrored from a SKILL.md) add `# MIRROR OF: ~/.openclaw/skills/<name>/SKILL.md (synced YYYY-MM-DD)` header at the top of the .py file and update `docs/SKILL_MIRROR.md`'s mapping table
