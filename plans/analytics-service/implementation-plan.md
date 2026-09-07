# Implementation Plan — `analytics-service`

**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-07, by adrianrg1996@gmail.com.

**Related:** ADR-0001 (hexagonal), ADR-0002 + its 2026-08-28 addendum (CQRS scope — `analytics-service` is explicitly "CQRS, read side only... consumes events into read models, no event-sourced write aggregate of its own"), ADR-0004 (messaging), ADR-0015 (billing/entitlements), ADR-0019 (sagas), `.claude/agents/analytics-agent.md`, `.claude/skills/cqrs-event-sourcing/SKILL.md`, `.claude/skills/messaging-conventions/SKILL.md`, `.claude/skills/resilience-patterns/SKILL.md`, `.claude/skills/database-migrations/SKILL.md`, `docs/events-catalog.md`, `docs/api-catalog.md`, `docs/data-platform-and-analytics.md` §1, `docs/domain-glossary-and-context-map.md`, `docs/sagas-and-distributed-transactions.md` (`ProUpgradeEntitlementPropagation`), `/plans/recipe-service/implementation-plan.md` and `/plans/social-service/implementation-plan.md` (closest structural precedents).

---

## 1. Scope

Build `analytics-service` end-to-end (domain → application → infrastructure → tests) plus its Terraform/Helm/CI wiring, mirroring the scaffolding pattern used for every prior Phase 2 service (`recipe-service`, `social-service`, `billing-service`, `activity-service`). This is the service's first-ever implementation plan — no code exists yet.

**Bounded context**: trend analysis, reporting, and anomaly/threshold detection built from other services' events, consumed into denormalized read models. Per ADR-0002's addendum, this is **CQRS read side only** — no event-sourced or even conventional write aggregate of its own; the read models *are* the whole write surface, populated as a side effect of consuming events.

**Initial event-consumption scope**:
- `diary-service`: `FoodEntryLogged`, `FoodEntryCorrected`, `FoodEntryDeleted`, `WaterIntakeLogged`, `WaterIntakeRemoved` — feeds logging-consistency/streak and running-totals trends.
- `profile-service`: `WeightRecorded` — feeds a weight-evolution trend line.
- `nutrition-calculation-service`: `NutritionValueRecomputed`, `NutritionTargetUpdated` — feeds the macro/micro rolling window used for both trend running-totals and deficiency detection.
- `billing-service`: `EntitlementGranted`, `EntitlementRevoked` — entitlement gating for reports/export, third real consumer of `ProUpgradeEntitlementPropagation`'s fan-out.

**Explicitly deferred**: `FastingWindowStarted/Ended`, `MealPlanned/Updated/Removed`, `BodyMetricRecorded`, `GoalSet/Updated`, `ExerciseLogged`, `RecipeCreated/Updated/Published/Unpublished`, `UserFollowed/Unfollowed`, `SubscriptionStarted/Renewed/Cancelled/PaymentFailed`. Each stays a documented-but-not-live consumer.

**Acceptance criteria:**
1. Four consumers idempotently project the events above into local read tables, never double-counting on redelivery (CLAUDE.md §2.4).
2. `GET /api/v1/analytics/trends/weekly` — **not Pro-gated**. Returns logging streak, running macro/water totals vs. target, over the trailing N weeks. Every returned statistic states its sample size (days with data) and window.
3. Nutrient-deficiency detection: a domain service evaluates the rolling micronutrient window against `NutritionTargetUpdated`'s targets; on a sustained breach, publishes `NutrientDeficiencyDetected` (v1) via Outbox — **not Pro-gated**, framed as informational only (CLAUDE.md §7/8 — never a diagnosis).
4. `GET /api/v1/analytics/reports/{report_type}` and a data-export endpoint — **Pro-gated**, entitlement checked cache-first against a local `entitlement_cache`, falling back to `billing-service`'s existing `GET /internal/v1/billing/entitlements/{user_id}` on a cache miss. Every export is recorded in an immutable audit trail.
5. Entitlement cache consumers, structurally identical to `recipe-service`'s/`social-service`'s pattern.
6. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70%.

