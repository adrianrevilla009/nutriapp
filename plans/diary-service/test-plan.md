# Test Plan — `diary-service`

**Status:** Approved
**Date approved:** 2026-08-26
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/diary-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD (`.claude/skills/testing-strategy/SKILL.md`). The implementation plan's §9.2 (simple open-window fasting check) and §9.6 (`meal_slot`/unit vocabulary) resolutions are treated as settled here.

## 0. Assumptions carried from the implementation plan (restated, not re-derived)

- `meal_slot`: `breakfast | lunch | dinner | snack`.
- `quantity` unit: `g | ml | serving`.
- Fasting overlap check: reject a new `FastingWindowStarted` if the user already has an open (unended) window — no interval-overlap math against closed windows.
- `source.source_type` for this plan is always `catalog_product`; `recipe`/`ai_detected` are reserved values not exercised by any test here (no adapter produces them yet).

## 1. Unit test cases

### Domain layer (no mocking, no I/O)

**Value objects**
- `Quantity`: positive amount + supported unit accepted; zero/negative amount raises `InvalidQuantityError`; unsupported unit string raises.
- `MealSlot`: only the four documented values valid; unknown value raises.
- `FoodSource`: valid `source_type="catalog_product"` + non-empty `source_reference_id` + complete snapshot accepted; missing `source_reference_id` raises; snapshot with negative macro values raises.
- `WaterAmountMl`: positive value accepted; zero/negative raises `InvalidWaterAmountError`.
- `TimeWindow`: `end` before `start` raises `InvalidTimeWindowError`; `end` absent (still open) is a valid state.

**`FoodEntry` aggregate**
- `rebuild([FoodEntryLogged])` yields an aggregate with the logged source/meal_slot/timestamp.
- `correct()` on a logged entry produces `FoodEntryCorrected`; `rebuild([FoodEntryLogged, FoodEntryCorrected])` yields the *corrected* values, with the original `FoodEntryLogged` event still present, unmodified, in the replayed stream.
- `correct()` called twice: second correction's replay yields the *latest* correction's values (last-write-wins over the derived state, all corrections retained in history).
- `delete()` produces `FoodEntryDeleted`; `rebuild()` including this event yields a `deleted=True` derived state; `correct()` after deletion raises `EntryAlreadyDeletedError`.

**`WaterIntakeEntry` aggregate**
- `rebuild([WaterIntakeLogged])` yields the logged amount.
- `remove()` produces `WaterIntakeRemoved`; `rebuild()` including it yields `removed=True`; `remove()` called twice raises `EntryAlreadyRemovedError`.

