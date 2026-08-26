# Test Plan — `profile-service`

**Status:** Approved
**Date approved:** 2026-08-24
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/profile-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD
(`.claude/skills/testing-strategy/SKILL.md`). §9.3 of the implementation
plan left `goal_policy` rules undefined; concrete rules are pinned down
below as **(assumption)**, same convention `identity-service`'s test plan
used for its own open points.

## 0. `goal_policy` rules assumed for this test plan

**(assumption)** — flag for correction if wrong, before `/implementation-execution`:
- `target_date` is required when `goal_type` is `lose` or `gain`; optional (and ignored if given) when `goal_type` is `maintain`.
- `target_value` is required for `lose`/`gain`, optional for `maintain`.
- For `lose`: `target_value` must be strictly less than the most recently recorded weight, if one exists; if no weight has been recorded yet, the check is skipped (nothing to compare against) rather than blocking goal-setting.
- For `gain`: `target_value` must be strictly greater than the most recently recorded weight, same skip-if-absent rule.
- `target_date`, when given, must be in the future relative to `set_at`/`update_at`.
- No bound on the magnitude of `target_value` itself (no domain-level min/max weight) — out of scope for a policy check, would be a UX-layer concern at most.

## 1. Unit test cases

### Domain layer (no mocking, no I/O)

**Value Objects**
- `WeightKg`: valid positive value accepted.
- `WeightKg`: zero or negative value raises `InvalidWeightError`.
- `HeightCm`: valid positive value accepted; zero/negative raises `InvalidHeightError`.
- `Age`: valid value (e.g. 1–120) accepted; out-of-range raises `InvalidAgeError`.
- `Sex`: only documented enum values valid; unknown value raises.
- `ActivityLevel`: only documented enum values valid; unknown value raises.
- `GoalType`: only `LOSE`/`MAINTAIN`/`GAIN` valid; unknown value raises.
- `GoalTarget`: constructing with `target_date` in the past raises `InvalidGoalTargetError`.

**`Profile` aggregate**
- `rebuild([ProfileCreated])` yields an aggregate with no metrics, no goal, consent not granted.
- `rebuild([ProfileCreated, BiometricConsentGranted])` yields `consent_granted = True`.
- `record_weight()` before consent is granted raises `ConsentRequiredError` — no event produced.
- `record_weight()` after consent produces a `WeightRecorded` event and updates current snapshot state to that value.
- `record_weight()` called twice: second call produces a second `WeightRecorded` event; the first is retained in the stream unmodified (correction-as-new-event, never mutated).
- `record_body_metric("height", ...)` / `("age", ...)` / `("sex", ...)` / `("activity_level", ...)` each produce a `BodyMetricRecorded` event with the matching `metric_type`.
- `record_body_metric()` with an unsupported `metric_type` raises `UnsupportedMetricTypeError`.
- `set_goal()` on an aggregate with no existing goal produces `GoalSet`.
- `set_goal()` on an aggregate that already has a goal raises `GoalAlreadyExistsError` — caller must use `update_goal()` instead **(assumption: `set_goal` is create-only, `update_goal` is the only path to change an existing goal)**.
- `update_goal()` on an aggregate with an existing goal produces `GoalUpdated` carrying `previous_goal_type`.
- `update_goal()` on an aggregate with no goal yet raises `NoExistingGoalError`.
- Full replay: `rebuild()` over `[ProfileCreated, BiometricConsentGranted, WeightRecorded(70kg), WeightRecorded(68kg), GoalSet(lose, 65kg)]` yields a snapshot with current weight `68kg` (latest wins) and the set goal — this is the aggregate's core rebuild test.

**`goal_policy`** (see §0 assumptions)
- `lose` goal with `target_value` < latest recorded weight: accepted.
- `lose` goal with `target_value` >= latest recorded weight: rejected with `InvalidGoalTargetError`.
- `lose` goal with no weight recorded yet: `target_value` check skipped, accepted (assuming other fields valid).
- `gain` goal with `target_value` > latest recorded weight: accepted; `<=` rejected; no-weight-yet skips the check, same as `lose`.
- `maintain` goal: `target_date`/`target_value` may be omitted entirely; if given, no comparison check applies.
- `lose`/`gain` goal missing `target_date`: rejected with `MissingGoalTargetDateError`.
- `target_date` in the past (relative to injected clock): rejected, regardless of goal type.

### Application layer (fake/in-memory ports)

**`CreateProfileOnUserRegisteredHandler`**
- Valid `UserRegistered` event, not previously processed: profile created, `event_id` recorded in `ProcessedEventsPort`.
- Same `event_id` delivered twice: second delivery is a no-op (idempotency test) — no second `ProfileCreated`, no error.

