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

## Addendum — 2026-09-11: Fitbit adapter (mocked, no real credentials) test plan

Implements `/plans/activity-service/implementation-plan.md`'s "Addendum — 2026-09-11 ... Fitbit adapter (mocked, no real credentials) approved." Scope is strictly the `WearableProviderPort` implementation for Fitbit (OAuth 2.0 Authorization Code exchange + refresh, the `sync` method, `disconnect`/revoke) plus the feature-flag gate in the composition root — no application-layer command/route, no dedup logic, matching the addendum's explicit scope (see the implementation summary's "Deviations" section for the reasoning).

All cases below run against `httpx.MockTransport` fixture responses only — never a live Fitbit call, matching `StripePaymentAdapter`'s and `ClaudeVisionAdapter`'s existing test convention in this repo.

### 1. Domain unit test cases

**`WearableOAuthTokens` value object:**
- Valid access/refresh token + future `expires_at` → constructed.
- Empty `access_token` or `refresh_token` → raises `InvalidWearableTokensError`.
- `repr()`/`str()` never include the raw `access_token`/`refresh_token` values (redacted, mirroring `identity-service`'s `Password` value object) — asserted by checking the token strings do not appear as substrings of `repr(tokens)`/`str(tokens)`.
- `is_expired(now)` — `True` once `now >= expires_at`, `False` before.

**`WearableSyncResult` value object:**
- Valid construction with a mapped `ExerciseType`, `DurationMinutes`, `CaloriesBurned`, `started_at`, `provider_activity_id`, optional `label`.
- Never claims more precision than the provider reports — `calories_burned` is constructed directly from Fitbit's reported integer kcal figure, never a computed/interpolated value (structural test: adapter-level test asserts the parsed value equals the fixture's raw `calories` field, no arithmetic applied).

### 2. Application/infrastructure unit & integration test cases — `FitbitProviderAdapter`

**OAuth connect (token exchange):**
- Valid `authorization_code` → adapter POSTs to Fitbit's token endpoint with `grant_type=authorization_code`, `Authorization: Basic <base64(client_id:client_secret)>`; on a 200 fixture response, tokens are persisted via `WearableTokenStorePort.save()`.
- Fitbit responds 400 (`invalid_grant` — e.g. an already-used or expired code) → raises `WearableProviderUnavailableError` (or a more specific typed error), nothing persisted to the token store.
- **Non-idempotent-operation rule**: a transient transport failure (simulated `httpx.ConnectError`) during token exchange is **never retried** — asserted by counting exactly one outbound request attempt — because an authorization code is single-use; a blind retry could burn the user's one-time code. Documented deviation from `sync()`'s retry behavior below.
- Circuit breaker: 5 consecutive transport/5xx failures open the `fitbit_oauth` circuit; the 6th call fails fast with zero additional outbound requests; recovers (half-open → closed) after `reset_timeout`.
- Explicit timeout: a fixture handler that never returns within the configured read timeout raises a timeout-derived `WearableProviderUnavailableError` (simulated via `httpx.MockTransport` raising `httpx.ReadTimeout`, never a real slow dependency, per resilience-patterns SKILL.md's Testing Requirements).

**Token refresh:**
- `sync()`/`disconnect()` called with a stored token whose `expires_at` is in the past → adapter calls the refresh endpoint (`grant_type=refresh_token`) before proceeding, and persists the rotated access/refresh token pair (Fitbit rotates refresh tokens on every use — asserted by checking the OLD refresh token is no longer stored after a refresh).
- Refresh transport failure → also never retried (same single-use-grant reasoning as token exchange — Fitbit invalidates the presented refresh token on use, so a blind retry with the same value cannot succeed twice), wrapped by its own circuit breaker (`fitbit_oauth`, shared with token exchange since both hit the same OAuth token endpoint/failure domain).
- No stored token for the user at all → raises `WearableConnectionNotFoundError`, never attempts a network call.

**Sync:**
- Valid stored (fresh) token, `since` timestamp → adapter GETs Fitbit's activity-logs-list endpoint with an `afterDate` query param derived from `since`; a 200 fixture response with 2 activities is parsed into 2 `WearableSyncResult`s with correctly mapped fields.
- An unrecognized Fitbit `activityName` maps to `ExerciseType.OTHER` with the raw name preserved only in `label` (never folded into the enum — same rule as manual entries' `ExerciseType.OTHER`/`label` split).
- Empty `activities` array → returns `[]`, not an error.
- Transient transport failure → retried up to 3 attempts (exponential backoff+jitter) since a GET fetch is a safe-to-retry read with no side effect — contrast with connect/refresh above.
- Circuit breaker: separate, dedicated `fitbit_activities_sync` breaker from `fitbit_oauth` — a sync-endpoint outage does not trip the breaker guarding the ability to (re)connect/refresh, and vice versa. Same fail_max/reset_timeout/recovery cases as the OAuth breaker.
- No stored token for the user → raises `WearableConnectionNotFoundError`, never attempts a network call.

**Disconnect:**
- Stored token exists → the local token-store record is deleted **before** (or regardless of the outcome of) the outbound revoke call — asserted by making the revoke call always fail (500) and confirming the token store no longer returns a record for that user afterward, and that a subsequent `sync()` call raises `WearableConnectionNotFoundError` rather than silently succeeding — this is the concrete test for `.claude/agents/activity-agent.md`'s "a wearable disconnection/revocation must be honored immediately" rule.
- Revoke call succeeds → same outcome (record deleted, subsequent `sync()` raises).
- No stored token for the user → idempotent no-op, no error, no network call attempted.

### 3. Idempotency

- Calling `disconnect()` twice in a row for the same user is idempotent — second call is a no-op (case above), matching this codebase's "safe to receive/replay the same operation" convention even though this isn't a message-consumer in the RabbitMQ sense.
- `sync()` is a pure read — replaying the same `since` value against the same fixture returns the same `WearableSyncResult` list both times (no state mutation as a side effect of a bare `sync()` call: this addendum does NOT implement the write side of sync consumption — no `ExerciseEntry`/outbox write, no dedup against manual entries — see scope note above and the implementation summary's "Deviations" section). A real double-count-prevention idempotency test belongs to the future addendum that adds the application-layer consumer.

### 4. Feature-flag gating (composition root)

- `Settings.from_env()` reads `ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED` (default `False`), `ACTIVITY_SERVICE_FITBIT_CLIENT_ID`/`_CLIENT_SECRET`/`_REDIRECT_URI` (default empty string).
- `Container.fitbit_provider` raises `WearableSyncDisabledError` when the flag is `False`, regardless of whether credentials are configured.
- `Container.fitbit_provider` raises `WearableSyncDisabledError` when the flag is `True` but `fitbit_client_id`/`fitbit_client_secret` are empty (no real credentials exist in this environment today — this is expected to raise in every real deployment of this repo until a human provisions a Fitbit developer account, per the addendum).
- `Container.fitbit_provider` returns a working `FitbitProviderAdapter` only when the flag is `True` AND both credential fields are non-empty (achievable only in a test that sets fixture/dummy credential strings, never a real deployment today).

### 5. Coverage expectation

`WearableOAuthTokens`/`WearableSyncResult` are small value objects — expect near-100%, comfortably clearing the domain ≥90% floor. `FitbitProviderAdapter`'s and the token-store adapter's branches (success, 4xx, transport failure/no-retry, transport failure/retry, breaker-open, timeout, disconnect-always-clears-local-state) are enumerated above with the explicit intent of clearing the infrastructure ≥70% floor with real branch coverage, not incidental coverage. The feature-flag gating cases in §4 exercise `Container`/`Settings`, also infrastructure-layer.
