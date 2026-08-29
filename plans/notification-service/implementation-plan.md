# Implementation Plan — `notification-service`

**Status:** Approved
**Date approved:** 2026-08-28
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — CQRS read-side only, see 2026-08-28 addendum reconciling scope with CLAUDE.md §2.3), ADR-0004 (messaging backbone), ADR-0011 (notification-service, SES/SNS providers), `.claude/agents/notification-agent.md`, `.claude/skills/notification-conventions/SKILL.md` (mandatory), `.claude/skills/messaging-conventions/SKILL.md`, `.claude/skills/resilience-patterns/SKILL.md`, `docs/notifications.md`, `docs/events-catalog.md`, `docs/api-catalog.md`, `docs/domain-glossary-and-context-map.md` (already documents the `notification-service` → `identity-service` reveal-endpoint exception), `/plans/identity-service/implementation-plan.md` (structural precedent), `/plans/profile-service/implementation-plan.md` and `/plans/catalog-service/implementation-plan.md` Addendum 2 (internal-endpoint precedent, not reused here — see §6)

## 1. Scope

Build `notification-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding (`infra/k8s/charts/_lib/`, shared RDS instance, shared ElastiCache cluster, root `docker-compose.yml`/`Makefile`).

**Bounded context** (CLAUDE.md §2.2, `notification-agent.md`): delivery of transactional email and push notifications, triggered by events from other services. This service owns *delivery* only — never the business decision to notify, which stays in the emitting domain service. It owns no user profile data beyond what a template strictly needs, no subscription/entitlement state (`billing-service`), no analytics computation (`analytics-service`).

**Architecture review (this session, `architecture-agent`, before this plan was written):**
- CQRS read-side classification confirmed correct (see §2).
- "Reminder due" design resolved as a **local `reminder_schedule` read-model projection + an in-service scheduler**, not a new synchronous call into `diary-service`. Reasoning: `docs/notifications.md` §2 already places the due/stale decision "in the domain layer of `notification-service`," which only makes sense with local state to reason about; CLAUDE.md §2.2 reserves synchronous calls for low-latency query needs, not continuous batch polling of "what's due now" across the whole user base; and reopening the already-merged, already-closed `diary-service` PR for a polling endpoint would recompute what the event stream already delivers, at no informational gain.

**Acceptance criteria:**

1. **Transactional email channel** — never suppressed by preference or quiet hours:
   - `UserRegistered` (identity-service, Active) → verification email. Payload carries `email_verification_token_reference_id`, not the raw secret; this service makes a synchronous, circuit-breaker-guarded call to identity-service's existing `POST /internal/v1/auth/tokens/{reference_id}/reveal` (already implemented — verified at `services/identity-service/infrastructure/http/routes/internal_token_routes.py`) to obtain the raw token, renders it into the versioned verification-email template, sends via SES.
   - `PasswordResetRequested` (identity-service, Active) → same reference-id→reveal pattern for `reset_token_reference_id`, reset-email template.
   - `NewDeviceLoginDetected` (identity-service, Active) → new-device alert email. No reveal call — `email` and `device_fingerprint_hash` already travel in the payload.
2. **Push channel** — respects per-category user preference and quiet hours (default 22:00–08:00 local, user-adjustable):
   - A `reminder_schedule` projection, populated by consuming `FastingWindowStarted`/`FastingWindowEnded`, `MealPlanned`/`MealPlanUpdated`/`MealPlanRemoved`, `WaterIntakeLogged`/`WaterIntakeRemoved` (all Active, diary-service).
   - A periodic in-service worker (APScheduler-style periodic task, not a message consumer) scans the projection, applies domain-layer due/stale rules (a reminder whose relevance window has passed is suppressed, never sent late), and enqueues a send for anything due, respecting the user's per-category opt-in and current quiet-hours window (delay to next allowed window, never drop).
   - `NutrientDeficiencyDetected` (analytics-service) is **explicitly out of scope** — analytics-service doesn't exist yet (Phase 2). Document it in `docs/events-catalog.md` as a documented future consumer, same as it already is; do not build a consumer for it.
3. **User preferences API** — `docs/notifications.md` §2 requires users to control non-transactional push categories independently and adjust quiet hours; this needs a small public endpoint set behind Kong:
   - `GET /api/v1/notifications/preferences` / `PATCH /api/v1/notifications/preferences` (JWT-authenticated, per ADR-0022 — reuse the shared JWT auth dependency centralized in `packages/shared-contracts`, per the 2026-08-28 `shared-contracts` refactor commit `4248242`).
4. **Templating**: every send goes through a versioned template (`template_id@version`) rendered via Jinja2 with autoescape mandatorily on for HTML email bodies — never inline string-built. Push payloads are short structured JSON (title/body/data), not HTML, but still go through the same versioned-template mechanism for consistency and testability.
5. **Idempotent consumption**: dedup on `(event_id, channel)` via a `processed_notifications` table — replaying any triggering event twice must never double-send. No Outbox pattern needed here (confirmed, see §6): this service never publishes a domain event of its own as a side effect of a write; it is a pure consumer.
6. **Delivery log & suppression**: every send attempt recorded (`sent | delivered | bounced | failed`, per channel, per user). A hard bounce or explicit unsubscribe adds the address/device to a permanent suppression list checked before every send; soft bounces retried with `tenacity` backoff up to a bounded attempt count before being logged `failed`. Re-addition requires new explicit consent — never automatic.
7. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).
8. No PII beyond what a given template strictly needs is ever included in a notification payload (`docs/data-protection-and-privacy.md`, `notification-agent.md`).

**Explicitly out of scope for this plan:**
- `NutrientDeficiencyDetected` consumption (blocked on `analytics-service`, Phase 2).
- Real SES production access / SNS device-endpoint provisioning — ADR-0011 already notes this is a lead-time AWS approval item tracked separately, not a blocker to building the service against SES/SNS sandbox mode.
- Any change to `diary-service` (already merged, closed) — the reminder design deliberately avoids reopening it (see architecture review above).
- A native mobile push client/SDK integration — this plan builds the server-side SNS fan-out only; device-token registration assumes a `POST /api/v1/notifications/devices` endpoint exists for the (not-yet-built) mobile client to call, stubbed with its own contract test but not a full device-lifecycle feature.

## 2. Architectural classification

**CQRS, read side only** (ADR-0002, 2026-08-28 addendum; same shape as `analytics-service`) — not event-sourced. No owned write aggregate: `reminder_schedule`, `processed_notifications`, `delivery_log`, `suppression_list`, and `notification_preferences` are all conventional read/operational tables built and maintained by event projectors and application-layer commands, never replayed to reconstruct state. Domain layer: due/stale/quiet-hours rules (pure functions/value objects, zero I/O). Application layer: command handlers per triggering event, the periodic reminder-scan use case, the preferences use case. Infrastructure layer: RabbitMQ consumers, SES/SNS adapters, Postgres repositories, the internal reveal-endpoint HTTP client, the public preferences HTTP routes.

## 3. Files to create or modify

```
services/notification-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_notification_tables.py
      # reminder_schedule (projection: schedule_id, user_id, category
      #   [fasting|meal|water], source_aggregate_id, due_at, relevance_expires_at,
      #   status [pending|sent|suppressed])
      # processed_notifications (event_id, channel, processed_at) -- idempotency
      # delivery_log (delivery_id, user_id, channel, template_id, template_version,
      #   status [sent|delivered|bounced|failed], attempted_at, failure_reason)
      # suppression_list (user_id, channel, address_or_device, suppressed_at, reason)
      # notification_preferences (user_id, category, push_enabled, quiet_hours_start,
      #   quiet_hours_end, timezone)
  domain/
    entities/            # ReminderScheduleEntry, DeliveryLogRecord, NotificationPreference
    value_objects/        # NotificationCategory, QuietHoursWindow, TemplateId,
                          # DeliveryStatus, SuppressionReason
    services/              # due_and_stale_policy.py (pure: is this reminder due now?
                          # has its relevance window passed?), quiet_hours_policy.py
                          # (pure: is `now` inside quiet hours for this user/timezone?)
    ports/                 # email_provider_port.py, push_provider_port.py,
                          # reminder_schedule_repository_port.py,
                          # delivery_log_repository_port.py,
                          # suppression_repository_port.py,
                          # preferences_repository_port.py,
                          # processed_notifications_repository_port.py,
                          # token_reveal_port.py (the identity-service internal call),
                          # template_renderer_port.py
  application/
    commands/              # send_verification_email.py, send_password_reset_email.py,
                          # send_new_device_alert.py, update_reminder_schedule.py
                          # (from diary-service events), scan_and_send_due_reminders.py,
                          # update_notification_preferences.py, record_delivery_result.py
                          # (bounce/unsubscribe webhook handling)
    queries/                # get_notification_preferences.py
    dto/
    errors.py
  infrastructure/
    http/
      routes/               # preferences_routes.py, provider_webhook_routes.py
                          # (SES bounce/complaint notifications), health.py
      schemas/
      dependencies.py       # reuses packages/shared-contracts' centralized JWT
                          # auth dependency (commit 4248242) for preferences_routes
      error_mapping.py
    external/
      identity_token_reveal_client.py  # implements TokenRevealPort; circuit
                          # breaker + tenacity retry + timeout around
                          # POST /internal/v1/auth/tokens/{reference_id}/reveal,
                          # sends the internal-reveal-credential header
      ses_email_adapter.py             # implements EmailProviderPort; own
                          # circuit breaker/retry/timeout, SES sandbox in dev/CI
      sns_push_adapter.py              # implements PushProviderPort; own
                          # circuit breaker/retry/timeout, SNS/local-fake in dev/CI
    templating/
      jinja_template_renderer.py       # implements TemplateRendererPort,
                          # autoescape=True mandatory
      templates/
        email/verification_v1.html.j2, password_reset_v1.html.j2,
              new_device_alert_v1.html.j2
        push/fasting_reminder_v1.json.j2, meal_reminder_v1.json.j2,
              water_reminder_v1.json.j2
    persistence/
      models.py, postgres_reminder_schedule_repository.py,
      postgres_delivery_log_repository.py, postgres_suppression_repository.py,
      postgres_preferences_repository.py,
      postgres_processed_notifications_repository.py
    messaging/
      identity_events_consumer.py      # UserRegistered, PasswordResetRequested,
                          # NewDeviceLoginDetected
      diary_events_consumer.py         # FastingWindowStarted/Ended,
                          # MealPlanned/Updated/Removed, WaterIntakeLogged/Removed
    scheduling/
      reminder_scan_worker.py          # periodic worker invoking
                          # scan_and_send_due_reminders.py
    composition_root.py, main.py
  tests/
    unit/domain/          # due_and_stale_policy, quiet_hours_policy,
                          # value object validation
    unit/application/     # command/query handlers, mocked ports
    integration/infrastructure/  # testcontainers Postgres/Redis/RabbitMQ,
                          # fixture-based SES/SNS fakes (never live calls),
                          # fixture-based identity-service reveal-endpoint fake
    contract/http/        # preferences endpoint contract, event payload
                          # contract per consumed event (matches
                          # docs/events-catalog.md schemas)
    fixtures/