**`GrantBiometricConsentHandler`**
- First grant: `BiometricConsentGranted` appended + outboxed.
- Second grant on an already-consented profile: idempotent no-op, no duplicate event **(assumption: granting is idempotent, not an error)**.

**`RecordWeightHandler`**
- Consent granted: `WeightRecorded` persisted + enqueued to outbox in the same unit of work; value passed through `DataEncryptionPort` before persistence.
- Consent not granted: rejected with `ConsentRequiredError`, nothing persisted, nothing outboxed.

**`RecordBodyMetricHandler`**
- Mirrors `RecordWeightHandler` cases for each of the four `metric_type` values, consent-gated identically.

**`SetGoalHandler` / `UpdateGoalHandler`**
- Valid input passing `goal_policy`: event persisted + outboxed.
- Input failing `goal_policy`: rejected before any repository call, no event produced.

**`GetProfileSnapshotHandler`**
- Existing profile: returns current snapshot DTO built from the read model (not from event replay).
- Unknown `user_id`: `ProfileNotFoundError`.

**`GetEvolutionTimelineHandler`**
- Returns entries filtered by `metric` and `[from, to]` window, ordered chronologically.
- Empty range (no entries in window): returns an empty list, not an error.

## 2. Integration test cases (testcontainers: Postgres, RabbitMQ)

- `PostgresEventStore`: append→load round-trip preserves event order for a given `user_id`; loading an unknown `user_id` returns an empty stream (not an error) so `rebuild()` can produce the "no profile yet" case cleanly.
- `PostgresSnapshotProjector`: consuming a fixed sequence of events (`ProfileCreated`, `BiometricConsentGranted`, two `WeightRecorded`, one `GoalSet`) produces the exact expected `profile_snapshot` row — **this is the mandatory projector-replay test** per `.claude/skills/cqrs-event-sourcing/SKILL.md`.
- `PostgresEvolutionProjector`: same fixed sequence produces the expected ordered `profile_evolution` rows, one per metric event, correction events appended (not overwritten) as extra rows.
- Outbox: event append + outbox row insert atomic (simulated failure between them leaves neither persisted); relay worker publishes pending rows once, doesn't republish already-published ones; simulated crash mid-relay doesn't lose the event — same three cases as `identity-service`'s outbox tests, new instance.
- `PostgresProcessedEventsRepository`: `already_processed()` round-trip; TTL expiry behavior (a sufficiently old processed-event record is treated as eligible for reprocessing per the configured TTL) — **(assumption: TTL long enough to exceed realistic RabbitMQ redelivery windows, exact value to be set at implementation time and documented in `profile-service/README.md`, per messaging-conventions)**.
- `KmsEnvelopeDataEncryption`: encrypt→decrypt round-trip for a given user's key; two different users' ciphertexts for the same plaintext differ; a decrypt attempt using a different user's key fails.
- `KmsEnvelopeDataEncryption` resilience (per `.claude/skills/resilience-patterns/SKILL.md`): circuit opens after the configured consecutive-failure threshold on simulated KMS failures; calls fail fast (typed exception) while the circuit is open, rather than hanging; circuit transitions half-open → closed after `reset_timeout` once KMS calls succeed again; an explicit timeout is enforced on the KMS call (simulated via an injected slow client, not a real slow dependency).
- `RabbitMqEventPublisher`: publishes to the correct exchange/routing key per `messaging-conventions` naming (`profile-service.profile.<event_type_snake_case>`), consumable by a test subscriber.
- `user_registered_consumer`: a nacked/failed message is requeued up to the configured limit, then routed to the dead-letter queue rather than retried forever or dropped silently.

## 3. Contract test cases

**HTTP**, happy path + error path against the OpenAPI schema, for every endpoint: `POST /consent`, `POST /metrics/weight`, `POST /metrics/body`, `POST /goal`, `PUT /goal`, `GET /profile`, `GET /profile/evolution`. Notable cross-cutting assertions:
- Every metric-writing endpoint returns `403` with a consistent error shape when consent hasn't been granted.
- No response body ever contains raw (unencrypted-at-rest-equivalent) values inconsistent with what's stored — i.e., the API returns decrypted plaintext to the authenticated owner, but the persisted representation is always the encrypted form (asserted at the integration layer, not here).
- `GET /profile` for a user with no profile yet (edge case: called before the `UserRegistered` consumer has processed, or for an unknown `user_id`) returns `404`, not a `500` or an empty-but-200 body.

