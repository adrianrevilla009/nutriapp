# Implementation Plan — `diary-service`

**Status:** Approved
**Date approved:** 2026-08-26
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0002 (CQRS/ES scope), `.claude/agents/diary-agent.md`, `.claude/skills/cqrs-event-sourcing/SKILL.md`, `/plans/profile-service/implementation-plan.md` (prior-art ES/CQRS reference — cited, not copied, per that skill's explicit instruction), `/plans/identity-service/implementation-plan.md` and `/plans/platform-infra/implementation-plan.md` (shared platform scaffolding reused as-is), `docs/domain-glossary-and-context-map.md`, `docs/events-catalog.md`

## 1. Scope

Build `diary-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding (`infra/k8s/charts/_lib/`, shared RDS instance, root `docker-compose.yml`/`Makefile`, `packages/shared-contracts`'s `JwtVerifier`) established by `identity-service` and `profile-service`. No new platform-level infra needed.

**Bounded context** (per `.claude/agents/diary-agent.md`, CLAUDE.md §2.2): the product's primary transactional write path — logging food entries, water intake, fasting windows, and planned meals. Four aggregates: **Food Entry**, **Water Intake Entry**, **Fasting Window**, **Meal Plan Entry**.

**Acceptance criteria:**
1. `POST /api/v1/diary/food-entries` — product reference + quantity + meal slot + timestamp → `FoodEntryLogged` appended → read models updated (asynchronously, see §2/§9.1).
2. `PATCH /api/v1/diary/food-entries/{entry_id}` — corrects a previously logged food entry via a new `FoodEntryCorrected` event — never mutates the stored `FoodEntryLogged` row.
3. `POST /api/v1/diary/water-intake` / `DELETE /api/v1/diary/water-intake/{intake_id}` — log and remove water intake entries (`WaterIntakeLogged` / `WaterIntakeRemoved`), removal as a new event, never a row delete.
4. `POST /api/v1/diary/fasting-windows/start` / `POST /api/v1/diary/fasting-windows/{window_id}/end` — start/end a fasting window (`FastingWindowStarted` / `FastingWindowEnded`); starting a window while the same user already has an open (unended) window is rejected as a domain invariant violation (`OverlappingFastingWindowError`).
5. `POST /api/v1/diary/meal-plan` / `PATCH /api/v1/diary/meal-plan/{plan_entry_id}` / `DELETE /api/v1/diary/meal-plan/{plan_entry_id}` — create/update/remove a planned (future) meal entry (`MealPlanned` / `MealPlanUpdated` / `MealPlanRemoved`), distinct from an as-eaten Food Entry.
6. Every state change is a named, versioned domain event (envelope per `cqrs-event-sourcing` SKILL.md: `event_id`, `aggregate_id`, `event_type`, `version`, `occurred_at`, `payload`, `metadata`), appended to an event store, outbox-relayed to RabbitMQ atomically with the append.
7. Each aggregate's state is fully rebuildable by replaying its event stream, backed by an actual runnable rebuild script (`scripts/rebuild_read_models.py`, mirroring `services/profile-service/scripts/rebuild_read_models.py`), not just a docstring claim.
8. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3), including a rebuild-from-events test per aggregate, a projector-replay test per read model, and an idempotency test for the internal projector consumer.

**Settled scoping constraint carried into this plan without relitigation:** Food Entry's (and Meal Plan Entry's) product/source reference is opaque and client-supplied — a `source_type` discriminator (`catalog_product` now; `recipe`/`ai_detected` reserved for later) carrying an opaque `source_reference_id` plus a denormalized snapshot (name, brand, per-unit macros as supplied by the client at logging time). `diary-service` makes no synchronous call to `catalog-service` or any other service to validate this reference.

## 2. Architectural classification

Per ADR-0002 and `.claude/agents/diary-agent.md`: **full event sourcing + CQRS**, the third service in the repo and the **second** ES/CQRS service (after `profile-service`), the one whose higher write volume forces this service to make its own freshly-justified call on the sync-vs-async projection axis rather than inherit `profile-service`'s deviation (`.claude/skills/cqrs-event-sourcing/SKILL.md`, "Deviation" section) — resolved in §9.1 in favor of the **async-projector-via-broker default**. All three hexagonal layers are touched.

Unlike `profile-service` (one aggregate type, one aggregate instance per user), `diary-service` uses **mixed aggregate granularity**, a deliberate deviation flagged for `architecture-agent` in §6:
- **Food Entry**, **Water Intake Entry**, **Meal Plan Entry**: one aggregate instance **per logged/planned item** (`aggregate_id` = `entry_id` / `intake_id` / `plan_entry_id`, a client- or server-generated UUID). No cross-instance invariant exists for these three, so keeping each item's own append-only stream narrow maximizes write concurrency — critical given this service's write volume is the highest in the system.
- **Fasting Window**: one aggregate instance **per user** (`aggregate_id` = `user_id`), holding the set of that user's fasting windows as entities within the aggregate. This is required because the "no overlapping windows" invariant (AC 4) must be enforced transactionally against *all* of a user's windows, which is only possible if they share one consistency boundary — see §9.2 for the overlap-check design detail.

## 3. Files to create or modify

```
services/diary-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_diary_tables.py
      # diary_events (single event store table, aggregate_type-discriminated:
      #   food_entry | water_intake_entry | fasting_window | meal_plan_entry),
      # outbox, processed_inbound_events,
      # daily_summary_view, food_entries_view, water_intake_view,
      # fasting_windows_view, meal_plan_view (read models)

  domain/
    entities/food_entry.py                    # aggregate root, aggregate_id=entry_id
    entities/water_intake_entry.py             # aggregate root, aggregate_id=intake_id
    entities/fasting_window.py                 # aggregate root, aggregate_id=user_id,
                                                # holds a collection of window entities
    entities/meal_plan_entry.py                # aggregate root, aggregate_id=plan_entry_id
    value_objects/quantity.py                  # amount + unit (g/ml/serving)
    value_objects/meal_slot.py                 # enum: breakfast/lunch/dinner/snack
    value_objects/food_source.py               # source_type discriminator +
                                                # source_reference_id + snapshot
                                                # (shared by Food Entry and Meal Plan Entry)
    value_objects/macro_snapshot.py            # denormalized per-unit macro fields
    value_objects/water_amount_ml.py
    value_objects/time_window.py               # start/end + overlap predicate helper
    events/base.py                             # DomainEvent envelope, mirrors
                                                # profile-service's domain/events/base.py
    events/food_entry_logged.py
    events/food_entry_corrected.py
    events/food_entry_deleted.py
    events/water_intake_logged.py
    events/water_intake_removed.py
    events/fasting_window_started.py
    events/fasting_window_ended.py
    events/meal_planned.py
    events/meal_plan_updated.py
    events/meal_plan_removed.py
    ports/event_store_port.py                  # generic, aggregate_type-parameterized
    ports/daily_summary_read_port.py
    ports/food_entries_read_port.py
    ports/water_intake_read_port.py
    ports/fasting_windows_read_port.py
    ports/meal_plan_read_port.py
    ports/daily_summary_cache_port.py          # Redis cache-aside port
    ports/event_publisher_port.py
    ports/outbox_repository_port.py
    ports/processed_events_port.py
    services/fasting_overlap_policy.py         # enforces the no-overlap invariant

  application/
    commands/log_food_entry.py                       (+ handler)
    commands/correct_food_entry.py                    (+ handler)
    commands/delete_food_entry.py                     (+ handler)
    commands/log_water_intake.py                      (+ handler)
    commands/remove_water_intake.py                   (+ handler)
    commands/start_fasting_window.py                  (+ handler)
    commands/end_fasting_window.py                    (+ handler)
    commands/plan_meal.py                             (+ handler)
    commands/update_meal_plan.py                      (+ handler)
    commands/remove_meal_plan.py                      (+ handler)
    queries/get_daily_summary.py                      (+ handler; cache-aside via
                                                         DailySummaryCachePort, falls
                                                         through to DailySummaryReadPort)
    queries/list_food_entries.py                      (+ handler)
    queries/list_water_intake.py                      (+ handler)
    queries/get_fasting_history.py                    (+ handler)
    queries/get_meal_plan_calendar.py                 (+ handler)
    dto/

  infrastructure/
    http/routes/food_entry_routes.py
    http/routes/water_intake_routes.py
    http/routes/fasting_window_routes.py
    http/routes/meal_plan_routes.py
    http/routes/daily_summary_routes.py
    http/schemas/
    http/dependencies.py                # get_authenticated_user_id, reusing
                                         # shared_contracts.auth.jwt_verifier.JwtVerifier
                                         # against identity-service's JWKS — diary-service
                                         # is JwtVerifier's second consumer after
                                         # profile-service, no new code needed in the
                                         # shared package
    http/error_mapping.py
    http/health.py
    messaging/rabbitmq_event_publisher.py
    messaging/outbox_relay_worker.py
    messaging/diary_event_projector_consumer.py
        # single consumer subscribing to diary.events, dedups via
        # ProcessedEventsPort, dispatches each event by event_type to the
        # relevant projector(s) below (one event can feed more than one
        # read model, e.g. FoodEntryLogged -> food_entries_view AND
        # daily_summary_view)
    persistence/models.py
    persistence/postgres_event_store.py           # EventStorePort adapter, shared by
                                                    # all 4 aggregate repositories
    persistence/postgres_outbox_repository.py
    persistence/postgres_processed_events_repository.py
    persistence/projectors/daily_summary_projector.py
    persistence/projectors/food_entries_projector.py
    persistence/projectors/water_intake_projector.py
    persistence/projectors/fasting_windows_projector.py
    persistence/projectors/meal_plan_projector.py
    cache/redis_daily_summary_cache.py             # DailySummaryCachePort adapter
    composition_root.py
    main.py

  scripts/rebuild_read_models.py
      # truncates all 5 read-model tables, replays diary_events grouped by
      # (aggregate_type, aggregate_id) then chronologically (sequence, never
      # occurred_at) through the same projector apply() methods the async
      # consumer calls -- mirrors services/profile-service/scripts/rebuild_read_models.py

  tests/
    unit/domain/...       # rebuild tests per aggregate, value object tests,
                           # fasting_overlap_policy tests
    unit/application/...  # command/query handler tests against fake ports
    integration/infrastructure/...   # testcontainers Postgres + RabbitMQ + Redis:
                                      # event store, all 5 projectors (replay tests),
                                      # outbox relay, projector-consumer idempotency,
                                      # Redis cache-aside + invalidation
    contract/http/..., contract/events/...   # producer contracts for all 10 new
                                              # events; no consumer contract yet
                                              # (see §6/§9.4 -- ProductAdded/
                                              # ProductUpdated consumption deferred)
    fixtures/factories.py

infra/k8s/charts/diary-service/
  Chart.yaml, values.yaml, values-dev.yaml, values-staging.yaml, values-prod.yaml
  values.schema.json                 # included from day one, per profile-service's
                                      # addendum lesson (identity-service's original gap)
  ci/synthetic-values.yaml
  templates/ (built on infra/k8s/charts/_lib/, same as identity-service/profile-service)

infra/terraform/environments/dev/diary-service.tf
    # mirrors profile-service.tf's structure minus the KMS block (no per-user
    # envelope encryption needed -- diary data isn't classified as GDPR
    # Article 9 special-category data the way profile-service's biometric
    # data is; revisit only if that classification is ever revised) --
    # module.ecr_diary_service, _db-provision-job via Helm release,
    # ElastiCache Redis wiring (reuses the single shared infra/terraform/modules/elasticache
    # cluster via a diary:* key namespace, same resolution as catalog-service's
    # Addendum 1 -- no new ElastiCache cluster)

.github/workflows/diary-service-ci.yml
    # mirrors profile-service-ci.yml, including the helm-lint-and-template
    # job from the start

docker-compose.yml, Makefile          # add diary-service block / SERVICE=diary-service
                                       # target; wire diary-db, reuse shared rabbitmq,
                                       # add a diary-redis container for local dev parity

packages/shared-contracts/schemas/food_entry_logged.v1.json              # new
packages/shared-contracts/schemas/food_entry_corrected.v1.json           # new
packages/shared-contracts/schemas/food_entry_deleted.v1.json             # new
packages/shared-contracts/schemas/water_intake_logged.v1.json            # new
packages/shared-contracts/schemas/water_intake_removed.v1.json           # new
packages/shared-contracts/schemas/fasting_window_started.v1.json         # new
packages/shared-contracts/schemas/fasting_window_ended.v1.json           # new
packages/shared-contracts/schemas/meal_planned.v1.json                   # new
packages/shared-contracts/schemas/meal_plan_updated.v1.json              # new
packages/shared-contracts/schemas/meal_plan_removed.v1.json              # new
packages/shared-contracts/python/shared_contracts/events/diary.py        # new,
                                                                           # add the 10 above

docs/events-catalog.md      # replace the two existing unmarked placeholder entries
                             # ("FoodEntryLogged / FoodEntryCorrected / FoodEntryDeleted"
                             # and "WaterIntakeLogged / FastingWindowStarted /
                             # FastingWindowEnded / MealPlanned") with 10 concrete,
                             # separately-versioned entries (splitting MealPlanned out
                             # and adding WaterIntakeRemoved, MealPlanUpdated,
                             # MealPlanRemoved, which the placeholders didn't cover),
                             # each Status: Active once contract tests pass
docs/api-catalog.md         # /api/v1/diary/*: planned -> active
docs/domain-glossary-and-context-map.md   # no new terms needed -- Food Entry, Water
                             # Intake Entry, Fasting Window, Meal Plan Entry are
                             # already defined there; confirm wording still matches
```

## 4. Ports/adapters affected

| Port (domain) | Adapter (infrastructure) |
|---|---|
| `EventStorePort` (generic, `aggregate_type`-parameterized: append/load stream) | `PostgresEventStore` — single adapter shared by all 4 aggregate repositories (§6 flags this consolidation for review) |
| `DailySummaryReadPort` | `PostgresDailySummaryProjector` (write+read side of `daily_summary_view`) |
| `FoodEntriesReadPort` | `PostgresFoodEntriesProjector` |
| `WaterIntakeReadPort` | `PostgresWaterIntakeProjector` |
| `FastingWindowsReadPort` | `PostgresFastingWindowsProjector` |
| `MealPlanReadPort` | `PostgresMealPlanProjector` |
| `DailySummaryCachePort` | `RedisDailySummaryCache` — cache-aside, event-driven invalidation (§7) |
| `EventPublisherPort` | `RabbitMqEventPublisher` (faststream) — new instance, same pattern as `identity-service`/`profile-service` |
| `OutboxRepositoryPort` | `PostgresOutboxRepository` + `OutboxRelayWorker` — new instance, own outbox table (CLAUDE.md §2.5, no shared schemas) |
| `ProcessedEventsPort` | `PostgresProcessedEventsRepository` — dedup for `diary_event_projector_consumer`, per `.claude/skills/messaging-conventions/SKILL.md` |

All new. No new adapter needed for authentication: `infrastructure/http/dependencies.py` reuses `shared_contracts.auth.jwt_verifier.JwtVerifier` exactly as `profile-service` wired it (ADR-0022), diary-service is simply its second caller.

## 5. Domain events

All follow the envelope in `.claude/skills/cqrs-event-sourcing/SKILL.md`. `source` below is the shared, minimally-generic discriminated shape used by both Food Entry and Meal Plan Entry:
```json
"source": {
  "source_type": "catalog_product",
  "source_reference_id": "uuid",
  "snapshot": {
    "name": "string",
    "brand": "string | null",
    "quantity": "number",
    "unit": "string (g|ml|serving)",
    "macros_per_unit": { "calories_kcal": "number", "protein_g": "number",
                          "carbs_g": "number", "fat_g": "number" }
  }
}
```
(`source_type` reserves `recipe` and `ai_detected` for later services; no port/adapter is built for those now, per the approved scoping decision.)

- **`FoodEntryLogged` (v1, new)** — `{ "entry_id", "user_id", "source": {...above}, "meal_slot": "breakfast|lunch|dinner|snack", "occurred_at" }`
- **`FoodEntryCorrected` (v1, new)** — same shape as `FoodEntryLogged` (full replacement of the correctable fields — `source`/`meal_slot`/`occurred_at`), plus `corrected_at`. Never mutates the original `FoodEntryLogged` row; a projector interprets the pair.
- **`FoodEntryDeleted` (v1, new)** — `{ "entry_id", "user_id", "deleted_at" }`
- **`WaterIntakeLogged` (v1, new)** — `{ "intake_id", "user_id", "amount_ml": "number", "occurred_at" }`
- **`WaterIntakeRemoved` (v1, new)** — `{ "intake_id", "user_id", "removed_at" }`
- **`FastingWindowStarted` (v1, new)** — `{ "window_id", "user_id", "started_at" }`
- **`FastingWindowEnded` (v1, new)** — `{ "window_id", "user_id", "ended_at" }`
- **`MealPlanned` (v1, new)** — `{ "plan_entry_id", "user_id", "source": {...above}, "meal_slot", "planned_for": "timestamp" }`
- **`MealPlanUpdated` (v1, new)** — same shape as `MealPlanned`, plus `updated_at`
- **`MealPlanRemoved` (v1, new)** — `{ "plan_entry_id", "user_id", "removed_at" }`

These replace the two existing unmarked placeholder entries in `docs/events-catalog.md` (the combined `FoodEntryLogged / FoodEntryCorrected / FoodEntryDeleted` entry and the combined `WaterIntakeLogged / FastingWindowStarted / FastingWindowEnded / MealPlanned` entry) with 10 concrete, separately-versioned entries — also correcting the placeholder's `product_id`/`detection_id` fields, which predate the now-settled opaque-`source`-discriminator design, and adding three event types (`WaterIntakeRemoved`, `MealPlanUpdated`, `MealPlanRemoved`) the placeholders never named. Requires `architecture-agent` concurrence (this is the first concrete payload shape for the `source_type` discriminator that a future `catalog-service`/`recipe-service`/`food-recognition-service` plan will need to either conform to or upcast against) and confirmation from `nutrition-calculation-agent`/`analytics-agent` (documented consumers, per `docs/domain-glossary-and-context-map.md`) that the shapes don't collide with their planned integration.

**No events consumed in this plan.** `docs/events-catalog.md` and `.claude/agents/diary-agent.md` both name `diary-service` as a future consumer of `catalog-service`'s `ProductAdded`/`ProductUpdated` — deliberately out of scope here since `catalog-service` doesn't exist yet and the opaque-`source`-snapshot design doesn't require it for these acceptance criteria. See §9.4.

## 6. Cross-service impact — flagged for `architecture-agent`

- **Third service, second ES/CQRS service** — does `profile-service`'s pattern generalize, or does `diary-service`'s higher write volume force real deviations? It forces three, all deliberate and documented here rather than left implicit:
  1. **Mixed aggregate granularity** (per-entry for Food Entry/Water Intake/Meal Plan, per-user for Fasting Window) instead of `profile-service`'s uniform per-user aggregate (§2). This is the first precedent in the repo for a mixed-granularity ES design — worth explicit sign-off since a future service (e.g. `activity-service`) may face the same "most instances are independent, one sub-concept has a cross-instance invariant" shape.
  2. **Async-projector-via-broker chosen over `profile-service`'s sync-same-transaction deviation** (§9.1) — the freshly-justified choice the skill explicitly required.
  3. **Single `diary_events` table with an `aggregate_type` discriminator**, shared by one `PostgresEventStore` adapter across all 4 aggregate types, rather than one dedicated event-store table+adapter per aggregate (which is what `profile-service`, with only one aggregate type, never had to choose between). This is an intra-service normalization call, not a violation of CLAUDE.md §2.5's "no shared schemas *across service boundaries*" — but it is a new pattern worth confirming before a service with even more aggregate types copies it uncritically.
- `nutrition-calculation-service` and `analytics-service` are documented consumers of all 10 events but don't exist yet — no live integration to break, but the `source` discriminator shape decided here becomes their contract, and is also the first concrete shape `catalog-service`'s parallel-in-progress plan needs to be aware doesn't collide with its own product-identifier design (it doesn't — `catalog-service`'s `product_id` is exactly the opaque `source_reference_id` this plan expects).
- `food-recognition-service` will eventually need `source_type: "ai_detected"` — not built now, but the discriminator's shape is generic enough to accommodate it later without an aggregate redesign.
- **Deferred, not resolved**: `diary-agent.md`'s testing requirement mentions a `ProductAdded`/`ProductUpdated` consumer with an explicit idempotency test — this plan does not build that consumer (see §9.4). Flag to `architecture-agent` whether `diary-agent.md` should be updated now to reflect the opaque-snapshot decision, or left as forward-looking guidance for a later plan.

## 7. Resilience/caching/migration needs

- **No new synchronous external dependency.** Per the settled scoping decision, `diary-service` makes no synchronous call to `catalog-service`. Its only synchronous outbound dependency is `identity-service`'s JWKS endpoint for JWT verification (cache-miss/expiry only) — already built and resilience-configured (circuit breaker + retry + timeout) in `packages/shared-contracts/python/shared_contracts/auth/jwt_verifier.py`; `diary-service` just becomes its second consumer, no new resilience work required here.
- **Caching** (`.claude/skills/caching-strategy/SKILL.md`, CLAUDE.md §2.7): `daily_summary_view` is the "hot aggregate" for Redis caching — cache-aside, keyed `diary:{user_id}:summary:{date}`, event-driven invalidation (the `daily_summary_projector` refreshes/invalidates the Redis key for the affected `user_id`+date immediately after updating the Postgres row for every event that touches that day). TTL: 60s (short, given the "today" screen's near-real-time expectation) — pinned down here rather than left to `/test-plan`.
- **Migration**: first Alembic migration, `CREATE TABLE`-only (event store, outbox, dedup table, 5 read-model tables) — additive, does not trigger the destructive-change approval gate (`.claude/skills/database-migrations/SKILL.md`).
- **Terraform**: mirrors `profile-service.tf` minus its KMS block (no per-user envelope encryption needed here); Redis reuses the single shared `infra/terraform/modules/elasticache` cluster via a `diary:*` key namespace (same resolution as `catalog-service`'s Addendum 1 — no new ElastiCache cluster), plus its own ECR repo via `infra/terraform/modules/ecr`.
- **Outbox**: mandatory (CLAUDE.md §2.4), same append-then-enqueue-in-one-transaction pattern as `identity-service`/`profile-service`, own outbox table and relay worker (no shared schema).

## 8. Test plan reference

See `/plans/diary-service/test-plan.md`.

## 9. Risks and open questions

**9.1 — Sync-same-transaction vs. async-projector-via-broker projection — resolved: async.**
Reasoning: (1) write volume — CLAUDE.md §2.2 itself calls diary logging "the core actions users repeat most often," an order of magnitude more frequent than `profile-service`'s occasional metric/goal writes; (2) 5 read models vs. `profile-service`'s 2 — more projection work per write if synchronous; (3) cross-service consumers (`nutrition-calculation-service`, `analytics-service`) already require the async/outbox path regardless, so making the internal projector just another consumer of that same published stream avoids maintaining two different delivery/consistency models for the same events. Trade-off accepted explicitly: `GET /api/v1/diary/summary` is only eventually consistent with a just-completed write; command responses return the newly-created/-corrected entry's data directly so the client isn't forced to immediately re-read the summary, and the frontend tolerates a short, consumer-lag-bounded staleness window — a normal CQRS trade-off, not a defect.

**9.2 — Fasting-window overlap-check implementation — resolved: (a) simple open-window check.**
Reject `FastingWindowStarted` if the user's aggregate already has a window with `started_at` set and no `ended_at`. O(1) against derived state, matches the "start...end" stopwatch phrasing (only ever one open window at a time). Full interval-overlap checking against historical closed windows (needed only if retroactive dual-timestamp logging is added later) is an additive future extension, not designed now.

**9.3 — Meal-plan-entry vs. food-entry linkage on "eaten" — explicitly out of scope, forward-compatibility seam only.**
`FoodEntryLogged`'s payload reserves an optional, nullable `planned_from_entry_id: uuid | null` field (additive, unused by any command in this plan) as a seam for a future "log from plan" workflow. Not populated or read by anything in this implementation.

**9.4 — `ProductAdded`/`ProductUpdated` consumption deferred, not built.**
`.claude/agents/diary-agent.md` and `docs/events-catalog.md` describe `diary-service` as a future consumer of `catalog-service`'s catalog events. Not built here: under the opaque-`source`-snapshot design, a food entry's snapshot is a point-in-time record of what the user logged, not a live mirror of the catalog — silently reconciling snapshots against a later catalog correction may be the wrong behavior, not merely a deferred one. Flagged for `architecture-agent` to decide whether `diary-agent.md`/`docs/events-catalog.md` should be corrected now or left for a dedicated future plan once `catalog-service` ships and this question can be answered with a real catalog event stream to design against.

**9.5 — Single consolidated event-store table — pragmatic default, revisit only if warranted by measured contention/index bloat in `staging`, per CLAUDE.md's no-speculative-infrastructure posture.**

**9.6 — `meal_slot`/quantity-unit vocabulary — pinned down for `/test-plan`:** `meal_slot` enum is `breakfast|lunch|dinner|snack`; `quantity` unit vocabulary is `g|ml|serving`. Assumed defaults, flagged for correction if wrong, mirroring `profile-service`'s `goal_policy` §9.3 precedent for this kind of deferral.

---

## Addendum 1 — 2026-08-26, approval and execution authorization

Approved as submitted, with the above open questions resolved as stated (9.1 async, 9.2 simple open-window check, 9.6 vocabulary pinned). No changes to the plan's scope, files, ports, or events were required.

**Human authorization for straight-through execution.** The product owner approved this plan and the accompanying test plan together and authorized proceeding directly through `/implementation-execution` and `/test-execution` without an additional per-stage pause, to be reviewed as a completed body of work afterward. This does **not** waive CLAUDE.md §7: no `git push`, no PR, and no merge happen as part of this authorization — the branch is left committed locally, unpushed, for human review.
