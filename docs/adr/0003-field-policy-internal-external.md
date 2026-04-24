# ADR 0003: Field visibility via internal/external user flag

- **Status**: Accepted
- **Date**: 2026-04-24 (retrospective)

## Context

BDGO has two user populations on the same schema:

- **Internal analysts** (company email domains in `INTERNAL_EMAIL_DOMAINS`, default `yafocapital.com`): need to see everything, including subjective columns like `BD跟进优先级`, `公司质量评分`, `内部备注`, `POS预测`, `Q1_生物学` through `Q4_商业交易性`, `差异化分级`, `战略评分`.
- **External partners** (other domains): see the neutral-factual columns only — company name, phase, indication, clinical endpoints — not the internal BD scoring.

These two views share the same tables. Duplicating the CRUD layer with "internal" and "external" tables would triple the write path (ETL writes to both, every edit touches both) and is a non-starter.

## Decision

`field_policy.py` defines `HIDDEN_FIELDS[<table>] = {col1, col2, ...}` for each CRM table and exposes `strip_hidden(rows, table, user)` — called on every external-facing response after the SQL fetch. A user is "internal" if `user.is_internal is True` (set at registration by `config.is_internal_email()` and overridable per-user by admins).

Hidden fields are stripped **post-query**, not excluded in SQL — the query ergonomics (SELECT \*) stay simple and we'd rather lose the marginal bandwidth saving than have two SQL code paths per endpoint.

## Consequences

- **Good**: Single SQL path, single CRUD code path. New columns default to internal-visible; adding to `HIDDEN_FIELDS` is a one-line change.
- **Good**: Admin override per-user (`users.is_internal` column) handles edge cases (contractor with temporary internal access) without data duplication.
- **Good**: Audited in one place — review `field_policy.py` for the full visibility matrix.
- **Bad**: Every response-producing endpoint must remember to call `strip_hidden`. Forgetting leaks internal columns. Mitigated by: keeping the surface small (all through `list_table_view` helper post-S-004 + a few one-off `strip_hidden` calls) and by security tests in `tests/security/`.
- **Bad**: SELECT \* fetches columns the external user never sees. Negligible at current row counts; revisit if a table grows huge hidden blobs.

## Alternatives considered

- **Row-Level Security (Postgres RLS)**: rejected — the policy is column-level, not row-level. RLS on columns is awkward and ties us to Postgres forever (incompatible with the SQLite snapshot).
- **Two separate tables per logical table (public / internal)**: rejected, see Context. Write-path tripling.
- **View per user class (`CREATE VIEW 公司_external AS SELECT ...`)**: considered. Rejected because the visibility rules change often (new BD columns added), and updating views lockstep with schema migrations would be painful.
