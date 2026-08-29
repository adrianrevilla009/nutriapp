# Test Plan — `bff-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/bff-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases

**`SectionStatus` value object:**
- `SectionStatus.available(data)` — carries the data, `status="available"`.
- `SectionStatus.unavailable(reason="downstream_error")` and `SectionStatus.unavailable(reason="not_yet_computed")` — no data, `status="unavailable"`, reason preserved; an unrecognized reason string raises (closed set, not a free-text field).

**`GetDashboardHandler`** (fake `DiarySummaryPort`, `NutritionTotalsPort`, `NutritionTargetPort`):
- All three calls succeed → response has all three sections `available`, each carrying the faked downstream data reshaped into the response schema (assert field-level mapping, not just "non-null").
- `DiarySummaryPort` raises (simulating circuit open) → `diary_summary` section is `unavailable/downstream_error`, the other two sections still `available` — confirms one failing dependency never blocks the others (the three calls are awaited via `asyncio.gather` with exceptions captured, not raised through).
- `NutritionTotalsPort` raises → same pattern, only `nutrient_totals` degraded.
- `NutritionTargetPort` raises with a generic/transport error → `target` section `unavailable/downstream_error`.
- `NutritionTargetPort` returns an explicit "no target computed yet" result (not an exception — a documented empty/404-mapped case per the known `Sex.OTHER`/deferred-recompute gap) → `target` section `unavailable/not_yet_computed`, distinct from the error case above (assert the `reason` field differs between these two tests, not just that both are `unavailable`).
- All three calls raise → response is still a `200` with all three sections `unavailable` (never a `5xx` for the whole endpoint — this is the core resilience guarantee of this handler, tested explicitly as its own case, not just implied by the three single-failure cases).
- Confirms **no computed/business value appears anywhere in the handler** — a structural test asserting the handler's own source contains no arithmetic/comparison operators beyond what's needed for basic response assembly (a lightweight guardrail against business-logic creep, mirroring `food-recognition-service`'s "never writes to diary-service" structural test precedent).

## 2. Integration test cases

- `DiaryServiceClient` — against a fixture HTTP server: a well-formed response maps correctly into the port's return shape; a `401`/`5xx`/timeout from the fixture server triggers the client's own circuit breaker after the configured failure threshold (call-count assertions show fast-fail once open), and a successful trial call after `reset_timeout` recovers it (half-open → closed, per `resilience-patterns/SKILL.md` §Testing Requirements).
- `NutritionCalculationServiceClient` — same three-part matrix (success, circuit trips, recovers) **run independently for its two methods** (`get_totals`, `get_target`), asserting the two breakers are independently named and tripping one does not affect the health of the other (a call-count assertion: with the totals breaker open, a `get_target` call still reaches the fixture server).
- `NutritionCalculationServiceClient.get_target` — additionally: a fixture `404`/empty response (the documented "not yet computed" case) maps to the `not_yet_computed` reason, not raised as an unhandled error and not conflated with a real transport failure.
- Alembic/migration: **not applicable** — no database, no migration to test.

## 3. Contract test cases

- `GET /api/v1/bff/dashboard?date={date}` — `200` with all three sections populated for a mocked all-succeed downstream state; `200` (not `5xx`) with a mix of `available`/`unavailable` sections for each single-dependency-failure scenario and the all-fail scenario; `401` for a missing/invalid `Authorization` header (before any downstream call is attempted — verified via the fixture downstream servers receiving zero requests in this case); `422` for a malformed/missing `date` query parameter.
- Response schema conformance: every section's shape (`available` vs. both `unavailable` variants) matches a fixed JSON schema, exercised for all documented section-status combinations, not just the happy path.

## 4. E2E test cases

**None added in this plan.** `bff-service`'s dashboard endpoint is a read aggregation over data created via the actual critical journey (CLAUDE.md §3 journey 1: register → log a food item → see totals) — that journey's own E2E test (owned by whichever service's test suite covers the full journey, if/when one exists) is the right place to exercise the real end-to-end path; this plan's own tests are fixture-based per §1/§2, consistent with every other service's precedent of not making live cross-service calls in its own test suite.

## 5. Event-sourcing-specific cases

**Not applicable.** `bff-service` publishes and consumes no events, owns no aggregate (implementation plan §2).

## 6. Coverage expectation

Domain layer (`SectionStatus`) is trivial — expect 100%, comfortably clearing the ≥90% floor. Application layer's single handler has 7 cases above covering every success/failure/degraded combination and the business-logic-creep guardrail — clears the ≥85% floor with room to spare given how small the surface is. Infrastructure layer's two clients (three methods total across them) each get the full circuit-breaker matrix plus the target-endpoint's two-reason-mapping case, plus the contract tests in §3 — expected to clear the ≥70% infrastructure floor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.

## 7. Fixtures (built, not sourced)

- `tests/fixtures/downstream_responses/diary_summary_*.json`, `nutrition_totals_*.json`, `nutrition_target_*.json` (including a `target_not_yet_computed.json` variant) — hand-authored, matching each real service's actual current response schema (read from that service's own Pydantic response model, not guessed).
- No real call to `diary-service` or `nutrition-calculation-service` anywhere in this suite.