infra/terraform/environments/dev/notification-service.tf   # mirrors
    nutrition-calculation-service.tf's structure; new resources: SES
    identity/config-set (sandbox), SNS platform application placeholders
    (deferred until a mobile client exists, per ADR-0011 follow-up), RDS
    schema/user via the shared secrets module, ECR repo
infra/k8s/charts/notification-service/     # own chart using the CORRECT
    _deployment.tpl env-list format and envFrom→ExternalSecret wiring
    (per the bug flagged in food-recognition-service's PR #12 — this
    service's chart must not perpetuate it; backporting the fix to the
    other five services' charts remains separately tracked, not part of
    this plan)
.github/workflows/notification-service-ci.yml   # mirrors the other
    services' pipelines (lint -> mypy -> unit -> pip-audit ->
    integration/contract -> coverage-gate -> image build/scan -> helm
    lint/template), pinned uv/action SHAs per the existing convention

docs/events-catalog.md     # see §5
docs/api-catalog.md        # add the two new public routes + the
    already-active internal reveal-endpoint row already lists this
    service as a consumer (line 38) -- verify still accurate
docs/domain-glossary-and-context-map.md   # the notification-service ->
    identity-service relationship entry already exists (line 45) and
    already says "not yet built" -- update once this service exists;
    add a new entry for notification-service's relationship to
    diary-service (Customer-Supplier via published events, pure
    consumer, no synchronous call)
