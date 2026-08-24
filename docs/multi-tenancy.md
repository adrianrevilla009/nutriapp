# Multi-Tenancy

## Decision

ADR-0018 (Accepted): NutriApp is **single-tenant, B2C** — one account per
user, no organizations or teams above the individual user. This is
Option A of the three options that ADR considered; the shared-schema
(Option B) and database-per-tenant (Option C) isolation models described
in an earlier draft of this document do not apply and have been removed.

## Consequences

- No `tenant_id` column, Row-Level Security policy, or tenant-scoped
  connection-pool sizing exists anywhere in the system. `identity-service`
  issues tokens scoped to a `user_id` only.
- `docs/authorization-model.md`'s access model is user-scoped throughout;
  there is no tenant-level role or provisioning/offboarding lifecycle.
- `social-service`'s "connecting with other people" feature is a
  user-to-user relationship (following), not an organizational membership
  — it does not reintroduce multi-tenancy; see
  `docs/domain-glossary-and-context-map.md` for how the two concepts are
  kept distinct.
- If a future B2B/coach-managing-clients direction is pursued, this is a
  new ADR (superseding ADR-0018), not a silent reinterpretation of this
  document — retrofitting tenancy after `profile-service` and
  `diary-service`'s event-sourced write models exist is materially more
  expensive than deciding it up front, which is exactly why ADR-0018 was
  resolved before their implementation began.

## Ownership

`architecture-agent` flags any change that reintroduces a tenant/
organization concept without a new ADR superseding ADR-0018.
