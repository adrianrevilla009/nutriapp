# Implementation Plan — `nutrition-calculation-service`

**Status:** Approved
**Date approved:** 2026-08-26
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — correction proposed, see §6(a)/§9.4), ADR-0004 (messaging backbone), ADR-0022 (JWT/JWKS), ADR-0023 (per-service encryption key ownership — directly implicated, see §6(d)/§9.1), `.claude/agents/nutrition-calculation-agent.md`, `.claude/skills/domain-calculation-conventions/SKILL.md` (mandatory), `.claude/skills/messaging-conventions/SKILL.md`, `.claude/skills/caching-strategy/SKILL.md`, `.claude/skills/cqrs-event-sourcing/SKILL.md`, `docs/domain-glossary-and-context-map.md`, `docs/events-catalog.md`, `/plans/catalog-service/implementation-plan.md` (structural precedent), `/plans/profile-service/implementation-plan.md` and `/plans/diary-service/implementation-plan.md` (cross-reference — inbound event payload shapes)

## 1. Scope

Build `nutrition-calculation-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding (`infra/k8s/charts/_lib/`, shared RDS instance, shared ElastiCache cluster, root `docker-compose.yml`/`Makefile`) established by `identity-service`/`catalog-service`. No new platform-level infra needed.

**Bounded context** (per `.claude/agents/nutrition-calculation-agent.md` / CLAUDE.md §2.2): computation of macro/micronutrient totals from `diary-service`'s logged entries plus `catalog-service`'s reference nutrient data, and computation of personalized calorie/macro targets from `profile-service`'s biometric metrics and goals via Mifflin-St Jeor. This service owns no logging state, no product data, and no auth — it is a pure computation/derivation service reacting to three upstream producers' events.

**Acceptance criteria:**

1. **Nutrient totals — per entry and per day.** `nutrient_amount = (per_100g_value / 100) × quantity_grams`, summed across contributing entries for the requested window. Macros come directly from `diary-service`'s `FoodEntryLogged`/`FoodEntryCorrected` payload (`source.snapshot.macros_per_unit`); no synchronous catalog lookup. Micronutrients are joined from this service's own local, denormalized mirror of `catalog-service`'s nutrient panel (built by consuming `ProductCatalogued`/`ProductUpdated`), keyed by `source_reference_id`, only when `source.source_type == "catalog_product"`. When there is no mirror match yet, the micronutrient portion is marked `"unavailable"` explicitly, never estimated.
2. **Goal-setting engine.**
   - BMR — Mifflin-St Jeor (Mifflin MD et al., *Am J Clin Nutr*, 1990): `(10 × weight_kg) + (6.25 × height_cm) − (5 × age) + 5` (male) / `... − 161` (female).
   - TDEE = `BMR × activity_factor`, per the 5-tier PAL table in §9.2.
   - Calorie target = `TDEE ± goal_adjustment`, clamped to the safety bounds in §9.3.
   - Macro repartition: protein 1.6–2.2 g/kg body weight, fat ≥ 20% of calories, carbs = remainder.
   - Reserved, not built this pass: `activity_adjustment_kcal` (seam for `activity-service`) and `confidence_range` (seam for `food-recognition-service`) — fields exist, no port/adapter built.
3. **Recomputation triggers**: `FoodEntryLogged`/`FoodEntryCorrected`/`FoodEntryDeleted` (diary-service) → recompute entry/day totals. `WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated` (profile-service) → recompute target.
4. **Idempotent recomputation**: replaying the same triggering event twice must not double-apply a target update or double-count a total, and must not double-publish either output event.
5. Every recomputation persists conventionally (upsert by natural key) and publishes `NutritionValueRecomputed`/`NutritionTargetUpdated` via the Outbox, and appends to a target-history table.
6. Mutation testing recommended (advisory, not merge-blocking) for the domain layer. Coverage: domain ≥ 90% (hard floor), application ≥ 85%, infrastructure ≥ 70%.
7. Every formula cites its source; every user-facing computed result is framed as an informational estimate, never medical nutrition therapy (CLAUDE.md §8); no false precision.

**Explicitly out of scope for this plan:**
- `activity-service`'s TDEE adjustment and `food-recognition-service`'s confidence-range carry-through — no upstream events exist yet.
- Any synchronous call to `catalog-service` for nutrient data — always the local mirror.
- A bulk reprocessing job for "recompute all historical values after a formula correction" — reserved (`formula_version`), not built speculatively.

## 2. Architectural classification

**Event-driven CRUD**, per `.claude/agents/nutrition-calculation-agent.md` and `.claude/skills/cqrs-event-sourcing/SKILL.md` — not full event sourcing. Current computed totals/target are stored conventionally (upsert by natural key), with a separate append-only `nutrition_target_history` table for the timeline. Every recomputation still publishes events via the Outbox, matching `catalog-service`'s pattern, not `profile-service`'s event-sourced aggregate/projector pair.

**ADR-0002's literal Decision text is stale and contradicts this** (see §6(a)/§9.4 for the correction). CLAUDE.md §2.3, the agent doc, and the cqrs-event-sourcing skill all agree with this plan's classification.

Structurally this is the closest match to `catalog-service`'s shape. It is the first service in the repo with **three simultaneous live inbound event dependencies**, and the first to maintain **two separate local, denormalized, read-only mirrors** of other services' data inside one service.

## 3. Files to create or modify

```
services/nutrition-calculation-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_nutrition_calculation_tables.py
      # nutrition_targets (current, one row per user, upsert)
      # nutrition_target_history (append-only timeline)
      # daily_nutrition_totals (current, one row per user+date, upsert)
      # nutrient_panel_mirror (local read-only mirror of catalog-service's
      #   nutrient panel, keyed by source_reference_id/barcode)
      # user_metrics_snapshot (per security-agent's sub-addendum requirement 8:
      #   metadata only -- last_fetched_at, formula_version used, which sex
      #   constant was applied for OTHER -- NEVER the raw weight/height/age/sex
      #   plaintext, which is fetched fresh from ProfileRevealPort at each
      #   recompute and never persisted here; derived scalars like bmr_kcal MAY
      #   be cached with a short documented TTL if performance requires it)
      # outbox
      # processed_events (dedup keyed by (consumer_name, event_id), shared
      #   across all 3 inbound consumers)

  domain/
    entities/daily_nutrition_total.py
    entities/nutrition_target.py
    value_objects/sex.py                      # own copy; MALE|FEMALE|OTHER;
                                                # OTHER handling per Addendum 1
                                                # (explicit user selection, see 9.8)
    value_objects/activity_level.py            # own copy (SEDENTARY..VERY_ACTIVE)
    value_objects/goal_type.py                 # own copy (LOSE|MAINTAIN|GAIN)
    value_objects/formula_version.py
    value_objects/calorie_target_bounds.py     # per Addendum 1 / section 9.3
    value_objects/macro_target_range.py
    value_objects/nutrient_total_line.py
    value_objects/confidence_range.py          # reserved, unused this pass
    events/nutrition_value_recomputed.py
    events/nutrition_target_updated.py
    ports/nutrition_target_repository_port.py
    ports/target_history_repository_port.py
    ports/daily_nutrition_total_repository_port.py
    ports/nutrient_panel_mirror_port.py
    ports/user_metrics_snapshot_port.py
    ports/profile_reveal_port.py               # NEW per Addendum 1: fetches
                                                # plaintext metrics from
                                                # profile-service's reveal endpoint
    ports/event_publisher_port.py
    ports/outbox_repository_port.py
    ports/processed_events_port.py
    services/bmr_calculator.py                 # cites Mifflin MD et al. 1990;
                                                # Sex.OTHER handling per Addendum 1
    services/tdee_calculator.py                # cites the section 9.2 PAL table
    services/calorie_target_calculator.py      # cites section 9.3 bounds
    services/macro_repartition_calculator.py
    services/nutrient_total_calculator.py
    services/recomputation_policy.py

  application/
    dto/nutrient_total_dto.py, nutrition_target_dto.py, user_metrics_snapshot_dto.py
    commands/recompute_daily_nutrient_total.py       (+handler)
    commands/recompute_nutrition_target.py            (+handler; calls
                                                        ProfileRevealPort, then
                                                        the domain calculators)
    commands/upsert_nutrient_panel_mirror_entry.py    (+handler)
    queries/get_current_nutrition_target.py
    queries/get_current_daily_total.py
    queries/get_target_history.py

  infrastructure/
    http/routes/target_routes.py
    http/routes/nutrition_total_routes.py
    http/schemas/, http/health.py
    http/profile_reveal_client.py               # NEW: httpx client for
                                                 # profile-service's reveal
                                                 # endpoint, circuit breaker +
                                                 # retry + timeout (Addendum 1)
    messaging/rabbitmq_event_publisher.py
    messaging/outbox_relay_worker.py
    messaging/diary_food_entry_consumer.py
    messaging/profile_metrics_consumer.py       # triggers recompute; does NOT
                                                 # read the ciphertext fields
                                                 # itself (Addendum 1) -- only
                                                 # uses user_id + which field
                                                 # changed as the trigger
    messaging/catalog_product_consumer.py
    persistence/models.py
    persistence/postgres_nutrition_target_repository.py
    persistence/postgres_target_history_repository.py
    persistence/postgres_daily_nutrition_total_repository.py
    persistence/postgres_nutrient_panel_mirror_repository.py
    persistence/postgres_user_metrics_snapshot_repository.py
    persistence/postgres_outbox_repository.py
    persistence/postgres_processed_events_repository.py
    caching/redis_current_target_cache.py
    caching/redis_current_total_cache.py
    composition_root.py
    main.py

  tests/
    unit/domain/...            # bmr/tdee/calorie_target/macro_repartition/
                                # nutrient_total calculators against published
                                # Mifflin-St Jeor worked examples
    unit/application/...       # command/query handlers, fake ports incl.
                                # FakeProfileRevealPort, idempotency-replay tests
    integration/infrastructure/
        test_postgres_nutrition_target_repository.py
        test_postgres_target_history_repository.py
        test_postgres_daily_nutrition_total_repository.py
        test_postgres_nutrient_panel_mirror_repository.py
        test_postgres_user_metrics_snapshot_repository.py
        test_diary_food_entry_consumer.py       # incl. idempotency case
        test_profile_metrics_consumer.py        # incl. idempotency case
        test_catalog_product_consumer.py        # incl. idempotency case
        test_profile_reveal_client.py           # circuit breaker trip/half-open/
                                                 # recover, against a fixture
                                                 # profile-service double, per
                                                 # Addendum 1's security requirements
        test_outbox_relay_worker.py
        test_redis_current_target_cache.py
        test_redis_current_total_cache.py
        test_migration_0001.py
    contract/http/test_target_routes.py, test_nutrition_total_routes.py
    contract/events/test_event_schemas.py
    fixtures/factories.py
    fixtures/reference_values.py

