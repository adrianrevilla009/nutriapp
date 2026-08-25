---
description: Implementation conventions for CQRS and Event Sourcing in NutriApp. Use whenever working on diary-service, profile-service, or analytics-service, or any code touching the event store, projections, or event schemas.
---

# CQRS and Event Sourcing — NutriApp Conventions

Full rationale in `docs/adr/0002-cqrs-and-event-sourcing.md`. Scope: full
event sourcing in `diary-service` and `profile-service`; CQRS read-only
consumption in `analytics-service` and `notification-service`; conventional
persistence with published events elsewhere (including
`nutrition-calculation-service` — see ADR-0002 for why it's the one
"computed value" service that stays event-driven CRUD rather than fully
event-sourced).

## Event Design

### Schema
Every event, regardless of producing service, follows this envelope:
```json
{
  "event_id": "uuid",
  "aggregate_id": "uuid",
  "event_type": "FoodEntryLogged",
  "version": 1,
  "occurred_at": "2026-08-23T10:15:00Z",
  "payload": { "...": "event-specific fields" },
  "metadata": {
    "correlation_id": "uuid",
    "causation_id": "uuid",
    "user_id": "uuid"
  }
}
```
- `event_type` + `version` together identify the schema. A breaking payload
  change means a new `version`, never mutating the meaning of an existing one.
- `causation_id` points to the event or command that caused this event,
  enabling full causal chain reconstruction for debugging/audit.

### Immutability
Once appended to the event store, an event is never updated or deleted.
Corrections are new events (`FoodEntryCorrected`), interpreted by projectors,
never edits to history.

### Versioning & Upcasting
When a payload schema must change in a breaking way:
1. Introduce `EventName` v2 with the new shape.
2. Write an upcaster that transforms v1 events into the v2 shape when read,
   so old events in the store remain usable without a destructive migration.
3. New code only ever produces the latest version; old versions are read-only,
   upcasted on the way in.

## Write Model (Event-Sourced Aggregates)

- The aggregate's current state is never stored directly as the source of
  truth — it is derived by folding over its event stream:
  ```python
  def rebuild(events: list[DomainEvent]) -> Aggregate:
      state = Aggregate.empty()
      for event in events:
          state = state.apply(event)
      return state
  ```
- Commands are validated against the *current derived state*, and on success
  produce one or more new events, appended atomically to the store.
- Snapshotting (storing a periodic materialized state to avoid replaying an
  ever-growing stream) is an optimization to introduce later, only once replay
  time is measured to be a real problem — do not add it speculatively.

## Read Models (Projections)

- Built asynchronously by projectors subscribing to the event stream (via
  RabbitMQ, sourced ultimately from the event store through the Outbox).
  This is the default; see the deviation note below for the one accepted
  exception in the repo so far.
- Fully disposable: a read model must always be rebuildable by replaying the
  relevant event stream from the beginning. Never store data in a read model
  that cannot be derived from events — if you need it, it belongs in an event
  payload instead. This must be an actual, operable capability (a runnable
  rebuild script/command that truncates the read model(s) and replays the
  event store through the same `apply()` used on the write path, with
  projector `apply()` idempotent under replay), not merely a docstring
  assertion — `services/profile-service/scripts/rebuild_read_models.py` is
  the concrete precedent.
- Optimized for the exact query the UI needs, not for generality — it is fine
  (expected) to have multiple read models derived from the same events, each
  shaped for a different query.

### Deviation: synchronous, same-transaction projection

`profile-service` applies `PostgresSnapshotProjector`/`PostgresEvolutionProjector`
**synchronously**, in the same DB transaction as the event-store append and
outbox enqueue, rather than via a separate projector process subscribing to
RabbitMQ (see `services/profile-service/CLAUDE.md` and `README.md`, "Projection
consistency"). This is an **accepted pattern only under a low-write-volume
profile** like `profile-service`'s (infrequent per-user updates — a handful
of metric/goal writes per user per session, not a high-throughput stream —
and few read models, currently two). It buys immediate read-after-write
consistency for `GET /profile` and avoids a third long-running consumer
process, at the cost of coupling read-model write latency to the command's
own transaction.

**This is not a default any other service inherits automatically.** Any
service considering this pattern — most notably `diary-service`, given its
much higher write volume and CLAUDE.md section 2.2's own description of it
as "the primary transactional domain" — must make a freshly-justified
choice on this specific axis (synchronous same-transaction projection vs.
the async-projector-via-broker default) in its own implementation plan,
citing `profile-service` as prior art but not simply copying the decision.
A high-write-volume service that couples projection to the write
transaction risks write-path latency/throughput degradation that
`profile-service`'s low-volume profile does not expose.

## Outbox Pattern (mandatory alongside event sourcing)

Appending an event to the store and publishing it to RabbitMQ must be a single
atomic unit from the producer's perspective:
1. In the same DB transaction as appending the event, insert a row into an
   `outbox` table.
2. A separate relay process/worker polls the `outbox` table and publishes to
   RabbitMQ, marking rows as published.
3. This guarantees at-least-once delivery without a dual-write race condition
   between the DB and the broker.

## Idempotent Consumption

Every consumer (in this service or others) must deduplicate by `event_id`
before applying an event's effect, since RabbitMQ delivery is at-least-once,
not exactly-once.

## Testing Requirements (see also `docs/testing-strategy.md`)
- **Rebuild test**: given a fixed sequence of events, `rebuild(events)` must
  produce the expected aggregate state. This is the single most important
  test category for an event-sourced aggregate.
- **Projector test**: given a fixed sequence of events, the resulting
  read-model row must match expectations.
- **Idempotency test**: applying the same event twice must not double-apply
  its effect.
