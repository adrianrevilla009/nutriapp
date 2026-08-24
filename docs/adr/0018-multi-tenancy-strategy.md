# ADR-0018: Multi-Tenancy Strategy

## Status
Accepted

## Date
2026-08-23

## Context
Every hexagonal service in this project has its own database (CLAUDE.md
section 2.5). Whether that database's tables need a `tenant_id`/
`organization_id` column on every row, whether authorization checks
(`docs/authorization-model.md`) are scoped per-user or per-organization,
and whether a support/billing feature needs to operate "on behalf of a
tenant" all depend on this decision. Left undecided, agents will guess
inconsistently across services.

## Decision

**Option A — No multi-tenancy (single-tenant per account).** NutriApp is
consumer-facing (B2C): every row is scoped by `user_id` only, with no
organization/tenant concept above the individual account.
`social-service`'s "connecting with other people" feature (following) is
a user-to-user relationship, not an organizational membership, and does
not reintroduce tenancy — see
`docs/domain-glossary-and-context-map.md`.

## Considered Alternatives

**Option B — Shared-schema multi-tenancy (`tenant_id` column).** Rejected
for v1: NutriApp has no B2B/organization concept in
`docs/product-requirements.md`'s feature list. Would add a `tenant_id`
column and Postgres RLS enforcement to every tenant-scoped table for no
current product need.

**Option C — Schema-per-tenant or database-per-tenant.** Rejected: no
named enterprise customer or compliance requirement drives physical data
isolation beyond the per-service database isolation already in place
(CLAUDE.md section 2.5).

## Consequences
### Positive
- `identity-service`'s data model, every other service's row-scoping
  convention, and `docs/authorization-model.md`'s permission checks are
  all consistent from the first implementation plan, not retrofitted.
- No RLS policies, tenant provisioning lifecycle, or per-tenant connection
  pooling to build or operate.

### Negative / Trade-offs
- Switching to Option B or C later, once real user data exists, is
  materially more expensive than it would have been up front — this was
  a deliberate, measure-twice-cut-once decision (the one exception to
  this repo's general bias toward deferring decisions until measured
  need, per ADR-0012's pattern). If a future B2B/coach-managing-clients
  direction is pursued, it requires a new ADR superseding this one, not a
  silent reinterpretation.

### Follow-up actions
- `CLAUDE.md` section 2.5 (Database Strategy) already states the
  single-tenant row-scoping convention (`user_id` only).
- `docs/multi-tenancy.md` documents the decision and its consequences for
  future reference.

## References
- `docs/authorization-model.md`
- `CLAUDE.md` section 2.5
- `docs/multi-tenancy.md`
- `docs/domain-glossary-and-context-map.md`