**Explicitly out of scope**: every deferred event above; a Redis hot-cache for trend reads; any data-warehouse/BI layer; wiring `nutrition-assistant-service` as a live `NutrientDeficiencyDetected` consumer (that service doesn't exist yet).

---

## 2. Architectural classification

CQRS, read side only (ADR-0002 addendum). No event-sourced write aggregate — this service never appends to its own event store; it only consumes other services' events and folds them into denormalized Postgres read tables, then publishes exactly one domain event of its own (`NutrientDeficiencyDetected`) as a side effect, via the standard Outbox pattern.

Trend/statistical computation logic lives in the domain layer as pure functions operating on already-fetched data (`domain/services/trend_calculator.py`, `domain/services/anomaly_detector.py`) — zero I/O, framework, or persistence dependency. All four layers are touched (domain, application, infrastructure, tests).

---

## 3. Files to create or modify

```
services/analytics-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_analytics_tables.py
      # daily_log_summary, micronutrient_window, weight_trend, anomaly_alerts,
      # entitlement_cache, processed_diary_events, processed_profile_events,
      # processed_nutrition_calculation_events, processed_entitlement_events,
      # export_audit_log, outbox
  domain/
    value_objects/    # trend_point.py, streak_summary.py, macro_running_total.py,
                       # deficiency_signal.py, report_period.py
    events/            # base.py, nutrient_deficiency_detected.py
    services/          # trend_calculator.py, anomaly_detector.py
    ports/             # daily_log_summary_repository_port.py, micronutrient_window_repository_port.py,
                       # weight_trend_repository_port.py, anomaly_alerts_repository_port.py,
                       # entitlement_cache_repository_port.py, entitlement_check_port.py,
                       # processed_*_events_repository_port.py (x4),
                       # export_audit_repository_port.py, event_publisher_port.py, outbox_repository_port.py
  application/
    commands/          # handle_food_entry_logged.py, handle_food_entry_corrected.py,
                       # handle_food_entry_deleted.py, handle_water_intake_logged.py,
                       # handle_water_intake_removed.py, handle_weight_recorded.py,
                       # handle_nutrition_value_recomputed.py, handle_nutrition_target_updated.py,
                       # handle_entitlement_granted.py, handle_entitlement_revoked.py
    queries/           # get_weekly_trend.py, get_report.py, export_report.py
    dto/, entitlement_check.py, errors.py
  infrastructure/
    http/routes/       # trend_routes.py, report_routes.py, health.py
    http/schemas/, dependencies.py, error_mapping.py
    external/          # billing_entitlement_client.py
    persistence/       # models.py + one repository per port above
    messaging/         # diary_events_consumer.py, profile_events_consumer.py,
                       # nutrition_calculation_events_consumer.py, billing_events_consumer.py,
                       # rabbitmq_event_publisher.py, outbox_relay_worker.py
    composition_root.py, main.py
  tests/
    unit/domain/, unit/application/, integration/infrastructure/,
    contract/http/, contract/events/

services/notification-service/    # small, coordinated addition (separate PR, sequenced first)
    domain/value_objects/notification_category.py   # add "nutrient_deficiency_alert"
    infrastructure/messaging/analytics_events_consumer.py   # new
    infrastructure/templating/templates/push/nutrient_deficiency_alert_v1.json.j2
    tests/

infra/terraform/environments/dev/analytics-service.tf
infra/k8s/charts/analytics-service/     # correct env-list format + envFrom from the start
.github/workflows/analytics-service-ci.yml

docs/events-catalog.md, docs/api-catalog.md, docs/domain-glossary-and-context-map.md,
docs/sagas-and-distributed-transactions.md, ARCHITECTURE.md, docker-compose.yml
```

---

## 4. Ports/adapters affected

New ports (all local to `analytics-service`, none shared): `DailyLogSummaryRepositoryPort`, `MicronutrientWindowRepositoryPort`, `WeightTrendRepositoryPort`, `AnomalyAlertsRepositoryPort`, `EntitlementCacheRepositoryPort`, `EntitlementCheckPort` (→ `billing-service`'s existing internal endpoint, no new endpoint needed), `ExportAuditRepositoryPort`, four `Processed*EventsRepositoryPort`s, `EventPublisherPort`, `OutboxRepositoryPort`.

`notification-service`: new adapter `analytics_events_consumer.py`, same shape as existing consumers — additive infrastructure only, no new port.

Entitlement-check design structurally copied from `recipe-service`'s/`social-service`'s implementation (own local cache + fallback-never-cached call), not a shared library.

---

## 5. Domain events

**Consumed:** `FoodEntryLogged`, `FoodEntryCorrected`, `FoodEntryDeleted`, `WaterIntakeLogged`, `WaterIntakeRemoved` (v1, `diary-service`); `WeightRecorded` (v1, `profile-service`); `NutritionValueRecomputed`, `NutritionTargetUpdated` (v1, `nutrition-calculation-service`); `EntitlementGranted`, `EntitlementRevoked` (v1, `billing-service`). All nine already exist in `docs/events-catalog.md` with `analytics-service` pre-listed as a documented consumer.

**Published:** `NutrientDeficiencyDetected` (v1) — flesh out from stub in `docs/events-catalog.md`: producer `analytics-service`, consumers `notification-service` (real) and `nutrition-assistant-service` (documented, deferred). Payload: standard envelope + `{ "user_id"/"aggregate_id": "uuid", "signal": "string", "window_days": "number", "value": "number", "target_min": "number" }`.

No producer-side change needed to any upstream service.

---

## 6. Cross-service impact

1. Consumes already-active events from `diary-service`, `profile-service`, `nutrition-calculation-service` — **no code change** to any of these three.
2. Consumes `billing-service`'s events + calls its existing internal endpoint — **no `billing-service` code change**.
3. `notification-service` gains a **real** new consumer, new push category, new template — genuine code change, sequenced as its own PR before `analytics-service`'s PR (two-PR pattern, same as `social-service`→`notification-service`).
4. `nutrition-assistant-service`: documented future consumer, not built (service doesn't exist).
5. `bff-service`: no change in this plan.

This plan touches four upstream event producers plus one downstream consumer simultaneously — the broadest cross-service surface of any single plan to date. `architecture-agent` review is recommended before/during implementation on: the event-scope cut, whether the four independent idempotency ledgers hide a simpler design, and the `NutrientDeficiencyDetected` schema.

---

## 7. Resilience/caching/migration needs

- Circuit breaker `billing_entitlement_check` (cache-miss fallback only), independent per-service instance per `resilience-patterns` skill.
- No Redis this pass — Postgres-backed projections only.
- One initial additive Alembic migration creating all tables.
- Queries over long historical windows must be paginated/date-range-bounded, never load full history into memory.
- Every returned value object (`StreakSummary`, `MacroRunningTotal`, `DeficiencySignal`) carries `sample_size`/`window_days` at the type level.

---

## 8. Test plan reference

`/test-plan` defines concrete cases next, per CLAUDE.md §3.

---

## 9. Risks and open questions — resolved at approval time (2026-09-07)

The plan was approved as proposed. The following open questions were flagged as needing a human decision before `/test-plan` could proceed meaningfully; resolutions below are the approved defaults to build against. Given the health-adjacent nature of deficiency detection, item 2's threshold logic is explicitly a **first-cut default for dev implementation**, not a clinically-reviewed rule — `security-agent` sign-off is still required before this reaches `staging`/prod, consistent with the plan's own recommendation.

1. **Event scope**: confirmed as proposed (logging + macros/water + weight only; fasting/exercise/etc. deferred).
2. **Deficiency taxonomy/threshold**: track only nutrients for which `nutrition-calculation-service` already publishes a `target_min` via `NutritionTargetUpdated` (no new nutrient list invented here). "Sustained breach" = value below `target_min` on at least 5 of the last 7 calendar days with logged data (tolerates one missed-logging day, avoids false trigger on a single bad day). Same signal is never re-published within a 14-day cooldown (deduplicated via `anomaly_alerts`). Every `NutrientDeficiencyDetected`-driven user-facing surface (push copy, any future in-app banner) must carry an explicit "not a medical diagnosis, consult a professional" disclaimer, mirroring the boundary language CLAUDE.md §8 mandates for `nutrition-assistant-service`, applied here by the same underlying principle even though this isn't that service.
3. **`/internal/v1/nutrition/targets`**: not built. This design gets targets via consumed events, not a synchronous call. `docs/api-catalog.md`'s `planned` row for it should be removed as part of this work unless a concrete synchronous need surfaces during implementation.
4. **Report/export format**: v1 ships CSV only (the JSON shape is already available via the trends endpoint), containing `daily_log_summary` + `micronutrient_window` rows for the requested date range. Extensible later, not blocking this plan.
5. **Two-PR sequencing**: confirmed — `notification-service`'s addition merges first, `analytics-service` second, so `NutrientDeficiencyDetected` is never live with zero consumers.
6. **`bff-service` dashboard surfacing**: confirmed out of scope for this plan.
7. **Export audit log**: build the first-cut schema as specified in §3 (`export_id`, `user_id`, `report_type`, `requested_at`, `format`, date range). Flagged for a follow-up `security-agent` review given GDPR Article 9 data (weight/biometric-derived trends) flows into exportable reports — this is a should-review-before-prod item, not a build blocker for dev implementation.
