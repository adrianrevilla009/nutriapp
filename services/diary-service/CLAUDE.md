# diary-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/diary-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/diary-agent.md`
(bounded context, domain responsibilities, rules) -- read both first.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001).
- Full event sourcing + CQRS (ADR-0002) -- NOT conventional persistence.
  Four aggregates, ALL always derived by folding over their event stream
  (`rebuild`), never stored as mutable current-state rows:
  `domain/entities/food_entry.py`, `water_intake_entry.py`,
  `fasting_window.py`, `meal_plan_entry.py`.
- **Mixed aggregate granularity** (the one deliberate deviation from
  `profile-service`'s uniform-per-user precedent, flagged for
  `architecture-agent` in the implementation plan section 6): `FoodEntry`
  / `WaterIntakeEntry` / `MealPlanEntry` are one instance **per logged
  item** (`aggregate_id = entry_id`/`intake_id`/`plan_entry_id`);
  `FastingWindow` is one instance **per user** (`aggregate_id = user_id`),
  because only it has a cross-instance invariant (no overlapping open
  windows) that must be enforced transactionally against all of a user's
  windows.
- Single `diary_events` table, discriminated by `aggregate_type`, shared
  by one `PostgresEventStore` across all 4 aggregate types
  (`infrastructure/persistence/postgres_event_store.py`). `append()` takes
  an `expected_version` and relies on a unique index on
  `(aggregate_type, aggregate_id, aggregate_sequence)` to serialize
  concurrent writers -- the loser raises `OptimisticConcurrencyError`
  (`domain/ports/event_store_port.py`), never silently corrupts the
  stream.
- Never mutate a row in `diary_events` -- a correction/removal is always a
  new event, appended, never an UPDATE.
- **Async-projector-via-broker** (the freshly-justified deviation from
  `profile-service`'s synchronous-projection choice, implementation plan
  section 9.1): command handlers ONLY call `EventStorePort.append` +
  `OutboxRepositoryPort.enqueue` -- they never touch a projector directly.
  `infrastructure/messaging/diary_event_projector_consumer.py` is the
  separate process that subscribes to this service's own `diary.events`
  exchange and applies each event to the relevant projector(s) via the
  shared `apply_event_to_read_models()` helper -- the exact same helper
  `scripts/rebuild_read_models.py` uses for a from-scratch replay, so the
  two paths can never drift. This means `GET`/list/calendar/summary
  endpoints are eventually consistent with a just-completed write --
  expected, not a bug; every command handler's result already carries the
  entry's own just-written data.
- `daily_summary_view` is recomputed (not incrementally diffed) by
  re-aggregating `food_entries_view`/`water_intake_view`/
  `fasting_windows_view` whenever a relevant event lands
  (`infrastructure/persistence/projectors/daily_summary_projector.py`) --
  this requires the entity-specific projector to run first in the
  dispatch order, which both the consumer and the rebuild script enforce.
- `fasting_overlap_policy` (`domain/services/fasting_overlap_policy.py`)
  is a pure function, isolated from the `FastingWindow` aggregate, so it
  has its own dedicated unit tests independent of the aggregate's own
  invariant tests (test-plan section 1).
- Authentication (ADR-0022): every request's `Authorization: Bearer
  <token>` header carries a RS256 JWT issued by identity-service, verified
  **locally** via `shared_contracts.auth.jwt_verifier.JwtVerifier`
  (`packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`
  -- diary-service is its third consumer, after identity-service and
  profile-service), which fetches + caches (10-minute TTL)
  identity-service's published JWKS (`/.well-known/jwks.json`). No
  synchronous call back to identity-service on every request, only on a
  JWKS cache miss/expiry -- see
  `infrastructure/http/dependencies.py`'s `get_authenticated_user_id`.
- No synchronous call to `catalog-service`: a Food Entry's/Meal Plan
  Entry's `source` is an opaque, client-supplied discriminated snapshot
  (`domain/value_objects/food_source.py`) -- diary-service never validates
  `source_reference_id` against a live catalog. This is a settled scoping
  decision (implementation plan section 1), not an oversight.
- No `ProductAdded`/`ProductUpdated` consumer is built here (plan section
  9.4) -- `docs/events-catalog.md` names diary-service as a future
  consumer, deliberately not implemented: reconciling a logged snapshot
  against a later catalog correction may be the wrong behavior, not
  merely a deferred one.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s) -- note there is no
  separate "projector port": projection only ever happens inside
  infrastructure (the consumer / the rebuild script), never invoked by an
  application-layer command handler, so no domain-layer port is needed
  for it.
- Adapters: `infrastructure/persistence/` (event store, outbox, processed-
  events dedup, and the 5 read-model projectors under
  `infrastructure/persistence/projectors/`), `infrastructure/cache/`
  (Redis daily-summary cache-aside), `infrastructure/messaging/`
  (RabbitMQ publisher, outbox relay worker, projector consumer).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. The
  rebuild-from-events test per aggregate lives under
  `tests/unit/domain/test_<aggregate>.py`; the projector-replay test per
  read model and the projector-consumer idempotency test live under
  `tests/integration/infrastructure/`.
