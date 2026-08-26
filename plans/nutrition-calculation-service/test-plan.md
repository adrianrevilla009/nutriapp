# Test Plan — `nutrition-calculation-service`

**Status:** Approved
**Date approved:** 2026-08-26
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/nutrition-calculation-service/implementation-plan.md`

No test code has been written yet. The implementation plan's Addendum 1 (activity-factor table, calorie-target safety bounds, `Sex.OTHER` handling) and its security-agent sub-addendum (reveal-endpoint requirements) are treated as settled here.

## 0. Reference values assumed (from Addendum 1)

- Activity factors: `SEDENTARY=1.2, LIGHT=1.375, MODERATE=1.55, ACTIVE=1.725, VERY_ACTIVE=1.9`.
- Calorie-target bounds: floor = BMR; deficit cap = 1000 kcal/day below TDEE; surplus cap = 500 kcal/day above TDEE.
- `Sex.OTHER` requires an explicit male/female constant selection for calculation purposes, stored alongside the result.

## 1. Unit test cases

### Domain layer (no mocking, no I/O)

**`bmr_calculator`**
- Male, published Mifflin-St Jeor worked example (e.g. 70kg, 175cm, 25y → expected BMR within rounding tolerance of the textbook value) → matches reference value.
- Female, published worked example → matches reference value.
- `Sex.OTHER` without an explicit calculation-constant selection → raises (per Addendum 1, selection is mandatory, never defaulted).
- `Sex.OTHER` with an explicit selection → computes using that constant, and the choice is returned/stored alongside the result (traceability, not silently discarded).
- Non-positive weight/height, or age ≤ 0 → raises `InvalidBiometricInputError` (never silently clamps to a default).

**`tdee_calculator`**
- Each of the 5 activity levels against a fixed BMR → exact expected multiplication (`SEDENTARY` through `VERY_ACTIVE`, per §0's table).
- Unrecognized activity level → raises.
- `activity_adjustment_kcal` always ignored/`None` this pass (reserved seam, not wired to any input yet) — a case asserting TDEE is unaffected by a `None` adjustment.

**`calorie_target_calculator`**
- `LOSE` goal within the deficit cap → target = `TDEE - goal_adjustment`, `clamped=False`.
- `LOSE` goal requesting a deficit greater than 1000 kcal/day → clamped to `TDEE - 1000`, `clamped=True`, `clamp_reason` cites the deficit cap.
- `GAIN` goal beyond the 500 kcal/day surplus cap → clamped, `clamp_reason` cites the surplus cap.
- A clamp that would still fall below BMR → floor wins, target = BMR exactly, `clamp_reason` cites the BMR floor specifically (distinct from the deficit-cap reason — two different rules could both apply, the test asserts which one actually binds and why).
- `MAINTAIN` goal → target = TDEE, `clamped=False`.

**`macro_repartition_calculator`**
- Protein range scales correctly with body weight (1.6–2.2 g/kg) for a fixed weight.
- Fat floor is exactly 20% of the calorie target.
- Carbs = calorie_target − (protein_kcal_at_midpoint + fat_kcal_floor) / 4, remainder never negative (test a pathological low-calorie-target case to confirm carbs floors at 0 rather than going negative, and that this is surfaced as a flag, not silently returned as a negative number).

**`nutrient_total_calculator`**
- Single entry, catalog-sourced, full macro + micro data available → correct per-entry total, `micronutrients_status="available"`.
- Single entry, `source_type="catalog_product"` but no local mirror match yet → macros present (from diary's own snapshot), micronutrients `"unavailable"`, never estimated/zeroed.
- Single entry, `source_type="recipe"` or `"ai_detected"` (reserved, not yet exercised by any real producer) → macros from the snapshot as given, micronutrients `"unavailable"` unconditionally (no mirror lookup attempted for non-catalog sources).
- Day total: 3 entries summed correctly, at least one contributing an `"unavailable"` micronutrient status → day-level `micronutrients_status` correctly reflects `"partial"` (not silently `"available"` just because *some* entries resolved).
- Correction handling: `FoodEntryLogged` then `FoodEntryCorrected` for the same `entry_id` → the day total reflects only the corrected values, not double-counting the original.
- Deletion: `FoodEntryLogged` then `FoodEntryDeleted` → the day total excludes the deleted entry entirely.

**`allergen`/naming-translation seam (per implementation plan §6(g))**
- A raw `catalog-service` `nutrition_per_100g` shape (`energy_kcal`, `carbohydrates_g`, ...) and a raw `diary-service` `macros_per_unit` shape (`calories_kcal`, `carbs_g`, ...) both translate to the same internal canonical vocabulary for the same nutrient.

## 2. Integration test cases (infrastructure layer, testcontainers Postgres + RabbitMQ + Redis)

- `PostgresNutritionTargetRepository`: upsert-by-`user_id` round-trip.
- `PostgresTargetHistoryRepository`: append-only insert, ordered read.
- `PostgresDailyNutritionTotalRepository`: upsert-by-`(user_id, date)` round-trip.
- `PostgresNutrientPanelMirrorRepository`: upsert on `ProductCatalogued`, then `ProductUpdated` for the same key updates in place (mirror, not append).
- `diary_food_entry_consumer`: idempotency test — the same `FoodEntryLogged` delivered twice results in exactly one contribution to the day total, not two.
- `profile_metrics_consumer`: idempotency test — the same `WeightRecorded` delivered twice triggers exactly one recompute (asserted via a fake `ProfileRevealPort` call-count, not two).
- `catalog_product_consumer`: idempotency test — same shape, for `ProductCatalogued`/`ProductUpdated`.
- `ProfileRevealClient` circuit breaker: trip after the configured consecutive-failure count against a fixture HTTP double (never a real `profile-service` instance in this service's own test suite); half-open retry; recovery. Failure while open → the recompute command defers cleanly (no crash, no silently-defaulted biometric values) — asserted explicitly, per the plan's fallback requirement.
- `RedisCurrentTargetCache` / `RedisCurrentTotalCache`: cache-aside miss/hit, event-driven invalidation on `NutritionTargetUpdated`/`NutritionValueRecomputed` respectively.
- `OutboxRelayWorker`: same shape as prior services' precedent.
- Alembic migration `0001`: applies cleanly to an empty database.
- **Negative test, security-critical**: `PostgresUserMetricsSnapshotRepository`'s persisted row never contains a `weight_kg`/`height_cm`/`age`/`sex` column at all (schema-level assertion, not just "the test didn't set one") — a regression guard for the plan's requirement 8 (no plaintext persistence).

## 3. Contract test cases

- `GET /api/v1/nutrition/target`, `GET /api/v1/nutrition/target/history`, `GET /api/v1/nutrition/totals/{date}` — response schemas match documented OpenAPI contracts; `401` with no valid JWT.
- `NutritionValueRecomputed` (v1) / `NutritionTargetUpdated` (v1) — published payloads match `packages/shared-contracts/schemas/*.v1.json`.
- Consumer-side contract tests (payload-shape only, not live cross-service calls) confirming this service's understanding of `FoodEntryLogged`/`FoodEntryCorrected`/`FoodEntryDeleted`, `WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated`, and `ProductCatalogued`/`ProductUpdated` matches what's actually documented in `docs/events-catalog.md` — these break loudly if an upstream service's schema drifts.

## 4. E2E test cases

**None added in this plan.** Critical journey #1 ("Register → log a food item from catalog search → see macro/micro totals") is now fully coverable in principle (`identity-service`, `catalog-service`, `diary-service`, and this service all exist) — but `bff-service` (frontend aggregation) doesn't exist yet, and no frontend exists to drive a real browser-level E2E test against. Recommend this be the trigger to finally add journey #1's E2E test once `bff-service` ships — flagged as the natural next milestone, not deferred indefinitely without a concrete trigger.

## 5. Event-sourcing-specific cases

**Not applicable.** `nutrition-calculation-service` uses conventional persistence + event-driven CRUD, not event sourcing. The equivalent guarantees are covered in §1/§2: idempotent recomputation (unit + integration), and upsert-by-natural-key at the storage layer as a second, independent backstop against double-application.

## 6. Coverage expectation

Domain layer (5 calculators + naming-translation seam) carries the widest, most rigorous case count by design — this is the "hard floor ≥90%" layer per the agent doc, and mutation testing is recommended (advisory) specifically because subtle formula bugs are the highest-consequence failure mode in this service. Application-layer handlers (3 commands + 3 queries) targeting ≥85%. Infrastructure's integration matrix (4 repositories, 3 consumers with idempotency cases, the reveal-client circuit breaker, 2 caches, outbox, migration, plus the security-critical negative test) targeting ≥70%, expected to land comparable to or above `catalog-service`'s precedent (97%/97%/89%) given the deliberate emphasis on the reveal-client and consumer idempotency paths. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.
