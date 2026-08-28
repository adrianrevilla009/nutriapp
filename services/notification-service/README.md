# notification-service

Transactional email (SES) and push (SNS) delivery for NutriApp, triggered
by events from other services (ADR-0011). This service owns *delivery*
only -- the decision to notify is made by the emitting domain service.

## Bounded context

See `.claude/agents/notification-agent.md` and `docs/notifications.md`.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001).
CQRS, read side only (ADR-0002) -- no owned write aggregate; a pure event
consumer plus one narrow synchronous exception (the identity-service
token-reveal call). Not event-sourced.

## Consumed events

- `UserRegistered`, `PasswordResetRequested`, `NewDeviceLoginDetected`
  (identity-service) -> transactional email.
- `FastingWindowStarted`/`Ended`, `MealPlanned`/`Updated`/`Removed`,
  `WaterIntakeLogged`/`Removed` (diary-service) -> the local
  `reminder_schedule` projection, scanned periodically for due push
  reminders.

This service publishes no domain events of its own.

## Public API

- `GET`/`PATCH /api/v1/notifications/preferences` -- JWT-authenticated
  (ADR-0022), reuses `packages/shared-contracts`' centralized auth
  dependency.
- `POST /api/v1/notifications/devices` -- stub-only device-token
  registration (no mobile client exists yet, ADR-0014).

## Internal API

- Calls identity-service's existing
  `POST /internal/v1/auth/tokens/{reference_id}/reveal` (never routed
  through Kong) to obtain a raw verification/reset secret.
- Exposes `POST /internal/v1/notifications/webhooks/provider` for
  SES/SNS bounce/complaint notifications (normalized payload shape;
  real webhook signature verification is a follow-up once real SES/SNS
  access exists).

## Resilience

Three independent external dependencies, each its own named `purgatory`
circuit breaker (`.claude/skills/resilience-patterns/SKILL.md`):

| Integration                | Circuit name           | fail_max | reset_timeout |
|-----------------------------|--------------------------|-----------|------------------|
| SES send                     | `ses_email`                | 5         | 30s                |
| SNS publish                  | `sns_push`                 | 5         | 30s                |
| identity-service reveal call | `identity_token_reveal`    | 5         | 30s                |

Each has its own `httpx.AsyncClient` connection pool (bulkhead) and a
`tenacity` retry (3 attempts, exponential backoff + jitter) on transport
failures only -- never on a well-formed 4xx business response.

## Idempotency

Every consumer dedups on `(event_id, channel)` via the
`processed_notifications` table -- replaying the same triggering event
twice never double-sends (CLAUDE.md section 2.4).

## Testing

`docs/testing-strategy.md`. Provider adapters are tested against
`httpx.MockTransport` fixtures standing in for SES sandbox / a local fake
push endpoint -- never a real SES/SNS/identity-service call in this
service's own test suite. Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.

## Provider status

SES/SNS sandbox mode only in dev/CI (docs/notifications.md section 5);
real production access is a tracked AWS lead-time item (ADR-0011), not a
blocker to this implementation.