infra/k8s/charts/nutrition-calculation-service/
  Chart.yaml, values.yaml, values-dev.yaml, values-staging.yaml, values-prod.yaml,
  values.schema.json, ci/synthetic-values.yaml, templates/ (built on _lib/)
  # NetworkPolicy must additionally allow egress to profile-service's internal
  # port only (Addendum 1's blast-radius requirement) -- not a blanket
  # cluster-wide egress rule

infra/terraform/environments/dev/nutrition-calculation-service.tf
    # mirrors catalog-service.tf: module.ecr, Helm release referencing
    # module.rds/module.secrets/module.eks outputs; Redis reuses the shared
    # elasticache cluster via a `nutrition:*` key namespace (no new cluster)

.github/workflows/nutrition-calculation-service-ci.yml
    # path-filtered, includes helm-lint-and-template job; mutation-testing
    # step is advisory/non-blocking

docker-compose.yml, Makefile
    # add nutrition-db, nutrition-redis, nutrition-calculation-service blocks /
    # SERVICE=nutrition-calculation-service target

packages/shared-contracts/schemas/nutrition_value_recomputed.v1.json      # new
packages/shared-contracts/schemas/nutrition_target_updated.v1.json       # new
packages/shared-contracts/python/shared_contracts/events/nutrition_calculation.py  # new

