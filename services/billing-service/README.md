# billing-service

Pro subscription lifecycle, Stripe payment processing, and entitlement
issuance for NutriApp (ADR-0015). This service is the single source of
truth for "is this user currently entitled to Pro features" -- every
Pro-gated service (`recipe-service`, `social-service`, `analytics-service`)
caches a locally-derived flag from the events this service publishes,
falling back to this service's own synchronous endpoint when its cache is
stale or unpopulated.

## Bounded context

See `.claude/agents/billing-agent.md` and `docs/adr/0015-billing-and-monetization.md`.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001).
Event-driven CRUD (ADR-0002) -- `Subscription` is stored conventionally
(one row per user, updated in place as Stripe webhooks arrive), not
event-sourced. Domain events are published as a side effect via the
Outbox pattern.

## Published events (v1)

`SubscriptionStarted`, `SubscriptionRenewed`, `SubscriptionCancelled`,
`SubscriptionPaymentFailed`, `EntitlementGranted`, `EntitlementRevoked` --
see `docs/events-catalog.md` for payload schemas. Consumers
(`recipe-service`/`social-service`/`analytics-service`) are documented as
future, not-yet-implemented (none of those services exist yet) -- same
deferral pattern used elsewhere in this codebase (e.g.
`activity-service`'s `ExerciseLogged`).

This service consumes no inbound domain events -- its only inbound
trigger is Stripe's own webhook (an external HTTP call, not an internal
domain event).

## Public API

- `POST /api/v1/billing/checkout-sessions` -- JWT-authenticated (ADR-0022,
  `packages/shared-contracts`' centralized auth dependency). Creates a
  Stripe-hosted Checkout Session and returns its URL; never collects card
  data itself (PCI scope minimization).

## Internal / webhook API

- `POST /internal/v1/billing/webhooks/stripe` -- **deliberately public
  despite the `/internal/v1` path prefix.** Every other service's
  `/internal/v1/...` route is never routed through Kong; this ONE route is
  the sole exception in the entire codebase, because Stripe itself must be
  able to reach it over the public internet (Stripe's own documented
  requirement for webhook endpoints). It is still never JWT-gated --
  authenticity is verified instead via the `Stripe-Signature` HMAC scheme
  (`Stripe-Signature: t=<timestamp>,v1=<signature>`,
  https://stripe.com/docs/webhooks/signatures). **Do not mistake this for
  a missing-auth bug** -- it is a documented, reviewed exception (see the
  Helm chart's `values.yaml` NetworkPolicy comment and
  `docs/api-catalog.md`'s matching note).
  - Idempotent: dedupes by Stripe's own event `id` (`processed_webhook_events`
    table) -- replaying the same webhook twice never double-grants or
    double-charges.
  - Handles five event types: `checkout.session.completed`,
    `customer.subscription.created`, `invoice.paid`,
    `customer.subscription.deleted`, `invoice.payment_failed`. A
    recognized-but-unhandled event type returns `200` with no side effect
    (Stripe expects a 2xx to stop retrying).

### Known limitation, resolved: `checkout.session.completed` / `customer.subscription.created` ordering

Stripe's real `checkout.session.completed` payload does **not** carry the
new subscription's `current_period_end` (only the `Subscription` object's
own webhook payload does) -- an earlier version of this service papered
over that gap with a hardcoded `now + 30 days` guess, which is wrong for
most real calendar months (28-31 days) and could revoke access up to a
day early, violating the "revocation timing must match what the user was
told" rule below. **Fixed** by additionally consuming
`customer.subscription.created`, whose payload carries the authoritative
value, without adding a third `PaymentProviderPort` operation (still
exactly `create_checkout_session` + `verify_webhook_signature`).

Stripe does not strictly guarantee the arrival order of
`checkout.session.completed` and `customer.subscription.created` for the
same new subscription, so both handlers are designed to be safe either
way:
- If `checkout.session.completed` arrives first: it creates the
  subscription row using a best-effort estimate
  (`current_period_end_estimate`, `now + 30 days`) purely as a
  placeholder, since a row has to exist for entitlement checks to work
  immediately. `customer.subscription.created`, whenever it arrives,
  corrects `current_period_end` to the real value
  (`Subscription.correct_period_end`) without touching anything else.
- If `customer.subscription.created` arrives first: it creates the row
  itself, using the real `current_period_end` from the start (resolving
  the owning `user_id` via `subscription_data[metadata][user_id]`, set at
  Checkout Session creation time -- `client_reference_id` only exists on
  Checkout Session objects, not on the Subscription object this event
  carries). `checkout.session.completed`, when it later arrives, finds the
  row already correct and reuses it as-is, never overwriting with the
  estimate.

Either way, `SubscriptionStarted`/`EntitlementGranted` remain published
exclusively by `HandleCheckoutCompletedHandler` -- `customer.subscription.created`
is a pure internal webhook-consumption detail feeding that existing flow,
not a new published domain event.
- `GET /internal/v1/billing/entitlements/{user_id}` -- never routed
  through Kong. `X-Internal-Service-Credential` header, constant-time
  compared (identity-service/catalog-service precedent). The synchronous
  fallback compensation path for the `ProUpgradeEntitlementPropagation`
  saga (`docs/sagas-and-distributed-transactions.md`) -- callers wrap this
  in their OWN circuit breaker. Zero real callers today (no Pro-gated
  service exists yet); returns `entitled: false` for a user with no
  subscription record, never an error (fail safe, not fail open).

## Cancellation retains access through the paid period's end

**Non-negotiable rule (`.claude/agents/billing-agent.md`).** Cancellation
(`customer.subscription.deleted`) publishes `SubscriptionCancelled`
immediately but NEVER publishes `EntitlementRevoked` synchronously.
Instead it schedules a revocation row (`entitlement_revocation_schedule`)
for the subscription's `current_period_end`; `revocation_scan_worker.py`
(a periodic in-service worker, same shape as
`notification-service`'s `ReminderScanWorker`) polls for due rows and
publishes `EntitlementRevoked` only once the paid period has actually
ended.

## Resilience

One external dependency with a network call, one without:

| Integration                          | Circuit name     | fail_max | reset_timeout |
|----------------------------------------|--------------------|------------|------------------|
| Stripe Checkout Session creation         | `stripe_checkout`    | 5          | 30s                |
| Stripe webhook signature verification     | n/a -- local HMAC, no network call, no circuit breaker |

Checkout Session creation reuses the SAME `Idempotency-Key` HTTP header
value across every retry attempt (Stripe's documented best practice) so a
retried create-call can never accidentally create two sessions.

## PCI scope minimization

This service never receives, logs, or persists raw card numbers, CVVs, or
full payment tokens -- only Stripe's own customer/subscription/session
IDs and status/timestamp fields. Card data goes directly from the client's
browser to Stripe via hosted Checkout (SAQ A eligibility rationale in
`docs/data-protection-and-privacy.md`).

## Testing

`docs/testing-strategy.md`. `StripePaymentAdapter` is tested entirely
against fixture Stripe API responses (`tests/fixtures/stripe_responses/`)
and offline-HMAC-signed fixture webhook payloads
(`tests/fixtures/stripe_webhooks/`, signed via
`tests/fixtures/stripe_webhooks/signing.py`) -- **zero live Stripe calls
anywhere in this test suite.** Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.

## Provider status

Real Stripe API key + webhook signing secret provisioning is a tracked
lead-time item (same pattern as ADR-0011's SES-production-access note) --
not a blocker to this implementation, which is built against Stripe's
real, publicly documented API contract throughout.

