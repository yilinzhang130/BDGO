# BD Go — Next Steps Roadmap

## Current State (as of 2026-04-11)

### ✅ Done
- Light theme redesign (3-column chat layout, DNA logo, session persistence)
- 6 Report Services: paper-analysis, buyer-profile, clinical-guidelines, disease-landscape, ip-landscape, target-radar
- 19 Chat tools (10 CRM + 3 Guidelines + 6 Report generators)
- Context panel (auto-extract entities from tool results)
- Multi-step dispatch (LLM-native, system prompt driven)
- Guidelines DB integrated (79 guidelines, 611 recs, 379 biomarkers)
- Tavily web search with sequential key drain
- Docx builder (Navy/Gold investment banking style)
- File attachments in Chat (PDF/PPTX/DOCX text extraction)
- BP Upload + analysis trigger

### 🔴 P0 — Before Internal Beta
1. **Bug fixes from user testing** — upload flow, dark mode residuals, mobile layout
2. **User auth** — NextAuth.js (Google/email login), JWT, user table in Postgres
3. **Session persistence** — move from localStorage to server-side (Postgres)
4. **Deploy to cloud** — Tencent Cloud 2C4G + Vercel frontend + domain + HTTPS
5. **CRM sync pipeline** — daily cron: local crm.db → cloud server (rsync/scp)

### 🟡 P1 — First 2 Weeks After Beta
6. **More report services** — tech-scout, catalyst-calendar, deal-scout
7. **Guidelines DB expansion** — add ESMO/JSCO for P1 diseases per EXPANSION_PLAN.md
8. **News feed page** — /news route showing recent deals as timeline cards
9. **Catalyst calendar page** — /calendar with month/week view from CRM catalyst fields
10. **Watchlist** — user favorites (companies/assets/targets) with notification badges
11. **Report history** — persist completed reports to Postgres (currently localStorage)

### 🟢 P2 — Month 2
12. **Anthropic Claude API** — replace MiniMax for higher quality (needs API key)
13. **Deeper dispatch agent** — coverage check via embedding similarity, not just prompt
14. **ClinicalTrials.gov integration** — live NCT search tool (not just CRM static data)
15. **PubMed MCP** — direct PubMed tool in Chat (beyond paper-analysis report)
16. **Pricing/quota** — Stripe + credit system for report generation
17. **Multi-language** — English UI option (current: Chinese-first with English terms)

### 🔵 P3 — Month 3+
18. **Mobile PWA** — responsive layout + offline report viewing
19. **Team features** — shared watchlists, report collaboration, @mentions
20. **API access** — public REST API for programmatic report generation
21. **Drug pipeline table** — new CRM table with ClinicalTrials.gov sync
22. **Conference tracker** — ASCO/ESMO/ASH/AACR abstract monitoring
23. **Advanced analytics** — deal comp visualizations, heatmaps, trend charts

## Architecture Notes for Next Session

### Files to know
- Backend entry: `api/main.py` (13 routers mounted)
- Chat brain: `api/routers/chat.py` (19 tools, system prompt with dispatch)
- Report framework: `api/services/report_builder.py` (ReportService ABC)
- Report services: `api/services/reports/*.py` (6 services)
- Shared helpers: `api/services/helpers/` (llm, pubmed, search, docx_builder, text)
- Central config: `api/config.py` (MINIMAX keys, paths)
- Frontend chat: `frontend/src/app/chat/page.tsx` (3-column layout)
- Sessions: `frontend/src/lib/sessions.ts` (localStorage, useSyncExternalStore)
- Reports UI: `frontend/src/app/reports/page.tsx` + ReportGenerateDialog.tsx

### Key decisions already made
- Layer 1 (local Claude Code + skills) ≠ Layer 2 (BD Go web). Don't mix.
- MiniMax M1-80k as LLM (Anthropic-compatible API, tool_use works)
- No dependency on openclaw.json / openclaw gateway for BD Go
- Report services: 1 new .py file + 2 lines registration = new feature
- Guidelines.db is separate from crm.db (different SQLite file)
- Tavily keys: sequential drain, never round-robin (see feedback_tavily_key_rotation.md)

### What NOT to touch
- ~/.openclaw/skills/* (Layer 1, Claude Code only)
- ~/.openclaw/openclaw.json (gateway config, breaks Feishu if changed)
- ~/.openclaw/agents/* (agent sessions, not dashboard's concern)
- workspace/scripts/*.py (data pipeline scripts, shared read-only)