docs/events-catalog.md      # replace the current combined placeholder with two
                             # separately-versioned, Status: Active entries
docs/api-catalog.md         # /api/v1/nutrition/*: planned -> active; add the
                             # new profile-service internal reveal endpoint to
                             # the Internal APIs table
docs/domain-glossary-and-context-map.md   # update the profile-service ->
                             # nutrition-calculation-service row to reflect the
                             # reveal-endpoint relationship (see section 6(e))

--- Also touches profile-service (existing, merged service) ---
services/profile-service/
  infrastructure/http/routes/internal_reveal_routes.py    # NEW: the reveal
                                                            # endpoint itself,
                                                            # per Addendum 1's
                                                            # security requirements
                                                            # (exact shape TBD by
                                                            # security-agent review,
                                                            # tracked as a
                                                            # sub-addendum before
                                                            # /implementation-execution
                                                            # touches this file)
  tests/contract/http/test_internal_reveal_routes.py       # NEW
  README.md, CLAUDE.md                                     # document the new
                                                            # internal endpoint,
                                                            # its caller, and its
                                                            # audit-log behavior
docs/api-catalog.md          # add the new internal endpoint row
```

## 4. Ports/adapters affected

| Port (domain/application) | Adapter (infrastructure) |
|---|---|
| `NutritionTargetRepositoryPort` | `PostgresNutritionTargetRepository` |
| `TargetHistoryRepositoryPort` | `PostgresTargetHistoryRepository` |
| `DailyNutritionTotalRepositoryPort` | `PostgresDailyNutritionTotalRepository` |
| `NutrientPanelMirrorPort` | `PostgresNutrientPanelMirrorRepository` |
| `UserMetricsSnapshotPort` | `PostgresUserMetricsSnapshotRepository` (metadata only — `last_fetched_at`, `formula_version`, `sex_constant_used` — never raw plaintext biometric values, per security-agent's sub-addendum requirement 8) |
| `ProfileRevealPort` (NEW) | `ProfileRevealClient` — synchronous HTTP call to `profile-service`'s new internal reveal endpoint, `purgatory` circuit breaker + `tenacity` retry + explicit timeout (per Addendum 1) |
| `EventPublisherPort` | `RabbitMqEventPublisher` |
| `OutboxRepositoryPort` | `PostgresOutboxRepository` + `OutboxRelayWorker` |
| `ProcessedEventsPort` | `PostgresProcessedEventsRepository` — dedup by `(consumer_name, event_id)`, shared across all 3 inbound consumers |
| Inbound: diary consumer | `RabbitMqDiaryFoodEntryConsumer` |
| Inbound: profile consumer | `RabbitMqProfileMetricsConsumer` — triggers recompute; does not itself carry or store ciphertext (per Addendum 1) |
| Inbound: catalog consumer | `RabbitMqCatalogProductConsumer` |
| `CurrentTargetCachePort` | `RedisCurrentTargetCache` (`nutrition:current-target:{user_id}`, 1h TTL) |
| `CurrentTotalCachePort` | `RedisCurrentTotalCache` (`nutrition:daily-total:{user_id}:{date}`, 5 min TTL — new namespace, added to `caching-strategy` SKILL.md in this PR) |

All new. This is a from-scratch service plus one new endpoint on `profile-service`.

## 5. Domain events

**`NutritionValueRecomputed` (v1, new)**
```json
{
  "user_id": "uuid", "scope": "entry | day", "entry_id": "uuid | null", "date": "date | null",
  "macros": { "calories_kcal": "number", "protein_g": "number", "carbs_g": "number", "fat_g": "number" },
  "micronutrients": { "...": "number | null" } | null,
  "micronutrients_status": "available | partial | unavailable",
  "is_estimated": "boolean", "confidence_range": { "min": "number", "max": "number" } | null,
  "formula_version": "string",
  "reason": "food_entry_logged | food_entry_corrected | food_entry_deleted | formula_correction",
  "recomputed_at": "timestamp"
}
```
`confidence_range` always `null` this pass.

**`NutritionTargetUpdated` (v1, new)**
```json
{
  "user_id": "uuid", "bmr_kcal": "number", "tdee_kcal": "number", "calorie_target_kcal": "number",
  "macro_targets": { "protein_g_min": "number", "protein_g_max": "number", "fat_g_min": "number", "carbs_g": "number" },
  "goal_type": "LOSE | MAINTAIN | GAIN",
  "activity_level": "SEDENTARY | LIGHT | MODERATE | ACTIVE | VERY_ACTIVE",
  "activity_adjustment_kcal": "number | null",
  "clamped": "boolean", "clamp_reason": "string | null",
  "formula_version": "string",
  "reason": "weight_recorded | body_metric_recorded | goal_set | goal_updated | formula_correction",
  "effective_from": "timestamp"
}
```
`activity_adjustment_kcal` always `null` this pass.

Both require `docs/events-catalog.md` entries and new `packages/shared-contracts` schemas.

**Inbound event contracts** (exact shapes per `docs/events-catalog.md`): `FoodEntryLogged`/`FoodEntryCorrected` (diary-service) — `source.snapshot.macros_per_unit`, `source.source_type`, `source.source_reference_id`. `FoodEntryDeleted` (diary-service). `WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated` (profile-service) — ciphertext fields, used only as a recompute *trigger* (carrying `user_id`), never decrypted from the event payload itself (Addendum 1). `ProductCatalogued`/`ProductUpdated` (catalog-service) — `nutrition_per_100g` in catalog-service's own field-naming vocabulary, translated per section 6(g).

## 6. Cross-service impact — flagged for `architecture-agent`

**(a) ADR-0002 correction, proposed.** See §9.4 — recommend a new superseding ADR (e.g. ADR-0024) via `/adr`, not a direct edit.

**(b) First service with 3 simultaneous live inbound event dependencies** (`diary-service`, `profile-service`, `catalog-service`). A `FoodEntryLogged` referencing a barcode whose `ProductUpdated` hasn't yet reached the local mirror is an accepted, eventually-consistent gap (explicit `"unavailable"`), not a bug — documented as a trade-off, not left implicit.

**(c) First instance of the local-mirror-of-another-service's-events pattern, introduced twice** (`nutrient_panel_mirror` from `catalog-service`; `user_metrics_snapshot` from `profile-service`, populated via the reveal endpoint rather than directly from event payloads per Addendum 1). Worth explicit sign-off as a new precedent — `activity-service`'s planned multi-wearable ingestion may want to copy this shape later.

**(d) Encryption boundary — resolved via Addendum 1.** `profile-service` gains a new internal reveal endpoint; `nutrition-calculation-service` calls it synchronously (with resilience patterns) rather than attempting to decrypt `profile-service`'s events itself, preserving ADR-0023's key-isolation principle (the key material itself is never shared — only a plaintext *result* of a decryption `profile-service` performs on its own). Concrete security requirements are pinned down in Addendum 1, informed by a dedicated `security-agent` review conducted as part of approving this plan.

**(e) `docs/domain-glossary-and-context-map.md`'s `profile-service → nutrition-calculation-service` row updated** to describe the reveal-endpoint relationship (a synchronous internal call, not a pure "via published domain events" relationship) — same pattern already documented for `identity-service`/`notification-service`'s reveal endpoint.

**(f) Resolves `catalog-service`'s own deferred question**: local mirror, never a live synchronous lookup for nutrient data specifically (the reveal endpoint is a different, narrower exception for encrypted biometric data only).

**(g) Naming mismatch between `diary-service`'s and `catalog-service`'s nutrient vocabularies** — this service defines its own canonical vocabulary and translates both at the application/infrastructure boundary.

## 7. Resilience/caching/migration needs

**Idempotent consumption** (all 3 event consumers): dedup via `ProcessedEventsPort.already_processed(consumer_name, event_id)`, retained 30 days. Write-model idempotency reinforced at the storage layer (upsert by natural key).

**New synchronous inter-service call** (`ProfileRevealClient` → `profile-service`'s reveal endpoint): `purgatory` circuit breaker + `tenacity` retry with backoff + explicit timeout, mirroring `identity-service`'s existing reveal-endpoint client pattern. Fallback behavior: if the circuit is open or the call fails, the recompute is deferred (retried later via the outbox-relay-style pattern or left for the next triggering event) rather than computing a target from stale/partial local data — a nutrition target must never be silently computed from incomplete inputs.

**Migration.** First Alembic migration, `CREATE TABLE`-only: `nutrition_targets`, `nutrition_target_history`, `daily_nutrition_totals`, `nutrient_panel_mirror`, `user_metrics_snapshot`, `outbox`, `processed_events`. Additive. **Terraform**: same shape as `catalog-service.tf`; Redis reuses the shared ElastiCache cluster via a `nutrition:*` key namespace.

**Caching**: `nutrition:current-target:{user_id}` (1h TTL), `nutrition:daily-total:{user_id}:{date}` (5 min TTL, new namespace added to `caching-strategy` SKILL.md in this PR). Event-driven invalidation on `NutritionTargetUpdated`/`NutritionValueRecomputed`.

## 8. Test plan reference

See `/plans/nutrition-calculation-service/test-plan.md`.

## 9. Risks and open questions — resolved in Addendum 1 below

Original open questions 9.1 (encryption boundary), 9.2 (activity-factor table), 9.3 (calorie-target safety bounds), 9.8 (`Sex.OTHER` handling) are resolved in Addendum 1. Remaining, non-blocking:

**9.4 — ADR-0002 correction mechanism.** Recommend a new superseding ADR (e.g. ADR-0024) via `/adr`, rather than editing ADR-0002's Decision text in place, to preserve the historical record of what was actually approved on 2026-08-23.

**9.5 — Naming translation seam.** Resolved as a design decision (§6(g)): this service owns its own canonical vocabulary.

**9.6 — No bulk-reprocessing job for a formula correction.** Domain model reserves `formula_version`; a bulk reprocessing job is deferred to a future plan once actually needed.

**9.7 — `activity-service`/`food-recognition-service` seams** — reserved fields, always-null this pass, no port/adapter built.

**9.9 — Mutation testing tooling and CI gating** — deferred to `/test-plan`; advisory, not a merge-blocking gate.

**9.10 — Target-history retention** — no pruning policy yet; not blocking given expected low per-user cardinality.

---

## Addendum 1 — 2026-08-26, blocking questions resolved at approval

**§9.1 resolved: Option A, a new internal reveal endpoint on `profile-service`.** `profile-service` gains `POST /internal/v1/profile/{user_id}/reveal-metrics`. `nutrition-calculation-service` calls it synchronously via `ProfileRevealClient`, wrapped in a circuit breaker, only when it needs to recompute a target (triggered by `RabbitMqProfileMetricsConsumer` receiving a metrics-changed event, which itself carries no ciphertext — it's purely a trigger).

**Sub-addendum — `security-agent` review, APPROVED WITH REQUIRED CHANGES, human-approved 2026-08-26.** Copying `identity-service`'s `.../reveal` endpoint as-is was rejected: that precedent uses one shared bearer credential (no per-caller distinction), has no rate limiting, and `profile-service` has no audit-trail mechanism at all today. The following are **binding requirements**, not suggestions, and `/implementation-execution` may not deviate from them without a new human approval:

1. **Per-caller credential**: a new, distinct Terraform-generated (`random_password`) Secrets Manager entry scoped specifically to `nutrition-calculation-service` as caller (e.g. `nutriapp/<env>/profile-service/internal-reveal-credential-nutrition-calc`) — not a reused/shared secret.
2. **Narrow IRSA exception, human-approved**: `nutrition-calculation-service`'s IRSA role gets `secretsmanager:GetSecretValue` on exactly that one secret ARN — never `profile-service`'s `db-credentials`, KMS key, or anything else. Documented explicitly in both services' Terraform as a deliberate, narrow, approved exception to CLAUDE.md §2.9's "no service reads another service's secrets" default.
3. **Separate port + NetworkPolicy**, excluding Kong: this endpoint is not reachable via the public API surface at all; ingress restricted to `nutrition-calculation-service`'s pod selector only, on a distinct `targetPort` from `profile-service`'s public port.
4. **App-level rate limiting**, keyed by both caller-credential and requested `user_id`, reusing `identity-service`'s `RateLimiterPort`/`RedisRateLimiter` pattern.
5. **Response minimization**: a new, dedicated query returns exactly `weight_kg, height_cm, age, sex, activity_level, goal_type` — no historical values, no consent metadata, no numeric goal targets, and not a thin wrapper around the full-profile decrypt path.
6. **New audit-trail capability in `profile-service`** (built from scratch — none exists today): append-only, INSERT-only DB role, recording on every call (success and failure): `actor_id` (the caller's identity, derivable from which per-caller credential was presented), `action="biometric_snapshot_revealed"`, `target_type="profile"`, `target_id=user_id`, `outcome`, `metadata={"fields": [...]}` (field **names** disclosed, never values), `correlation_id`.
7. **Dedicated circuit breaker** on `nutrition-calculation-service`'s calling side — never sharing `profile-service`'s own internal KMS breaker — explicit `fail_max`/`reset_timeout`/timeout documented in both services' `README.md`. Fallback on open-circuit/failure: defer the recompute (retry on the next triggering event), never guess or default biometric values.
8. **No persistence of raw plaintext biometric fields in `nutrition-calculation-service`.** `user_metrics_snapshot` may cache only derived scalars if needed for performance (e.g. `bmr_kcal`) with a short documented TTL — never the raw weight/height/age/sex response (that would create a second, unencrypted, non-crypto-shreddable copy of Art. 9 data outside `profile-service`'s erasure design, defeating ADR-0023). This is a correction to §3's original `user_metrics_snapshot` table design, which is now scoped to metadata (e.g. `last_fetched_at`, `formula_version` used) rather than the plaintext values themselves — the actual plaintext is fetched fresh from `ProfileRevealPort` at each recompute, not cached as raw fields.
9. **Never log the response body or any field value** — structured logs may record that a reveal occurred and which field names were requested, never values. A redaction test is required.
10. **Required tests** (`profile-service` side): wrong/missing credential → 401/403 + audit record with `outcome="failure"`; rate-limit exceeded → 429; response-shape test asserting only the 6 allow-listed keys are present; log-redaction test.
11. **`docs/api-catalog.md`** gets a new Internal APIs row for this endpoint, same format as the existing `/internal/v1/auth/tokens/{reference_id}/reveal` row.
12. This is new Terraform/Helm/K8s scope and a new inter-service dependency for `profile-service` — implemented as its own coordinated sub-plan (`profile-service` reveal endpoint) alongside this plan, both reviewed together at `/implementation-review` before either merges.

**§9.2 resolved.** Activity-factor table confirmed as proposed: `SEDENTARY = 1.2`, `LIGHT = 1.375`, `MODERATE = 1.55`, `ACTIVE = 1.725`, `VERY_ACTIVE = 1.9` (standard published PAL values). Cited in `tdee_calculator.py`'s docstring.

**§9.3 resolved.** Calorie-target safety bounds confirmed as proposed: floor = never below BMR; deficit cap = 1000 kcal/day below TDEE; surplus cap = 500 kcal/day above TDEE. Cited in `calorie_target_calculator.py`'s docstring, with `clamped`/`clamp_reason` surfaced to the user per the domain-calculation-conventions SKILL.md's "no false precision" / transparency rule.

**§9.8 resolved.** `Sex.OTHER` requires explicit user selection (male/female constant) for calculation purposes only, with user-facing copy that clearly frames this as a limitation of the published Mifflin-St Jeor formula, not a statement about the user's identity. The choice is stored alongside the computed target (which constant was used) for traceability, not silently discarded after one use.

**Human authorization for straight-through execution**, consistent with the last two services: once the security-agent sub-addendum lands, proceed directly through `/test-plan`, `/implementation-execution`, and `/test-execution` without an additional per-stage pause — reviewed as a completed body of work afterward. No `git push`, PR, or merge without explicit human review, per CLAUDE.md §7.
