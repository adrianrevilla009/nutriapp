# Test Plan — `analytics-service`

**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-07, by adrianrg1996@gmail.com.
**Implements:** `/plans/analytics-service/implementation-plan.md` (as persisted, including §9 addendum resolutions 1-7).

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases — domain

**`trend_calculator.py` (pure functions):**
- `compute_streak(daily_log_summary_rows, window_days)` — small-N: 3 days of data in a 7-day window, 2 of them consecutive ending today → streak = 2, `sample_size` = 3, `window_days` = 7 (documents the confidence limitation explicitly, per CLAUDE.md's disclosure rule). Large-N: 60 days of data with 3 separate gaps → known streak = the correct trailing run, `sample_size` = 60.
- `compute_running_totals(daily_log_summary_rows, target)` — macro/water totals vs. target over a window; both a 2-day sample and a 30-day sample with known expected averages/totals.
- Empty input (zero logged days in window) → returns a value object with `sample_size = 0`, never a computed average that implies data exists (e.g. never silently returns 0 as if that were a real average).

**`anomaly_detector.py` (pure function, resolution 2's rule):**
- `evaluate_breach(micronutrient_window_rows, target_min, lookback=7, threshold=5)`:
  - Exactly 5 of the last 7 calendar-days-with-data below `target_min` → breach = True (boundary, inclusive).
  - Exactly 4 of 7 below → breach = False (boundary, one below threshold).
  - Fewer than 7 calendar-days-with-data ever recorded for that nutrient (e.g. only 3) → breach = False, distinct "insufficient sample" result (not silently evaluated against a padded/assumed window) — documents the small-N confidence limitation.
  - A nutrient row with `target_min = None` (not published by `nutrition-calculation-service` for that nutrient) → excluded entirely from evaluation, never treated as a breach or a pass (resolution 2: "only nutrients where target_min is published").
  - Large-N: 30 days of data with two separate 5-of-7 breach windows separated by a compliant stretch → both correctly identified as independent candidate breach periods (cooldown/dedup itself is tested at the application layer, §2, since it depends on `anomaly_alerts` state, not just the window).

**Value objects:**
- `StreakSummary`, `MacroRunningTotal`, `DeficiencySignal`, `ReportPeriod` — construction fails (raises) if `sample_size < 0` or `window_days <= 0`; these fields are structurally required, not optional/defaultable, per the plan §7 rule that every returned stat carries them at the type level.
- `DeficiencySignal` — construction requires a non-empty disclaimer string (resolution 2: every user-facing surface driven by this must carry the "not a medical diagnosis" disclaimer) — tested as a structural guard, not just a docstring convention.

## 2. Unit test cases — application (all handlers, mocked ports)

**`HandleFoodEntryLoggedHandler` / `HandleFoodEntryCorrectedHandler` / `HandleFoodEntryDeletedHandler`:**
- Valid event → `daily_log_summary` row upserted/adjusted correctly (correction replaces, not adds; deletion subtracts, not zeroes the whole day).
- Same `event_id` processed twice → second call is a no-op (assert the fake repository's write method called exactly once total — mandatory idempotency test per messaging-conventions skill and CLAUDE.md §2.4).

**`HandleWaterIntakeLoggedHandler` / `HandleWaterIntakeRemovedHandler`:**
- Same upsert/adjust + idempotent-replay shape as above, specifically verifying a duplicate `WaterIntakeRemoved` delivery doesn't double-subtract `water_ml`.

**`HandleWeightRecordedHandler`:**
- Valid event → `weight_trend` row stored with the ciphertext field untouched (assert no decryption call is made anywhere — analytics-service never decrypts, per ADR-0023's non-decrypting posture already used by other services).
- Idempotent replay → no duplicate row.

**`HandleNutritionValueRecomputedHandler`:**
- Valid event → `micronutrient_window` rows upserted per nutrient/date, using the nutrient's currently-known `target_min` (from the last `NutritionTargetUpdated` on file, not retroactively rewritten by a later target change — historical rows keep the target value in effect when they were written).
- After upsert, triggers `detect_nutrient_deficiency`: breach detected AND signal not in 14-day cooldown → `anomaly_alerts` row inserted, `NutrientDeficiencyDetected` enqueued to outbox exactly once.
- Breach detected but signal IS within 14-day cooldown (an `anomaly_alerts` row for the same `user_id`+`signal` exists with `detected_at` < 14 days ago) → no new outbox publish, no duplicate alert row (resolution 2's cooldown rule, tested explicitly with both a 13-day-old and a 15-day-old prior alert as boundary cases).
- No breach → no `anomaly_alerts` row, no publish.
- Idempotent replay of the same `NutritionValueRecomputed` event_id → no duplicate `micronutrient_window` row, no duplicate deficiency evaluation side effect.

**`HandleNutritionTargetUpdatedHandler`:**
- Valid event → updates the stored "current target" reference for that user/nutrient; does not mutate already-written `micronutrient_window` historical rows (assert their `target_min` is unchanged after the handler runs).
- Idempotent replay → no duplicate effect.

**`HandleEntitlementGrantedHandler` / `HandleEntitlementRevokedHandler`:**
- Same shape as `recipe-service`/`social-service`'s precedent: cache upserted, event marked processed, replay is a no-op, revocation never touches `daily_log_summary`/`micronutrient_window`/`anomaly_alerts` (non-destructive, structural guard).

**`GetWeeklyTrendHandler` (query, not Pro-gated):**
- Unentitled user succeeds (assert zero calls to any entitlement port — structurally distinguishes this from the gated queries below).
- Small-N (2 days logged) → returns a result with `sample_size = 2` and the window explicit, not suppressed or padded.
- Large-N (90 days) → correct aggregation.
- Requested window exceeding a defined maximum → repository called with an explicit bounded date range/pagination, never an unbounded "fetch everything" call (assert on the mock repository's call arguments — enforces the plan §7 pagination rule).

**`GetReportHandler` / `ExportReportHandler` (query, Pro-gated, CSV per resolution 4):**
- Entitled user (cache hit) → CSV containing `daily_log_summary` + `micronutrient_window` rows for the requested date range; `export_audit_log` write happens exactly once per successful export call (including on a repeated identical request — every export logs, this is not idempotency-deduplicated, unlike event consumption).
- Unentitled user (cache hit, `entitled=False`) → rejected before any report-data repository read and before any `export_audit_log` write (cheapest-check-first, mirrors `recipe-service`/`social-service`).
- No cache entry → falls back to `EntitlementCheckPort`; result used for this call but never written back to `entitlement_cache` (assert the fake cache repository's write method is never called in this path — the same structural invariant `recipe-service`'s test plan calls "the single most important" one).

## 3. Integration test cases (testcontainers Postgres/RabbitMQ)

- `diary_events_consumer.py`, `profile_events_consumer.py`, `nutrition_calculation_events_consumer.py`, `billing_events_consumer.py` — each: duplicate delivery of the same `event_id` results in exactly one effect; a handler that raises is nacked/requeued up to the configured limit then dead-lettered (per `messaging-conventions/SKILL.md`).
- Postgres repositories — round-trip persistence for all 11 tables from §3 of the implementation plan (`daily_log_summary`, `micronutrient_window`, `weight_trend`, `anomaly_alerts`, `entitlement_cache`, four `processed_*_events` tables, `export_audit_log`, `outbox`).
- `BillingEntitlementClient` — fixture HTTP server: entitled/unentitled responses map correctly; repeated failures trip the `billing_entitlement_check` circuit breaker; recovery verified after `reset_timeout`.
- Outbox relay worker — atomicity: a simulated failure after the DB write but before publish must not lose the `NutrientDeficiencyDetected` event.
- Alembic migration `0001` applies cleanly to an empty database; `downgrade()` verified where feasible.
- CSV export generation — integration test against seeded `daily_log_summary`/`micronutrient_window` rows: correct header row, correct row count for both a small date range (documents the sample-size limitation in the export itself) and a larger one. Includes the leading manifest comment/header row stating row count + date range (resolution to the CSV-manifest question, approved 2026-09-07).

## 4. Contract test cases

- `GET /api/v1/analytics/trends/weekly` — `200` with `sample_size`/`window_days` present in the payload; succeeds for an unentitled user (not gated); `401` unauthenticated.
- `GET /api/v1/analytics/reports/{report_type}` / export endpoint — `200` with `text/csv` content-type for an entitled user; `402`/`NOT_ENTITLED` for an unentitled user (reusing `recipe-service`'s exact convention per the implementation plan §4); `401` unauthenticated.
- `NutrientDeficiencyDetected` (v1) — published payload matches the fleshed-out schema to be added to `docs/events-catalog.md` in Stage B (envelope + `user_id`/`aggregate_id`, `signal`, `window_days`, `value`, `target_min`).
- Contract tests for the 9 **consumed** events' payload shapes, matching their already-documented schemas in `docs/events-catalog.md` (`FoodEntryLogged/Corrected/Deleted`, `WaterIntakeLogged/Removed`, `WeightRecorded`, `NutritionValueRecomputed`, `NutritionTargetUpdated`, `EntitlementGranted/Revoked`).

## 5. E2E test cases

Not built — same reasoning as every prior service's plan (no cross-service E2E harness exists yet). `analytics-service` doesn't complete a new named CLAUDE.md §3 journey; it's additive.

## 6. Event-sourcing-specific cases

Not applicable — CQRS read side only (ADR-0002 addendum), no event-sourced write aggregate of analytics-service's own.

## 7. Coverage expectation

- **Domain** (`trend_calculator`, `anomaly_detector`, 4 value objects): enumerable boundary cases dominate (§1) — expect to clear ≥90% comfortably.
- **Application** (10 command handlers + 3 query handlers, each with 2-5 cases in §2 covering idempotent replay, entitlement gating, cooldown/dedup, and the never-write-back-on-fallback invariant): expect to clear ≥85%.
- **Infrastructure** (4 consumers' idempotency/DLQ, 11 repositories, circuit-breaker matrix, outbox relay, migration, CSV generation, contract groups in §3-4): expect to clear ≥70%. This is the layer most likely to be tight given the number of distinct adapters (4 consumers × idempotency+DLQ, 11 repos) — actual numbers will be reported rather than assumed.

## 8. Fixtures (built, not sourced)

- `tests/fixtures/diary_events/*.json`, `profile_events/*.json`, `nutrition_calculation_events/*.json`, `billing_responses/*.json` — fixture payloads for consumer/client tests, matching `docs/events-catalog.md`'s documented shapes.
- No real call to `diary-service`, `profile-service`, `nutrition-calculation-service`, or `billing-service` anywhere in the suite.

## Flagged for review (not a blocker)

The CSV export carries a leading manifest comment/header row stating row count and date range, consistent with CLAUDE.md's "never present a statistic without sample size and window" rule applied to an export rather than just an API response — approved as the default 2026-09-07. Flagged alongside the already-flagged `export_audit_log` schema and the dev-default deficiency threshold (implementation plan §9 resolution 2) for `security-agent`/`architecture-agent` review before prod promotion.
