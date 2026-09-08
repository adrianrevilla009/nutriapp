# analytics-service

CQRS read-side trend analysis, nutrient-deficiency anomaly detection, and
Pro-gated CSV report/export, built from other services' domain events
(CLAUDE.md section 2.2, `.claude/agents/analytics-agent.md`).

## Bounded context

See `.claude/agents/analytics-agent.md` and
`/plans/analytics-service/implementation-plan.md`.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001).
**CQRS, read side only** (ADR-0002's addendum) -- this service has no
event-sourced or conventional write aggregate of its own; it consumes
other services' events and folds them into denormalized Postgres read
tables, then publishes exactly one domain event
(`NutrientDeficiencyDetected`) as a side effect via the standard Outbox
pattern. Trend/statistical computation lives in the domain layer as pure
functions operating on already-fetched data
(`domain/services/trend_calculator.py`, `domain/services/anomaly_detector.py`).

## Consumed events (v1)

- `FoodEntryLogged`/`FoodEntryCorrected`/`FoodEntryDeleted`,
  `WaterIntakeLogged`/`WaterIntakeRemoved` (`diary-service`) -- one
  consumer, `diary_events_consumer.py`, one idempotency ledger
  (`processed_diary_events`). Projects `daily_log_summary`.
- `WeightRecorded` (`profile-service`) -- `profile_events_consumer.py`.
  Projects `weight_trend`, storing the AES-256-GCM ciphertext field
  as-is (this service never decrypts it, ADR-0023).
- `NutritionValueRecomputed`/`NutritionTargetUpdated`
  (`nutrition-calculation-service`) -- `nutrition_calculation_events_consumer.py`.
  Projects `micronutrient_window` and triggers deficiency evaluation.
- `EntitlementGranted`/`EntitlementRevoked` (`billing-service`) --
  `billing_events_consumer.py`. THIRD real consumer of these two events
  (after `recipe-service`, `social-service`), implementing this service's
  side of the `ProUpgradeEntitlementPropagation` saga's fan-out.

**Deferred this pass** (documented-but-not-live consumer, same pattern
already recorded in `docs/events-catalog.md`): `FastingWindowStarted/Ended`,
`MealPlanned/Updated/Removed`, `BodyMetricRecorded`, `GoalSet/Updated`,
`ExerciseLogged`, `RecipeCreated/Updated/Published/Unpublished`,
`UserFollowed/Unfollowed`, `SubscriptionStarted/Renewed/Cancelled/PaymentFailed`.

## Published events (v1)

`NutrientDeficiencyDetected` -- see `docs/events-catalog.md` and
`packages/shared-contracts/schemas/nutrient_deficiency_detected.v1.json`.
Emitted when a tracked nutrient's value is below its `target_min` on at
least 5 of the last 7 calendar-days-with-data, subject to a 14-day
cooldown per (user, signal) pair (`anomaly_alerts` table, dedup guard).
Real consumer: `notification-service` (separate, coordinated PR, not part
of this change -- see "Known gap" below for sequencing).

**Known, flagged gap** (`domain/tracked_nutrients.py`'s docstring has the
full reasoning): only `protein_g`/`fat_g` are evaluated today.
`NutritionTargetUpdated`'s actual documented payload has no micronutrient
`target_min` field -- only `macro_targets.protein_g_min`/`fat_g_min` are
genuinely `_min`-shaped targets in the schema as it exists. True
micronutrient (vitamin/mineral) deficiency detection is NOT functionally
live -- the mechanism is generic/nutrient-agnostic and fully tested, but
has no real target data to evaluate against for anything beyond those two
macros. Flagged for `architecture-agent`/`security-agent` review.

## Public API

JWT-authenticated (ADR-0022, `packages/shared-contracts`' centralized
auth dependency) throughout.

- `GET /api/v1/analytics/trends/weekly` -- logging streak + macro/water
  running totals vs. target, over a trailing window (default 7 days,
  clamped to `MAX_WINDOW_DAYS=90`). **Not Pro-gated.** Every returned
  statistic carries `sample_size`/`window_days` explicitly.
- `GET /api/v1/analytics/reports/{report_type}?start_date=...&end_date=...`
  -- CSV export of `daily_log_summary` + `micronutrient_window` rows for
  the requested range (v1 ships CSV only). **Pro-gated.** Every call --
  success OR rejection (invalid request, not entitled) -- is recorded in
  `analytics_audit.export_audit_log` (CLAUDE.md section 2.8,
  docs/observability-and-audit.md section 4.1) -- every call, never
  deduplicated.

**Entitlement-rejection status code**: `402 Payment Required`, code
`NOT_ENTITLED` -- reuses `recipe-service`'s repo-wide convention verbatim.

## Entitlement gating

Cache-first: `entitlement_cache` table (populated by consuming
`EntitlementGranted`/`EntitlementRevoked`), checked only by the
report/export query -- `GET /trends/weekly` never touches an entitlement
port at all (structural guard). On a genuine cache MISS, falls back to
`billing-service`'s synchronous
`GET /internal/v1/billing/entitlements/{user_id}` (own circuit breaker,
`billing_entitlement_check`) -- the fallback result is never written back
into the cache. A fallback-check failure fails SAFE (not entitled).

## Resilience

| Integration                                                    | Circuit name              | fail_max | reset_timeout |
|------------------------------------------------------------------|------------------------------|------------|------------------|
| `billing-service` entitlement check (cache-miss fallback only) | `billing_entitlement_check` | 5          | 30s              |

## Testing

`docs/testing-strategy.md`, `/plans/analytics-service/test-plan.md`.
`BillingEntitlementClient` is tested entirely against `httpx.MockTransport`
fixtures -- zero live calls to billing-service anywhere. Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.
Actual (2026-09-08, after the export-audit-trail compliance fix): domain
99%, application 99%, infrastructure 86%, 110/110 tests passing.

## Flagged for review before prod promotion

1. **Deficiency threshold rule** (5-of-7-days below `target_min`, 14-day
   cooldown) is an explicit dev-default, not clinically reviewed
   (`/plans/analytics-service/implementation-plan.md` section 9,
   resolution 2) -- `security-agent` sign-off required before staging/prod.
2. **Micronutrient-target gap** (see above) -- `architecture-agent` should
   confirm whether extending `NutritionTargetUpdated` (a
   `nutrition-calculation-service` change) is worth reopening that
   already-merged service's formula surface.
3. ~~**`export_audit_log` schema** is a first-cut...~~ **Fixed** (2026-09-08,
   security review): `analytics_audit.export_audit_log` now carries the
   full docs/observability-and-audit.md section 4.2 shape
   (`outcome`/`actor_id`/`action`/`target_type`/`target_id`/
   `correlation_id`, in addition to the pre-existing `export_id`/`user_id`/
   `report_type`/`requested_at`/`export_format`/date-range/`row_count`),
   lives in a separate schema with `UPDATE`/`DELETE` genuinely revoked at
   the Postgres level from the connection the app writes through
   (`analytics_service_audit_writer`, `SET ROLE`-per-connection --
   `infrastructure/composition_root.py`'s `Container.audit_engine`,
   migrations/versions/0002_export_audit_log_compliance.py), and now
   audits rejected/probing export attempts too, not just successful ones
   (`application/queries/get_report.py`).
4. **`notification-service` consumer for `NutrientDeficiencyDetected`** is
   a separate, coordinated change (not part of this service's own PR) --
   this service's own tests never assume a live consumer exists.
