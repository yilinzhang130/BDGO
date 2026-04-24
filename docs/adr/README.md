# Architecture Decision Records

Lightweight capture of decisions that would otherwise be "tribal knowledge".

## When to write one

- The decision is **not obvious from the code alone** — someone reading the repo six months from now would ask "why?"
- Reasonable people could disagree with the choice
- You considered 2+ alternatives before settling

## When NOT to write one

- The code tells the story (well-named identifiers, commit message, inline comment)
- Pure style preferences (`black` vs `ruff format`, etc.)
- Choices so obvious they wouldn't be questioned

## Template

```markdown
# ADR NNNN: Short title

- **Status**: Accepted | Superseded by ADR-NNNN | Rejected
- **Date**: YYYY-MM-DD

## Context
What problem are we solving? Constraints in play?

## Decision
What did we choose? One paragraph.

## Consequences
What changes for future code? What do we lose / gain?

## Alternatives considered
Other options + why they lost. Keep to 1-3 bullets each.
```

Keep each ADR under ~100 lines. Link from findings.md / code comments when revisiting.

## Index

- [0001 — LLM provider selection: MiniMax primary, DeepSeek/Claude staged](0001-llm-provider-selection.md)
- [0002 — Two-Postgres split (auth DB vs CRM DB)](0002-two-database-split.md)
- [0003 — Field visibility via internal/external user flag](0003-field-policy-internal-external.md)
- [0004 — Report task state machine backed by report_history](0004-report-state-machine.md)
- [0005 — Integration tests run against a real Postgres provided via env var](0005-integration-test-postgres.md)