**Event schema contracts** (`docs/events-catalog.md`):
- `WeightRecorded` (v1, new) — `user_id`, `weight_kg`, `recorded_at`; documented consumers (`nutrition-calculation-service`, `analytics-service`) don't exist yet, so no live cross-service contract test runs against them — this test asserts the payload matches the catalog entry shape only.
- `BodyMetricRecorded` (v1, new) — `user_id`, `metric_type` (one of the four documented values), `value`, `recorded_at`.
- `GoalSet` (v1, new) — `user_id`, `goal_type`, `target_value`, `target_date`, `set_at`.
- `GoalUpdated` (v1, new) — same shape plus `previous_goal_type`.
- `UserRegistered` (v1, consumed) — `profile-service`'s consumer test asserts it correctly handles the existing documented schema, including the `email_verification_token_reference_id` field it doesn't use (forward-compatible: an unused field must not break parsing).
- Idempotent-consumption test for `UserRegistered` (already listed in §1's `CreateProfileOnUserRegisteredHandler` cases, and exercised again at the integration layer in §2) — this is `profile-service`'s obligation as the consumer, per `identity-service`'s test plan §3 note.

## 4. E2E test cases

**None for this change.** Journey 1 in `docs/testing-strategy.md` §2.4
("Register → log a food item → see totals") doesn't require `profile-service`
directly, and no other listed journey touches it yet. The consent +
metric-recording flow built here becomes a fixture once `diary-service`
and `nutrition-calculation-service` exist and a profile-dependent journey
is added to the E2E set.

## 5. Event-sourcing-specific cases

**Applies** — `profile-service` is one of the two full-ES services (ADR-0002), alongside `diary-service`.
- **Rebuild-from-events test**: covered in §1 ("Full replay" case) — a fixed event sequence must fold to the exact expected aggregate state.
- **Idempotency test for the new consumer** (`UserRegistered`): covered in §1 and §2 — processing the same `event_id` twice must not double-create a profile or duplicate any downstream event.
- **Projector tests**: covered in §2 for both `profile_snapshot` and `profile_evolution` — each must be derivable purely by replaying the event stream, per the "read models are disposable" rule.

## 6. Coverage expectation

- **Domain ≥ 90%** — every value object validation branch, every aggregate state transition (creation, consent, metric recording, goal set/update and their rejection paths), and every `goal_policy` branch from §0 is covered above.
- **Application ≥ 85%** — all 8 handlers have happy-path + every documented failure/idempotency branch covered.
- **Infrastructure ≥ 70%** — every adapter's round-trip, the projector-replay tests, the outbox atomicity tests, and the KMS resilience tests (circuit open/half-open/closed, timeout) are covered. Actual % confirmed by `pytest-cov` at `/test-execution`.

## Addendum 2 — 2026-08-26, `reveal-metrics` endpoint test cases

Implements Addendum 2 of `/plans/profile-service/implementation-plan.md`. All cases below are security-critical — this endpoint discloses Article 9 health data outside its owning service.

**Unit (domain/application, fake ports)**
- `GetBiometricSnapshotForCalculationQuery` handler returns exactly the 6 allow-listed fields (`weight_kg, height_cm, age, sex, activity_level, goal_type`) — a response-shape test asserting no other key is present, even if the underlying aggregate has more decryptable fields available.
- Handler writes exactly one audit record per call, `outcome="success"`, with `metadata.fields` listing the 6 field names and no values, on every successful call.
- Handler writes exactly one audit record with `outcome="failure"` on a rejected call (bad credential), before returning the error response.

**Integration (testcontainers Postgres + Redis)**
- Correct credential + valid `user_id` → `200` with the 6-field body; audit record persisted.
- Missing/wrong credential → `401`/`403`; audit record persisted with `outcome="failure"`; response body contains no biometric data.
- Rate limit exceeded (same caller-credential + `user_id` combination, above the configured threshold) → `429`; no additional decryption/KMS call is made for the throttled request (verify the KMS-decrypting port is never invoked once the limiter rejects).
- `audit_records` table: confirmed append-only at the DB-role level (a DB-level `UPDATE`/`DELETE` attempt against the audit table, executed directly in the test, is rejected by the grant — not just "the application code never issues one").
- **Log-redaction test**: capture structured log output for a successful reveal call; assert no numeric weight/height/age value or raw `sex`/`activity_level`/`goal_type` value appears anywhere in the captured log lines — only field names, `user_id`, and outcome.
- Circuit/timeout behavior on the KMS-decryption path this endpoint depends on is already covered by `profile-service`'s existing `KmsEnvelopeDataEncryption` resilience tests — not re-tested here, this endpoint just reuses that adapter.

**Contract**
- `POST /internal/v1/profile/{user_id}/reveal-metrics` response schema documented and contract-tested, added to `docs/api-catalog.md`'s Internal APIs table (enforced by `/implementation-review`).

## Addendum 2 coverage expectation

This endpoint's handler, audit-write path, and rate-limiter integration are expected to be fully covered given the security-critical nature of the feature — treat any uncovered branch here as a `/test-review` blocking finding, not an advisory one, given what's at stake (Article 9 data disclosure).