**`FastingWindow` aggregate (per-user, holds a collection of windows)**
- `start_window()` on a user with no existing windows produces `FastingWindowStarted`.
- `start_window()` on a user whose latest window has no `ended_at` yet (open) raises `OverlappingFastingWindowError` — **no event produced** (§9.2's resolved policy).
- `start_window()` on a user whose latest window *is* ended succeeds, producing a second `FastingWindowStarted` for a new `window_id`.
- `end_window(window_id)` on that user's open window produces `FastingWindowEnded`.
- `end_window(window_id)` on an already-ended window raises `WindowAlreadyEndedError`.
- `end_window(window_id)` for a `window_id` that doesn't belong to this user's aggregate raises `WindowNotFoundError`.
- Full replay: `rebuild([Started(w1), Ended(w1), Started(w2)])` yields exactly one open window (`w2`) and one closed window (`w1`) in derived state — the core rebuild test for this aggregate's collection-of-entities shape.

**`MealPlanEntry` aggregate**
- `rebuild([MealPlanned])` yields the planned source/meal_slot/planned_for.
- `update()` produces `MealPlanUpdated`; replay yields the updated values, original `MealPlanned` retained unmodified.
- `remove()` produces `MealPlanRemoved`; `update()`/`remove()` after removal raise `PlanEntryAlreadyRemovedError`.

**`fasting_overlap_policy`** (isolated unit tests beyond the aggregate-level cases above, covering the policy function directly with constructed state)
- Empty window list + start request: always accepted.
- Window list with exactly one open window + start request: always rejected.
- Window list with only closed windows (any count) + start request: always accepted.

## 2. Integration test cases (infrastructure layer, testcontainers Postgres + RabbitMQ + Redis)

- `PostgresEventStore`: append then load-stream round-trip for each of the 4 `aggregate_type` values, confirming no cross-contamination between aggregate types sharing the one `diary_events` table.
- `PostgresEventStore`: concurrent append to the *same* `aggregate_id` (simulating a race) is serialized correctly (optimistic concurrency check on the aggregate's version/sequence) — this is the one place `diary-service`'s higher write concurrency (vs. `profile-service`) needs an explicit test, since two client requests correcting/deleting the same food entry near-simultaneously is a realistic scenario this service must not silently corrupt.
- `PostgresFoodEntriesProjector` / `PostgresWaterIntakeProjector` / `PostgresFastingWindowsProjector` / `PostgresMealPlanProjector`: each, given a fixed event sequence, produces the expected read-model row(s) — one **rebuild/replay test per projector**, per `cqrs-event-sourcing` SKILL.md's "single most important test category."
- `PostgresDailySummaryProjector`: given a mixed sequence of `FoodEntryLogged`, `WaterIntakeLogged`, and a `FastingWindowEnded` all on the same day for one user, produces a correctly aggregated daily summary row (this projector is the one fed by *all* event types, so its replay test must exercise at least one event from each of the 4 aggregate types together).
- `diary_event_projector_consumer` **idempotency test**: the same `FoodEntryLogged` event delivered twice (simulating RabbitMQ's at-least-once redelivery) results in exactly one row in `food_entries_view` and exactly one corresponding update to `daily_summary_view` — the mandatory idempotency test called out in acceptance criterion 8.
- `OutboxRelayWorker`: same shape as `profile-service`'s equivalent test — a row inserted in the same transaction as an event append is published; a publish failure leaves it retryable.
- `RedisDailySummaryCache`: cache miss on first `GET .../summary` populates the cache; a subsequent event affecting that user+date invalidates exactly that key, not other users'/dates' cached summaries.
- `scripts/rebuild_read_models.py`: given a non-trivial fixed event history across all 4 aggregate types for at least two users, truncating all 5 read-model tables and running the rebuild script reproduces byte-for-byte the same read-model state the async projectors produced originally — the acceptance-criterion-7 "actual runnable rebuild capability" test, mirroring `profile-service`'s precedent test for its own rebuild script.
- Alembic migration `0001`: applies cleanly to an empty database.

## 3. Contract test cases

- `POST /api/v1/diary/food-entries`, `PATCH .../food-entries/{id}`, `POST/DELETE .../water-intake`, `POST .../fasting-windows/start|{id}/end`, `POST/PATCH/DELETE .../meal-plan` — each endpoint's request/response schema matches its documented OpenAPI contract; each returns `401` with no valid JWT (reusing `JwtVerifier`'s already-contract-tested behavior from `profile-service`, only the wiring is new here) and `403`/`404` for cross-user access attempts (e.g. `PATCH` another user's `entry_id`).
- `POST .../fasting-windows/start` while a window is already open — contract-tests the `409 Conflict` (or equivalent documented status) mapping for `OverlappingFastingWindowError`, not just the domain-level raise.
- All 10 new events (`FoodEntryLogged`, `FoodEntryCorrected`, `FoodEntryDeleted`, `WaterIntakeLogged`, `WaterIntakeRemoved`, `FastingWindowStarted`, `FastingWindowEnded`, `MealPlanned`, `MealPlanUpdated`, `MealPlanRemoved`) — published payload for each matches its corresponding `packages/shared-contracts/schemas/*.v1.json` file.

## 4. E2E test cases

**None added in this plan**, for the same reason as `catalog-service`'s test plan: critical journey #1 (`docs/testing-strategy.md` §2.4) needs `catalog-service` and `nutrition-calculation-service` live alongside this service before a real end-to-end test is meaningful; both are either in-progress (`catalog-service`, parallel plan) or not yet planned (`nutrition-calculation-service`). Deferred, not dropped — noted explicitly rather than faked with mocked upstream services.

## 5. Event-sourcing-specific cases

`diary-service` is one of ADR-0002's two full-event-sourcing-mandatory services, so this section is directly applicable (in addition to, not instead of, §1's per-aggregate rebuild tests and §2's per-projector replay tests already covering the letter of this requirement):
- **Rebuild-from-events**: covered per aggregate in §1 (one dedicated full-replay case per aggregate type, four total) — the `FastingWindow` case is the most load-bearing since it's the one aggregate with genuinely stateful derived collections (open vs. closed windows), not just "latest value wins."
- **Idempotency**: covered in §2 for `diary_event_projector_consumer` — required per acceptance criterion 8, since this is the first *new* consumer introduced in this plan (unlike `profile-service`'s `UserRegistered` consumer, this one consumes `diary-service`'s own published events, but the at-least-once redelivery guarantee and the resulting idempotency requirement are identical).
- **Version/concurrency**: the `PostgresEventStore` concurrent-append test in §2 is this plan's equivalent of a correctness guarantee `profile-service` didn't need to test as rigorously, given `diary-service`'s higher expected concurrent-write rate per aggregate — included here as a event-sourcing-specific case, not a generic infra test.

## 6. Coverage expectation

Touches all three layers. Domain layer carries the heaviest case count (4 aggregates × rebuild/invariant cases, `fasting_overlap_policy`, 5 value objects) to comfortably clear ≥90% — this is also where the plan's one genuine new invariant (fasting-window overlap) lives, so it gets proportionally more scrutiny than a typical value-object-only service. Application-layer command/query handlers (10 commands + 5 queries) each get a success-path and documented-error-path test against fake ports, targeting ≥85%. Infrastructure's §2 integration matrix (event store × 4 aggregate types, 5 projectors, the projector-consumer idempotency test, outbox, cache, rebuild script) plus §3's contract tests are expected to clear ≥70% infrastructure coverage, matching or exceeding `profile-service`'s precedent (99.4%/97.2%/88.4% actuals) given comparable design rigor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.