ARCHITECTURE.md            # already has a notification-service
    placeholder in the service map -- verify it's still accurate, no
    structural change expected
docker-compose.yml         # add a notification-service block, same
    pattern as the six already-merged services
```

## 4. Ports/adapters affected

**New ports** (all introduced by this service, no existing port reused across a service boundary):
- `EmailProviderPort` / `PushProviderPort` — SES / SNS adapters (ADR-0011), each with its own circuit breaker.
- `TokenRevealPort` — the synchronous call into identity-service's existing internal endpoint.
- `ReminderScheduleRepositoryPort`, `DeliveryLogRepositoryPort`, `SuppressionRepositoryPort`, `PreferencesRepositoryPort`, `ProcessedNotificationsRepositoryPort` — Postgres adapters.
- `TemplateRendererPort` — Jinja2 adapter.

No existing port from another service is reused; `packages/shared-contracts`' centralized JWT auth dependency (introduced 2026-08-28, commit `4248242`, already used by `food-recognition-service`) is reused for the new preferences routes — confirmed still the correct, current pattern (lazy container lookup per commit `052a821`).

## 5. Domain events

**Consumed** (no new events introduced by this service — it publishes none):
- `UserRegistered`, `PasswordResetRequested`, `NewDeviceLoginDetected` (identity-service) — already list `notification-service` as a consumer in `docs/events-catalog.md`; no catalog change needed for these three.
- `FastingWindowStarted`, `FastingWindowEnded` (diary-service) — catalog already lists `notification-service` as a consumer but annotated "documented, not yet existing"; **flip this annotation once implemented and covered by a passing contract test.**
- `WaterIntakeLogged`, `WaterIntakeRemoved`, `MealPlanned`, `MealPlanUpdated`, `MealPlanRemoved` (diary-service) — catalog currently lists only `analytics-service` as a consumer; **this plan must add `notification-service` to each of these five entries' consumer lists** (architecture-agent finding, this session).
- `NutrientDeficiencyDetected` (analytics-service) — remains documented as a future consumer only; not implemented, no catalog change (already correctly marked not-yet-existing on the producer side).

`docs/events-catalog.md` update is part of this plan's file list (§3) and must land in the same PR as the code, per the standing rule that an event's consumer list stays current with the same change that makes it true.

## 6. Cross-service impact

**Flagged for `architecture-agent` review, already addressed this session:**
- The `TokenRevealPort` call into identity-service's existing internal endpoint is not a new cross-service contract — it's already documented in `docs/domain-glossary-and-context-map.md` (line 45) as a planned, deliberate, single-endpoint exception. This plan is what makes it real; no change to identity-service is required (endpoint already implemented and merged).
- The reminder-due design deliberately introduces **no new call into `diary-service`** and requires **no change to `diary-service`** — confirmed by architecture-agent as the correct choice specifically to avoid reopening an already-merged, closed PR (see §1). This is the one place a naive design would have crossed a service boundary; it doesn't.
- `docs/events-catalog.md` consumer-list additions (§5) are metadata-only — they don't change any producer's contract or require a producer-side code change, since `diary-service` already publishes these events unconditionally to its own exchange.

No other service's code, contract, or behavior changes as a result of this plan.

## 7. Resilience/caching/migration needs

- **Circuit breakers** (three independent external dependencies, each its own named `pybreaker`/`purgatory` instance per `resilience-patterns/SKILL.md`): SES send, SNS send, identity-service token-reveal call. `fail_max`/`reset_timeout` values chosen and documented in `README.md` once implemented, mirroring `food-recognition-service`'s and `nutrition-calculation-service`'s precedent of per-integration tuning rather than copy-pasted defaults.
- **Retry**: `tenacity` exponential backoff + jitter on all three; the token-reveal call is idempotent (a GET-shaped reveal, no state mutated), SES/SNS sends are deduplicated via `(event_id, channel)` before any retry is attempted so a retried send can't double-fire.
- **Timeout**: explicit per-call timeout on all three, no unbounded waits.
- **Bulkhead**: a dedicated `httpx.AsyncClient` per external integration (SES, SNS, identity-service), not a shared client.
- **No caching layer needed** — no read-heavy hot path here; the suppression-list check is a single indexed Postgres lookup per send, not a candidate for Redis per `caching-strategy/SKILL.md`'s "cache what's actually hot" framing. Revisit only if real send volume later shows this lookup as a measured bottleneck.
- **Migration**: one initial Alembic migration (§3) creating five new tables, purely additive (new service, no existing schema to preserve compatibility with) — standard case, no destructive-change approval needed per `database-migrations/SKILL.md`.

## 8. Test plan reference

`/test-plan` will define concrete test cases next per `.claude/agents/notification-agent.md`'s testing requirements: idempotency tests (replaying a triggering event twice → exactly one delivery attempt per channel), template-rendering tests per template version with fixed sample payloads asserting no unescaped user input reaches rendered output, circuit-breaker open/fallback/recovery tests for all three external dependencies, quiet-hours and due/stale policy unit tests, and contract tests for the two new public routes and every consumed event's payload shape against `docs/events-catalog.md`. Not enumerated further here.

## 9. Risks and open questions

1. **SES/SNS sandbox vs. production access** — ADR-0011 already flags this as a tracked AWS lead-time item, not a blocker to this plan; this service is built and tested entirely against SES sandbox mode and a local fake push endpoint (never real sends in CI), consistent with `docs/notifications.md` §5. No human decision needed now; flagged so it isn't forgotten before any real `staging` traffic.
2. **Shared Helm chart env-format bug** (flagged in `food-recognition-service` PR #12, still open per `STATUS.md`) — this service's own new chart is built with the correct format from the start (§3), but the five already-merged services' charts remain unfixed. Out of scope for this plan; recommend a dedicated follow-up PR, unchanged from the existing STATUS.md note.
3. **Device-token registration for push** — no mobile client exists yet (ADR-0014: responsive web first). This plan stubs a minimal `POST /api/v1/notifications/devices` endpoint and contract test so the port/adapter shape exists, but there's no real device to register against yet in practice. Low risk — push sends simply have no real device endpoints to target until a mobile client exists; this doesn't block shipping the email channel or the reminder-scheduling logic, which are independently valuable now.
4. No other open questions — the two architecturally significant questions (CQRS classification, reminder-due design) were resolved by `architecture-agent` before this plan was written (§1).

## Addendum — 2026-08-28: water-intake reminder descoped to a documented no-op

Found during implementation review (`reviewer-agent`): §1.2's acceptance criterion lists the `reminder_schedule` projection as "populated by consuming ... `WaterIntakeLogged`/`Removed`" without carving out an exception, but `docs/notifications.md` §1's "meal/water/fasting reminder due" implies water gets the same due/stale treatment as fasting and meal reminders. In practice, a single `WaterIntakeLogged`/`WaterIntakeRemoved` event is not itself a reminder trigger — a water reminder is inherently an *absence* signal ("no intake logged by some time of day"), which needs a different mechanism (a per-user daily-goal check against accumulated intake, not a per-event projection row) than the discrete per-item scheduling that already works for `FastingWindowStarted`/`Ended` and `MealPlanned`/`Updated`/`Removed`.

This plan's scope, as actually implemented, treats `WaterIntakeLogged`/`WaterIntakeRemoved` as consumed-but-no-op: the events are subscribed to (satisfying idempotent-consumer coverage and keeping `notification-service` correctly listed as a consumer in `docs/events-catalog.md`), but no `reminder_schedule` row is created and no water-absence reminder is sent by this version of the service. This is a deliberate, narrower interpretation than §1.2's original wording, not an oversight — it is explicitly pinned down as expected behavior in `/plans/notification-service/test-plan.md` §1 ("`WaterIntakeLogged` → does **not** create a `reminder_schedule` row by itself").

**Follow-up (not part of this plan or its PR):** a real water-intake-absence reminder requires a small design of its own (a daily-goal-vs-accumulated-intake check, likely another periodic worker reading a local projection of `WaterIntakeLogged`/`Removed` events grouped by day) — track as a future addition to `notification-service`, scoped and planned separately when there's an actual daily water-goal source to check against (today, no service publishes a per-user daily water goal).
