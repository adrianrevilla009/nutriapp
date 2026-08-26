# diary-service

NutriApp's primary transactional write path: food logging, water intake,
fasting windows, and weekly meal planning. Full event sourcing + CQRS
(ADR-0002) -- the third service in the repo to use this pattern, and the
second ES/CQRS service after `profile-service` (see `CLAUDE.md` in this
directory for the deliberate deviations this service makes from that
precedent).

## Bounded context

Logging a food entry against a `catalog-service` product reference or a
`food-recognition-service`-detected item (photo or barcode -- reserved
`source_type` values, not yet exercised by any adapter), with quantity and
meal slot; logging water intake and intermittent fasting windows;
scheduling planned (future) meal entries distinct from the as-eaten log;
correcting or deleting a previous entry as new events, never as a
destructive update to history; and building/maintaining the read-model
projections used by the frontend and by downstream consumers
(`nutrition-calculation-service`, `analytics-service`). No product
inventory (`catalog-service`'s domain), no macro/micro calculation
(`nutrition-calculation-service`'s domain).

## Event sourcing model

- **Mixed aggregate granularity** (implementation plan section 2, the
  first precedent of this shape in the repo): `FoodEntry`,
  `WaterIntakeEntry`, and `MealPlanEntry` are each **one aggregate
  instance per logged/planned item** (`aggregate_id = entry_id` /
  `intake_id` / `plan_entry_id`) -- no cross-instance invariant exists for
  these three, so each item's own append-only stream stays narrow to
  maximize write concurrency. `FastingWindow` is **one aggregate instance
  per user** (`aggregate_id = user_id`), holding that user's set of
  windows as entities within the aggregate, because the "no overlapping
  windows" invariant must be enforced transactionally against *all* of a
  user's windows.
- **Single `diary_events` table**, discriminated by `aggregate_type`
  (`food_entry | water_intake_entry | fasting_window | meal_plan_entry`),
  shared by one `PostgresEventStore` adapter across all 4 aggregate types
  -- a pragmatic intra-service normalization call (plan section 9.5), not
  a violation of CLAUDE.md section 2.5's "no shared schemas across
  service boundaries."
- **Async-projector-via-broker** (plan section 9.1, the freshly-justified
  choice against `profile-service`'s synchronous deviation): command
  handlers only append to `diary_events` and enqueue to `outbox` --
  `infrastructure/messaging/diary_event_projector_consumer.py` is a
  RabbitMQ consumer of this service's own published events, dispatching
  each to the relevant projector(s). `GET /api/v1/diary/summary` and the
  list/calendar endpoints are therefore eventually consistent with a
  just-completed write; every command response returns the newly-created/
  -corrected entry's own data directly so the client isn't forced to
  immediately re-read a list/summary.
- Read models: `food_entries_view`, `water_intake_view`,
  `fasting_windows_view`, `meal_plan_view` (one current-state row per
  aggregate instance) and `daily_summary_view` (recomputed by
  re-aggregating the other four whenever a relevant event lands) -- all
  five disposable, rebuildable by replaying `diary_events`
  (`scripts/rebuild_read_models.py`).
- A correction or removal is always a new event -- `diary_events` rows are
  never mutated.

## Caching

`daily_summary_view` is the "hot aggregate" cached in Redis, cache-aside,
key `diary:{user_id}:summary:{date}`, TTL 60s. Invalidation is
event-driven: the projector consumer invalidates exactly the affected
`(user_id, date)` key immediately after updating Postgres for every event
that touches that day (`infrastructure/cache/redis_daily_summary_cache.py`).
A Redis outage fails **open** (falls through to Postgres), unlike
identity-service's rate limiter, which fails closed -- this cache isn't a
security control.

## Authentication

Per ADR-0022 and `docs/authorization-model.md` section 2: every request
carries an `Authorization: Bearer <token>` header with a RS256 JWT issued
by `identity-service`. This service verifies the token's signature and
expiry **locally**, using the shared
`shared_contracts.auth.jwt_verifier.JwtVerifier`
(`packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`)
against `identity-service`'s published JWKS
(`/.well-known/jwks.json`, cached with a bounded TTL) --
**no synchronous call back to identity-service on every request**, only on
a JWKS cache miss/expiry. diary-service is this verifier's third consumer
after identity-service (issuer) and profile-service. See
`infrastructure/http/dependencies.py`'s `get_authenticated_user_id` for
the FastAPI wiring. A missing/malformed/expired/tampered token, or a
JWKS-fetch failure, all fail closed as `401`. Cross-user access to another
user's entry_id/intake_id/plan_entry_id fails as `403`
(`FoodEntryAccessDeniedError` and siblings); a fasting-window `window_id`
that doesn't belong to the caller's own per-user aggregate fails as `404`
(`WindowNotFoundError`) since it's scoped out at the aggregate-load level,
not a separate ownership check.

## Running locally

```
docker compose up diary-service diary-db diary-redis rabbitmq
```

See root `docker-compose.yml` for required environment variables
(`DIARY_SERVICE_DATABASE_URL`, `DIARY_SERVICE_RABBITMQ_URL`,
`DIARY_SERVICE_REDIS_URL`, `DIARY_SERVICE_IDENTITY_JWKS_URL` /
`DIARY_SERVICE_IDENTITY_ISSUER` for the JWT verifier -- defaults to
`http://identity-service:8000/.well-known/jwks.json` / `identity-service`,
matching the docker-compose service name).

## Testing

```
cd services/diary-service
uv sync --extra dev
uv run pytest tests/unit                       # domain + application, no I/O
uv run pytest tests/integration                # testcontainers: Postgres, RabbitMQ, Redis
uv run pytest tests/contract                    # HTTP + event schema contracts
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage targets (CLAUDE.md section 3): domain >= 90%, application >= 85%,
infrastructure >= 70%.

Event-sourcing-specific test categories (test-plan section 5, all
present): a rebuild-from-events test per aggregate
(`tests/unit/domain/test_food_entry.py` and siblings, plus
`test_fasting_window.py`'s full-replay case for the one aggregate with a
genuinely stateful derived collection), a projector-replay test per read
model (`tests/integration/infrastructure/test_postgres_*_projector.py`),
an idempotency test for the projector consumer
(`test_diary_event_projector_consumer.py`), and a concurrent-append test
proving the single event-store table's optimistic-concurrency guard
actually serializes two racing writers (`test_postgres_event_store.py`).

## Read-model rebuild (runbook)

All 5 read models are disposable projections -- they can always be
rebuilt from `diary_events`, the source of truth. To actually do so (e.g.
after a projector bug is fixed and historical rows need to be
reprojected, or to stand up a fresh read-model database):

```
cd services/diary-service
DIARY_SERVICE_DATABASE_URL=postgresql+asyncpg://... python -m scripts.rebuild_read_models
```

This truncates all 5 read-model tables and replays every row in
`diary_events`, grouped by `(aggregate_type, aggregate_id)` and ordered
chronologically within each group (by the monotonic `sequence` column,
never `occurred_at`), through the exact same
`apply_event_to_read_models()` helper the live async consumer uses --
`scripts/rebuild_read_models.py`. Do not run this against a database with
concurrent writers without first pausing the write path -- see the
script's module docstring.

## Resilience configuration

This service has one synchronous external dependency: identity-service's
JWKS endpoint (JWT verification, fetched only on a cache miss/expiry, not
per request), already resilience-configured (circuit breaker + retry +
timeout) in `packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`
-- diary-service is simply its second-generation caller, no new
resilience work required here (implementation plan section 7). It makes
no synchronous call to `catalog-service` (the food-entry/meal-plan
`source` is an opaque, client-supplied snapshot -- settled scoping
decision, plan section 1) and consumes no events from any other service
in this plan's scope (plan section 9.4).

- `processed_inbound_events` dedup TTL: 7 days -- comfortably longer than
  any realistic RabbitMQ redelivery window, short enough that a periodic
  cleanup (follow-up, not implemented) keeps the table bounded.
- `diary_event_projector_consumer`: failed messages are retried up to 5
  times (`x-diary-retry-count` header, manually incremented on republish),
  then routed to `diary-service.diary_event_projector.dlq` instead of
  being retried forever or dropped silently.
- `OutboxRelayWorker`: polls every 2s, publishes and marks-published one
  event at a time so a crash mid-relay never loses an event or
  republishes an already-published row.

## Owned events (see docs/events-catalog.md)

- `FoodEntryLogged` / `FoodEntryCorrected` / `FoodEntryDeleted` (v1).
- `WaterIntakeLogged` / `WaterIntakeRemoved` (v1).
- `FastingWindowStarted` / `FastingWindowEnded` (v1).
- `MealPlanned` / `MealPlanUpdated` / `MealPlanRemoved` (v1).

Documented future consumers: `nutrition-calculation-service`,
`analytics-service` (neither exists yet -- no live cross-service contract
test runs against them, only a payload-shape contract test against each
entry, per `packages/shared-contracts/schemas/*.v1.json`).

## Consumed events

None in this plan (implementation plan section 9.4). `catalog-service`'s
`ProductAdded`/`ProductUpdated` consumption is deliberately deferred, not
built: a food entry's `source.snapshot` is a point-in-time record of what
the user logged, not a live mirror of the catalog.

## Dependencies

- PostgreSQL (own logical database within the shared RDS instance).
- Redis (shared ElastiCache cluster, `diary:*` key namespace) --
  cache-aside for `daily_summary_view` only; a Redis outage degrades
  gracefully to always reading Postgres.
- RabbitMQ (outbox relay -> `diary.events` topic exchange; the
  `diary_event_projector_consumer` also subscribes to that same exchange,
  binding `diary.#`).
