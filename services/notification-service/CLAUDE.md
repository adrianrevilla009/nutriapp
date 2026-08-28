# notification-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/notification-service/`. It does not replace the root
`/CLAUDE.md` (architecture, workflow, guardrails) or
`.claude/agents/notification-agent.md` (bounded context, domain
responsibilities, rules) -- read both first, and read
`.claude/skills/notification-conventions/SKILL.md` and
`docs/notifications.md` before touching anything in `domain/` or a
template -- mandatory, non-negotiable reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, or jinja2.
- CQRS, read side only (ADR-0002) -- no owned write aggregate. Not
  event-sourced.
- Pure event consumer + exactly one narrow synchronous exception: the
  identity-service token-reveal call
  (`infrastructure/external/identity_token_reveal_client.py`). This
  service publishes no domain event of its own -- never add an
  `EventPublisherPort`/outbox here.
- No `diary-service` client/port anywhere in this codebase beyond the
  two RabbitMQ consumers -- the reminder-due decision is entirely local
  (`reminder_schedule` projection + `ReminderScanWorker`), never a new
  synchronous call into `diary-service`.

## Never do this

- Never send email/push in response to an HTTP request path directly --
  always via a consumed event (`.claude/skills/notification-conventions/SKILL.md`).
- Never construct notification content from a raw event payload --
  always through `TemplateRendererPort`/`JinjaTemplateRenderer`, which
  has `autoescape=True` mandatory for every template, including the push
  `.json.j2` ones (see the renderer's own docstring for why that's still
  valid JSON).
- Never skip the `(event_id, channel)` idempotency check before a send.
- Never suppress or quiet-hours-gate a transactional email category --
  `NotificationCategory.email(...)`'s `is_transactional` and
  `quiet_hours_policy`'s structural refusal both enforce this; do not
  work around either.
- Never remove a suppression-list entry automatically. Re-addition to the
  allowed set requires a new, separate, explicit-consent code path --
  `RecordDeliveryResultHandler` only ever adds.
- Never make a live call to a real SES/SNS/identity-service instance in
  this service's own test suite -- `httpx.MockTransport` fixtures only.
- Never bump a template version in place. A content change to an
  existing `template_id@version` is a new version file plus a new
  `TemplateId(..., version=N+1)` reference, reviewed like code
  (`docs/notifications.md` section 3).

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `EmailProviderPort`,
  `PushProviderPort`, `TokenRevealPort`, `TemplateRendererPort`, and five
  repository ports.
- Adapters: `infrastructure/external/` (SES, SNS, identity-reveal, each
  with its own named circuit breaker), `infrastructure/templating/`,
  `infrastructure/persistence/`, `infrastructure/messaging/` (the two
  RabbitMQ consumers), `infrastructure/scheduling/` (the periodic
  reminder-scan worker, not a message consumer).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).

