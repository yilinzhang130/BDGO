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
3. **`/timing` ↔ conference-ingest MCP** — currently `/timing` only reads CRM catalysts; wire the MCP server so upcoming-conference data feeds into outreach-window suggestions
4. **Outreach pipeline UI** — `/outreach` returns a markdown thread today; add a chat-embedded mini-table view (no separate dashboard route — chat-first per product decision)
5. **Watchlist** — user-favorited companies/assets/targets with status badges
6. **Report history persistence** — completed tasks live in Postgres but the chat UI still relies on localStorage for ordering; add a real `/history` endpoint
7. **Anthropic Claude API as alternate LLM** — current MiniMax works, but Anthropic via OpenRouter or direct gives higher fidelity for /draft-X long-form output

### 🟢 P2 — Month 2
8. **Pricing / quota** — credit system + usage metering already in DB schema; needs Stripe wiring + dashboard
9. **Deeper planner agent** — coverage check via embedding similarity rather than rigid 7-step template
10. **PubMed MCP / ClinicalTrials.gov MCP** — direct tools in Chat beyond the existing CRM-only path
11. **Multi-language** — English UI option (currently Chinese-first with English terms inline)
12. **News feed page / catalyst calendar** — secondary nav routes pulling from CRM catalyst fields

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
