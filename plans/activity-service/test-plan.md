# Test Plan — `activity-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/activity-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases

**Value objects:**
- `ExerciseType` — each enumerated value (`running`, `walking`, `cycling`, `strength_training`, `swimming`, `other`) accepted; an unrecognized string raises.
- `DurationMinutes(0)` raises (must be positive); `DurationMinutes(1)` accepted; `DurationMinutes(-5)` raises.
- `CaloriesBurned(0)` accepted (a very light/short activity can genuinely be ~0); `CaloriesBurned(-1)` raises (never negative).

**`LogExerciseHandler` (fake repository, fake outbox):**
- Valid command → entry persisted, `ExerciseLogged` published with matching payload (type/duration/calories/occurred_at/user_id).
- `exercise_type="other"` with a free-text label → label persisted and returned, but confirmed **not** part of the published event's aggregable fields (a structural assertion: the event payload's `exercise_type` is still the enum value `other`, the label is a separate, clearly-secondary field) — guards against the free-text label silently becoming a de facto second taxonomy.

**`UpdateExerciseHandler`:**
- Existing entry, valid field update → persisted change reflected on read-back; no new `ExerciseLogged` event double-published incorrectly (confirm exactly one publish per handler invocation, not zero and not two).
- Non-existent `entry_id` → raises a typed not-found error, no repository write attempted.
- Soft-deleted entry → update rejected (can't correct a deleted entry), typed error.

**`DeleteExerciseHandler`:**
- Existing entry → soft-deleted (row remains, `deleted_at` set), never a hard row delete (assert the fake repository's delete method is never called, only its soft-delete/update path).
- Already-deleted entry → idempotent no-op (deleting twice doesn't raise, doesn't double-publish).

**`ListExercisesForDateHandler`:**
- Multiple entries on the queried date → all returned, ordered by `occurred_at`.
- A soft-deleted entry on the queried date → excluded from the list.
- No entries on the queried date → empty list, not an error.
- Entries belonging to a different user → never returned (user-scoping enforced at the query level, not just trusted from the caller).

## 2. Integration test cases

- `PostgresExerciseRepository` — round-trip persistence via testcontainers Postgres: create/update/soft-delete/list-by-date-and-user, same convention as every other service.
- `PostgresOutboxRepository` / outbox relay worker — appending an event and the outbox row happens atomically (a simulated failure after the DB write but before the publish must not lose the event — still relayed on retry), per `messaging-conventions/SKILL.md` §Testing Requirements.
- Alembic migration `0001` applies cleanly to an empty database.
- `RabbitMQEventPublisher` — a published `ExerciseLogged` event's payload matches the documented schema in `docs/events-catalog.md`, via a real (testcontainers) RabbitMQ round-trip.

## 3. Contract test cases

- `POST /api/v1/activity/exercises` — `201` with the created entry for a valid payload; `422` for a missing/invalid field (negative duration, unrecognized exercise type); `401` unauthenticated.
- `PATCH /api/v1/activity/exercises/{entry_id}` — `200` on a valid update; `404` for a non-existent or another user's entry (never leak existence of another user's entry via a `403` vs `404` distinction); `422` for an invalid field value.
- `DELETE /api/v1/activity/exercises/{entry_id}` — `204` on success (soft delete); `404` for non-existent/another user's entry; a second `DELETE` on an already-deleted entry is idempotent (`204`, not `404` — matches the unit-level idempotent-soft-delete case).
- `GET /api/v1/activity/exercises?date={date}` — `200` with the authenticated user's entries for that date only; `422` for a malformed date.
- `ExerciseLogged` (v1) — published payload matches `docs/events-catalog.md`'s documented schema.

## 4. E2E test cases

**None added in this plan.** None of CLAUDE.md §3's three critical journeys exercise `activity-service` as a required step. Deferred, not silently dropped, consistent with `notification-service`'s and `bff-service`'s precedent for services outside the critical-journey set.

## 5. Event-sourcing-specific cases

**Not applicable.** `activity-service` uses conventional persistence + event-driven CRUD (implementation plan §2), not event sourcing.

## 6. Coverage expectation

Domain layer (`ExerciseType`, `DurationMinutes`, `CaloriesBurned`) is small and simple — expect close to 100%, comfortably clearing the ≥90% floor. Application layer's four handlers each have 2-4 cases above, deliberately covering not-found/already-deleted/cross-user edge cases and not just the happy path — clears the ≥85% floor. Infrastructure layer's repository, outbox, migration, and publisher integration tests plus the contract-test group in §3 are expected to clear the ≥70% infrastructure floor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.

## 7. Fixtures (built, not sourced)

- No external-provider fixtures in this plan — no wearable adapter exists to fixture against (implementation plan §1). All fixtures are this service's own request/response payloads for its own contract tests.
