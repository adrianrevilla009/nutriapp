# Test Plan — `notification-service`

**Status:** Approved
**Date approved:** 2026-08-28
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/notification-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases

**Value objects / domain services (pure, zero I/O):**
- `NotificationCategory` — only `fasting`/`meal`/`water` accepted for push; email categories (`verification`/`password_reset`/`new_device_alert`) rejected as push categories and vice versa (channel/category mismatch raises).
- `QuietHoursWindow(start=22:00, end=08:00, tz=...)` — a window crossing midnight is accepted and correctly reports `10:00 local` as outside quiet hours and `23:00 local` as inside; a same-value `start == end` window raises (ambiguous "always/never quiet").
- `TemplateId("verification", version=1)` — version must be a positive int; `version=0`/negative raises.
- `DeliveryStatus` transitions — `sent → delivered` and `sent → bounced` and `sent → failed` are valid; `delivered → sent` (going backward) raises.
- `due_and_stale_policy`: a `reminder_schedule` row with `due_at` in the past and `relevance_expires_at` in the future → due now, send. `due_at` in the past and `relevance_expires_at` also in the past → suppressed, not sent late (docs/notifications.md §2's explicit rule). `due_at` in the future → not due yet, no action.
- `quiet_hours_policy`: `now` inside the user's quiet-hours window → delay (returns the next allowed send time, never drops); `now` outside the window → send immediately; a **transactional** category passed through this policy is never delayed regardless of quiet hours (policy itself refuses to apply to transactional categories — a structural test, not just a scenario one).

**`SendVerificationEmailHandler` / `SendPasswordResetEmailHandler` (fake `TokenRevealPort`, fake `EmailProviderPort`, fake `ProcessedNotificationsRepositoryPort`):**
- Reveal call succeeds → email sent with the real secret rendered into the template; delivery logged `sent`; `(event_id, "email")` marked processed.
- Reveal call raises (simulating identity-service circuit open) → handler does not send a half-rendered email, logs the attempt as `failed`, raises a typed error the consumer's dead-letter path can act on (never silently drops).
- Same `event_id` handled twice → second call is a no-op (already-processed check short-circuits before any reveal call or send is attempted) — dedup verified by asserting the fake reveal/email ports were called exactly once total across both invocations.

**`SendNewDeviceAlertHandler` (fake `EmailProviderPort`):**
- Normal case → email sent using the `email` already present in the event payload, no reveal call made (asserts the fake `TokenRevealPort` — if injected at all — is never called from this handler, confirming the "no reveal needed" design in implementation plan §1.1).

**Reminder-schedule projector commands (fake `ReminderScheduleRepositoryPort`):**
- `FastingWindowStarted` → a new `reminder_schedule` row created with `category="fasting"`, correct `due_at`/`relevance_expires_at` derived from the event's `started_at`.
- `FastingWindowEnded` → the matching open row (by `source_aggregate_id`) is marked resolved/removed from the active schedule, not left dangling.
- `MealPlanned` → a row created keyed to `planned_for`; `MealPlanUpdated` → the existing row (same `plan_entry_id`) is updated in place, not duplicated; `MealPlanRemoved` → the row is removed.
- `WaterIntakeLogged` → does **not** create a `reminder_schedule` row by itself (a single log entry isn't a reminder trigger — the water reminder is a "haven't logged in a while" absence signal); confirms the projector's actual behavior matches whatever the implementation settles on for this event (this test pins that behavior down explicitly rather than leaving it implicit).
- Same event (`event_id`) applied twice via the projector → same end state as applying it once (idempotent projection, not just idempotent *notification send* — the two are tested separately since the projection and the send are two different write paths).

**`ScanAndSendDueRemindersHandler` (fake repository pre-seeded with a mix of due/not-due/stale rows, fake `PreferencesRepositoryPort`, fake `PushProviderPort`, fake `SuppressionRepositoryPort`):**
- A due, non-suppressed, preference-enabled, non-quiet-hours row → push sent, row marked `sent`.
- A due row for a user with that category disabled in preferences → not sent, row marked `suppressed` (preference honored), no push-port call made.
- A due row for a suppressed device/user (in `suppression_list`) → not sent, checked *before* attempting any provider call.
- A due row during the user's quiet hours → not sent now, but not dropped — remains `pending` with an updated next-eligible-check time (delayed, per policy above), verified by asserting the row is still present and still `pending` after the scan, not marked `sent` or `suppressed`.
- A stale row (relevance window passed) → marked `suppressed`, no push-port call made.

**`UpdateNotificationPreferencesHandler`:**
- Valid category + quiet-hours update → persisted, returned in the next `GetNotificationPreferences` query.
- Attempt to set a quiet-hours window for a **transactional** category → rejected (structural enforcement that transactional channels are never preference/quiet-hours-gated, mirroring the domain-service test above at the application-command boundary).

**`RecordDeliveryResultHandler`** (SES/SNS bounce/complaint webhook → this command):
- Hard bounce → delivery logged `bounced`, address/device added to `suppression_list` immediately.
- Soft bounce → delivery logged `bounced` but **not** added to suppression list; a subsequent retry (via `tenacity`, exercised at the adapter/integration level, see §2) is still permitted up to the bounded attempt count.
- Explicit unsubscribe complaint → address/device added to suppression list with `reason="unsubscribe"`; re-adding requires a new, separate consent event — this handler alone never removes a suppression entry.

## 2. Integration test cases

- `SesEmailAdapter` — against SES sandbox (dev/CI never hits real SES): a well-formed send succeeds; a simulated repeated-failure sequence trips the adapter's own circuit breaker (call-count assertions show fast-fail once open, and a successful trial call after `reset_timeout` closes it again — half-open → closed verified explicitly, per `resilience-patterns/SKILL.md` §Testing Requirements).
- `SnsPushAdapter` — same three-part matrix (success, circuit opens on repeated failure, recovers half-open → closed) against a local fake push endpoint.
- `IdentityTokenRevealClient` — against a fixture HTTP server standing in for identity-service's internal endpoint: valid credential + known reference id → secret returned; unknown reference id → explicit not-found (mapped, not raised as unhandled); simulated repeated failures trip this adapter's own, independently-named circuit breaker (never shares state with the SES/SNS breakers — a structural assertion per `resilience-patterns/SKILL.md`'s "never share one breaker across unrelated dependencies").
- Postgres repositories (`reminder_schedule`, `delivery_log`, `suppression_list`, `notification_preferences`, `processed_notifications`) — round-trip persistence via testcontainers Postgres, same convention as every other service.
- `identity_events_consumer` / `diary_events_consumer` — against a real (testcontainers) RabbitMQ: publishing the same event twice results in exactly one delivery attempt (idempotency test, per `messaging-conventions/SKILL.md` §Testing Requirements); a handler that raises is nacked/requeued up to the configured limit, then dead-lettered (verified by asserting the DLQ receives the message, not silently dropped).
- `JinjaTemplateRenderer` — for each of the six templates (3 email, 3 push): rendering a fixture payload containing HTML-significant characters (`<script>`, `&`, `"`) in a user-controlled field (e.g. a display name, where applicable) produces output with those characters escaped, never raw — an explicit XSS-prevention assertion per `docs/notifications.md` §3, not just a "it renders without error" check.
- Alembic migration `0001` applies cleanly to an empty database.

## 3. Contract test cases

- `GET /api/v1/notifications/preferences` — `200` with the caller's own preferences for a valid JWT; `401` for a missing/invalid JWT (via the shared-contracts centralized auth dependency).
- `PATCH /api/v1/notifications/preferences` — `200` on a valid partial update; `422` for an invalid category name or a malformed quiet-hours window; `401` unauthenticated.
- `POST /api/v1/notifications/devices` (stub, implementation plan §9.3) — `200`/`201` accepting a device-token registration payload; `422` for a malformed payload. No downstream send behavior asserted here — registration plumbing only.
- Consumed-event payload contracts, each checked against its `docs/events-catalog.md` schema: `UserRegistered`, `PasswordResetRequested`, `NewDeviceLoginDetected`, `FastingWindowStarted`, `FastingWindowEnded`, `WaterIntakeLogged`, `WaterIntakeRemoved`, `MealPlanned`, `MealPlanUpdated`, `MealPlanRemoved` — one contract-test fixture per event, sourced from the producing service's own published schema, not hand-guessed.

## 4. E2E test cases

**None added in this plan.** None of CLAUDE.md §3's three critical journeys (register→log→see totals; photo→AI-detect→log; upgrade to Pro→publish/discover a recipe) exercise `notification-service` as a required step — email/push delivery is observable but not a gating step in any of those journeys. Deferred, not silently dropped, consistent with `food-recognition-service`'s precedent for a service outside the critical-journey set.

## 5. Event-sourcing-specific cases

**Not applicable.** `notification-service` is CQRS read-side only (implementation plan §2), not event-sourced — no aggregate rebuild-from-events case applies. The idempotency cases in §1 and §2 cover the "new consumer introduced" requirement from the test-plan template in lieu of a rebuild test.

## 6. Coverage expectation

Domain layer (`due_and_stale_policy`, `quiet_hours_policy`, the five value objects) is pure logic with the boundary/edge cases enumerated above — expect close to 100%, comfortably clearing the ≥90% floor. Application layer's nine command/query handlers each have 2-5 fake-port-driven cases above, deliberately covering failure/fallback paths (circuit-open, suppression, quiet-hours delay, stale-suppression) and not just happy paths — clears the ≥85% floor. Infrastructure layer's three external adapters (§2, each with the full circuit-breaker open/fallback/recovery matrix per `resilience-patterns/SKILL.md`), five repositories, two RabbitMQ consumers with idempotency/DLQ cases, the template renderer's XSS-prevention cases, and the four contract-test groups in §3 are expected to clear the ≥70% infrastructure floor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.

## 7. Fixtures (built, not sourced)

- `tests/fixtures/identity_events/*.json` — one fixture per consumed identity-service event, matching `docs/events-catalog.md`'s documented payload shape exactly.
- `tests/fixtures/diary_events/*.json` — same, for each of the seven consumed diary-service events.
- `tests/fixtures/template_payloads/*.json` — one fixed sample payload per template version, including at least one with HTML-significant characters in a user-controlled field, for the XSS-prevention assertion.
- No real SES/SNS credentials or live external calls anywhere in this suite, per `docs/notifications.md` §5.
