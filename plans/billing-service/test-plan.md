# Test Plan — `billing-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/billing-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases

**Value objects:**
- `SubscriptionStatus` — only `active`/`past_due`/`canceled` accepted; an unrecognized value raises.
- `StripeCustomerId`/`StripeSubscriptionId` — Stripe's documented ID prefix format (`cus_...`/`sub_...`) validated; a malformed ID (wrong prefix, empty) raises.

**`Subscription` entity:**
- `cancel()` sets `cancel_at_period_end=True` and schedules a revocation record for `current_period_end`, but does **not** itself change `status` away from `active` — the subscription remains fully entitled until period end (mirrors `billing-agent.md`'s explicit rule).
- `mark_past_due()`/`mark_canceled()` (from webhook-driven state transitions) — valid transitions accepted; an already-`canceled` subscription receiving another `customer.subscription.deleted` is idempotent (no duplicate state change, no exception).

**`CreateCheckoutSessionHandler` (fake `PaymentProviderPort`):**
- Valid user, no existing active subscription → Checkout Session created, URL returned.
- User already has an `active` subscription → rejected with a typed error (never a second concurrent subscription for the same user), no call to the payment provider attempted.

**`HandleCheckoutCompletedHandler` (fake repository, fake outbox):**
- Valid Stripe event → subscription persisted (`active`, `stripe_customer_id`/`stripe_subscription_id` recorded), `SubscriptionStarted` and `EntitlementGranted` both published, exactly once each.
- Same Stripe `event_id` processed twice → second call is a no-op (idempotency check short-circuits before any repository write or event publish) — verified by asserting the fake ports were called exactly once total across both invocations.

**`HandleInvoicePaidHandler`:**
- Existing subscription, renewal invoice → `current_period_end` extended, `SubscriptionRenewed` published.
- Invoice for an unknown subscription (no matching `stripe_subscription_id`) → typed not-found error, no event published (never silently swallowed).

**`HandleSubscriptionDeletedHandler`:**
- Existing active subscription → `SubscriptionCancelled` published immediately; `EntitlementRevoked` is **not** published immediately — instead a revocation-schedule row is created/confirmed for `current_period_end` (the deferred-revocation case, matching the entity-level test above at the application-handler boundary).

**`HandlePaymentFailedHandler`:**
- Existing active subscription → `SubscriptionPaymentFailed` published; subscription `status` becomes `past_due`; entitlement is **not** revoked by this handler alone (Stripe's own dunning process determines if/when the subscription is ultimately canceled — that's `HandleSubscriptionDeletedHandler`'s job, not this one's).

**`ProcessDueRevocationsHandler` (fake repository pre-seeded with a mix of due/not-due revocation rows):**
- A due, unprocessed row → `EntitlementRevoked` published, row marked processed.
- A not-yet-due row → no action, row remains unprocessed.
- An already-processed row → not reprocessed (idempotent scan, no duplicate `EntitlementRevoked`).

**`GetEntitlementForUserHandler`:**
- User with an `active` subscription → entitled.
- User with a `canceled` subscription past its `current_period_end` → not entitled.
- User with a `canceled` subscription **before** its `current_period_end` (cancel-at-period-end window) → still entitled (matches the deferred-revocation rule).
- User with no subscription record at all → not entitled (never an error, a clean "no" answer).

## 2. Integration test cases

- `StripePaymentAdapter.create_checkout_session` — against a fixture HTTP server standing in for Stripe's API: well-formed response → Checkout Session URL returned; simulated repeated failures trip the `stripe_checkout` circuit breaker (call-count assertions show fast-fail once open, recovery verified after `reset_timeout`, per `resilience-patterns/SKILL.md` §Testing Requirements); the idempotency-key header is asserted present on every create-call attempt (including retries), per Stripe's documented best practice referenced in implementation-plan.md §7.
- `StripePaymentAdapter.verify_webhook_signature` — a validly-signed fixture payload (signed offline with a fixture test secret, matching Stripe's documented HMAC scheme) verifies successfully; a tampered payload (body modified after signing) fails verification; a payload signed with the wrong secret fails verification; an expired-timestamp payload (outside Stripe's documented tolerance window) fails verification. None of these four cases make a live call to Stripe.
- Postgres repositories (`subscriptions`, `processed_webhook_events`, `entitlement_revocation_schedule`, `outbox`) — round-trip persistence via testcontainers Postgres, same convention as every other service.
- Outbox relay worker — appending an event and the outbox row happens atomically; a simulated failure after the DB write but before the publish must not lose the event (still relayed on retry), per `messaging-conventions/SKILL.md` §Testing Requirements.
- `revocation_scan_worker` — against a real Postgres testcontainer: a due row is processed and published to a real (testcontainers) RabbitMQ exchange; a not-due row is left alone across multiple scan cycles.
- Alembic migration `0001` applies cleanly to an empty database.

## 3. Contract test cases

- `POST /api/v1/billing/checkout-sessions` — `201` with a Checkout Session URL for a valid authenticated request with no existing active subscription; `409` for a user who already has an active subscription; `401` unauthenticated.
- `POST /internal/v1/billing/webhooks/stripe` (or the provider's conventional path, per implementation-plan.md §1.2) — `200` for a validly-signed, recognized event type; `401` for an invalid/missing signature (never processed, no side effect); `200`-but-no-op for a replayed `event_id` (idempotent, not an error to the caller — Stripe expects a 2xx to stop retrying); `200`-but-no-op for a recognized-but-unhandled event type (never a 4xx/5xx for an event type this service simply doesn't act on).
- `GET /internal/v1/billing/entitlements/{user_id}` — `200` with `entitled: true`/`false` per `GetEntitlementForUserHandler`'s cases; `401`/`403` for a missing/wrong internal-service credential.
- `SubscriptionStarted`/`SubscriptionRenewed`/`SubscriptionCancelled`/`SubscriptionPaymentFailed`/`EntitlementGranted`/`EntitlementRevoked` (v1) — each published payload matches `docs/events-catalog.md`'s documented schema.

## 4. E2E test cases

**None added in this plan.** CLAUDE.md §3's journey 3 ("Upgrade to Pro → publish a recipe → another user finds it in recipe search") touches `billing-service`, but `recipe-service` doesn't exist yet — that journey's E2E test is deferred until both sides of it exist, not built partially here. Consistent with every other service's precedent for a journey that isn't fully buildable yet.

## 5. Event-sourcing-specific cases

**Not applicable.** `billing-service` uses conventional persistence + event-driven CRUD (implementation plan §2), not event sourcing.

## 6. Coverage expectation

Domain layer (`SubscriptionStatus`, `StripeCustomerId`, `StripeSubscriptionId`, `Subscription` entity) is small with clear edge cases enumerated above — expect close to 100%, comfortably clearing the ≥90% floor. Application layer's seven handlers each have 2-4 cases above, deliberately covering idempotency, deferred-revocation, and not-found/already-processed edge cases and not just happy paths — clears the ≥85% floor. Infrastructure layer's Stripe adapter (both methods' full matrices), four repositories, outbox relay, revocation worker, migration, and the four contract-test groups in §3 are expected to clear the ≥70% infrastructure floor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.

## 7. Fixtures (built, not sourced)

- `tests/fixtures/stripe_responses/checkout_session_created.json` — matching Stripe's actual documented Checkout Session object shape.
- `tests/fixtures/stripe_webhooks/{checkout_session_completed,invoice_paid,subscription_deleted,invoice_payment_failed}.json` — matching Stripe's actual documented webhook event object shapes for each handled type, plus one unhandled-event-type fixture for the no-op contract case.
- `tests/fixtures/stripe_webhooks/signing.py` (or similar) — a small helper that HMAC-signs a fixture payload with a fixture test secret, matching Stripe's documented `Stripe-Signature` header format exactly, so the tampered/wrong-secret/expired-timestamp cases can be constructed precisely and deterministically.
- No real Stripe API key or live call anywhere in this suite.
