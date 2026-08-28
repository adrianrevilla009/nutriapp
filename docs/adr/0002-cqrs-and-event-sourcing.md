# ADR-0002: CQRS and Event Sourcing Scope

## Status
Accepted

## Date
2026-08-23

## Context
Some NutriApp domains have very different read and write shapes: `diary-service`
writes individual entries but is read as daily/weekly aggregates; `analytics-service`
reads large historical windows to compute trends but rarely writes; `nutrition-calculation-service`
needs a fully auditable history of how a user's targets and computed values evolved
over time (useful for later features like "why did my target change last month?").
Applying full CQRS + event sourcing everywhere would be over-engineering for domains
like `identity-service`, which are closer to simple CRUD.

## Decision
- Apply **CQRS** (separate write and read models) to `diary-service`,
  `nutrition-calculation-service`, and `analytics-service`.
- Apply **full event sourcing** (aggregate state derived purely from its event
  stream) to `diary-service` and `nutrition-calculation-service`, where historical
  auditability and replay have direct product value (e.g. recomputing derived
  values if a formula is corrected).
- `analytics-service` consumes events from other services to build its read
  models but does not need its own event-sourced write model, since it has no
  meaningful "write" side of its own beyond ingesting events.
- `identity-service`, `catalog-service`, `food-recognition-service`, and `nutrition-assistant-service`
  use a conventional persistence model (state stored directly), publishing
  domain events as a side effect for other services to consume ("event-driven
  CRUD"), without full event sourcing.

## Considered Alternatives
- **Event sourcing everywhere** — maximizes consistency of approach, but adds
  substantial complexity (event versioning, snapshotting, replay tooling) to
  domains that do not need it, slowing delivery without a clear benefit.
- **No event sourcing anywhere, only CQRS where needed** — simpler, but loses the
  ability to replay history for `diary-service`/`nutrition-calculation-service`, which is
  valuable both for correctness (recompute after a bug fix) and for future
  features (undo, audit, "how did this number get here?").

## Consequences
### Positive
- Event sourcing on the two domains where correctness and auditability matter
  most gives strong guarantees without paying that cost everywhere.
- Read models can be rebuilt independently, simplifying schema evolution on the
  read side.

### Negative / Trade-offs
- Two different persistence philosophies exist in the codebase (event-sourced vs.
  conventional) — must be clearly documented per service (`README.md` states
  which model applies) to avoid confusion.
- Event schema evolution requires discipline (versioning + upcasters) from day one.

### Follow-up actions
- Define the event store table schema in `diary-service` and `nutrition-calculation-service`
  before writing any other code.
- Document the event catalog in `docs/events-catalog.md`, updated with every new
  event type.

## References
- CLAUDE.md, section 2.3
- ADR-0001 (hexagonal architecture underpins where ports for the event store and
  projections live)

## Addendum — 2026-08-28: reconciling scope drift with CLAUDE.md §2.3

Discovered by `architecture-agent` while reviewing `notification-service`'s
implementation plan: this ADR's original Decision (2026-08-23, above) never
mentions `profile-service` or `notification-service`, and assigns full event
sourcing to `nutrition-calculation-service` — both of which diverge from
CLAUDE.md §2.3 and `.claude/skills/cqrs-event-sourcing/SKILL.md`, and from
what was actually built and merged: `profile-service` (PR #2) is
event-sourced; `nutrition-calculation-service` (PR #6) is event-driven CRUD.
This addendum corrects the record to match the actual, already-implemented
scope — it is not a new architectural decision, and no already-shipped
service is affected by it.

Corrected scope (supersedes the Decision section's list above):
- **Full event sourcing + CQRS**: `diary-service`, `profile-service`.
- **CQRS, read side only** (consumes events into read models, no
  event-sourced write aggregate of its own): `analytics-service`,
  `notification-service`.
- **Conventional persistence / event-driven CRUD**: `identity-service`,
  `catalog-service`, `food-recognition-service`, `nutrition-calculation-service`,
  `nutrition-assistant-service`, and (by default, unless a future ADR
  addendum says otherwise for a specific one) every other still-unbuilt
  Phase 2 service — `bff-service`, `activity-service`, `recipe-service`,
  `social-service`, `billing-service`.
