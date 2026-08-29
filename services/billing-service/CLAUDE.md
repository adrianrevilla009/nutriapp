# billing-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/billing-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/billing-agent.md`
(bounded context, domain responsibilities, rules) -- read both first,
plus `.claude/skills/saga-conventions/SKILL.md` and
`.claude/skills/resilience-patterns/SKILL.md` before touching anything in
`domain/`, `application/commands/handle_subscription_deleted.py`, or
`infrastructure/external/stripe_payment_adapter.py` -- mandatory,
non-negotiable reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, or the Stripe SDK.
- Event-driven CRUD (ADR-0002), not event-sourced -- `Subscription` is a
  conventional row per user, mutated via immutable-entity transition
  methods (`start`/`renew`/`cancel`/`mark_past_due`/`correct_period_end`)
  that each return a NEW `Subscription` instance; the application layer
  persists the returned instance.
- `PaymentProviderPort` has exactly two operations
  (`create_checkout_session`, `verify_webhook_signature`) --
  `StripePaymentAdapter` is the only implementation. Do not add a third
  operation (e.g. "retrieve subscription") to get Stripe's real
  `current_period_end` -- that gap is instead closed by consuming
  `customer.subscription.created` as a 5th webhook event type (pure
  webhook consumption, same pattern as the other four handlers), not an
  outbound API call. See
  `infrastructure/http/routes/stripe_webhook_routes.py`'s
  `PRO_TIER_BILLING_PERIOD_END_ESTIMATE_DAYS` docstring and
  `application/commands/handle_subscription_created.py` for the full
  ordering-safety design (Stripe does not strictly order
  `checkout.session.completed` and `customer.subscription.created`
  relative to each other) and `README.md`'s "Known limitation, resolved"
  section for the reviewer-agent-flagged correctness issue this fixed
  (a flat 30-day guess could revoke access up to a day early in most
  real calendar months).

## Never do this

- Never revoke entitlement (`EntitlementRevoked`) synchronously from
  `HandleSubscriptionDeletedHandler` (the `customer.subscription.deleted`
  webhook handler) -- it MUST only ever be published by
  `ProcessDueRevocationsHandler`, once a scheduled row's `revoke_at` is
  actually due. This is `.claude/agents/billing-agent.md`'s single most
  important rule ("cancellation retains access through the paid period's
  end").
- Never log or persist a raw card number, CVV, or full payment token --
  only Stripe's own IDs/references and subscription status/timestamps.
  Stripe's own webhook payloads for the four event types this service
  handles don't include PANs by design, but never assume that stays true
  without checking a new fixture payload before wiring it in.
- Never process a Stripe webhook payload before
  `PaymentProviderPort.verify_webhook_signature` succeeds. Never trust an
  unverified payload, even for a "harmless-looking" read.
- Never make a live call to a real Stripe account in this service's own
  test suite -- fixture Stripe API responses
  (`tests/fixtures/stripe_responses/`) and offline-HMAC-signed fixture
  webhook payloads (`tests/fixtures/stripe_webhooks/`) only.
- Never skip the `processed_webhook_events` idempotency check before a
  webhook handler's first write -- every one of the four webhook command
  handlers checks `is_processed()` before touching any repository or
  enqueueing any event.
- Never let `CreateCheckoutSessionHandler` call `PaymentProviderPort` for
  a user who already has a `status == active` subscription -- reject
  first, never a second concurrent subscription per user.
- Never add trial periods, coupons, multiple plan tiers, or proration
  without a new implementation plan -- explicitly out of scope per
  `/plans/billing-service/implementation-plan.md` section 1.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `PaymentProviderPort`,
  `SubscriptionRepositoryPort`, `ProcessedWebhookEventsRepositoryPort`,
  `EntitlementRevocationScheduleRepositoryPort`, `OutboxRepositoryPort`.
- Adapters: `infrastructure/external/stripe_payment_adapter.py` (the only
  `PaymentProviderPort` implementation, own `stripe_checkout` circuit
  breaker), `infrastructure/persistence/` (four Postgres repositories),
  `infrastructure/messaging/` (`RabbitMqEventPublisher`,
  `OutboxRelayWorker`), `infrastructure/scheduling/revocation_scan_worker.py`
  (periodic in-service worker, started as a background task from
  `Container.startup()`, same shape as
  `notification-service`'s `ReminderScanWorker` -- NOT a message
  consumer).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`; the offline
  Stripe-Signature signing helper lives in
  `tests/fixtures/stripe_webhooks/signing.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).

