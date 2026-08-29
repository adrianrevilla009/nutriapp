# Implementation Plan — `billing-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — event-driven CRUD), ADR-0004 (messaging backbone), ADR-0015 (billing/monetization, Stripe), ADR-0019 (saga pattern), `.claude/agents/billing-agent.md`, `.claude/skills/resilience-patterns/SKILL.md`, `.claude/skills/messaging-conventions/SKILL.md`, `.claude/skills/saga-conventions/SKILL.md`, `docs/sagas-and-distributed-transactions.md` (`ProUpgradeEntitlementPropagation`), `docs/events-catalog.md`, `docs/api-catalog.md`, `docs/data-protection-and-privacy.md`, `docs/domain-glossary-and-context-map.md`

## 1. Scope

Build `billing-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing shared platform scaffolding.

**Bounded context** (CLAUDE.md §2.2, ADR-0015): subscription lifecycle for the paid Pro tier, payment processing via Stripe, and issuing the entitlement state other services gate Pro features on.

**Provider approach (explicit direction, this session):** unlike `activity-service`'s wearable-provider deferral (four bespoke OAuth integrations with no universal public contract), Stripe is a single, extremely well-documented, stable, universally-implementable public API — this plan builds a **real, correct `PaymentProviderPort` adapter** against Stripe's actual documented API shapes (Checkout Sessions, webhook event types, subscription objects), tested entirely via fixtures/mocks (never a live Stripe call, same convention as every other provider integration in this codebase). Real Stripe API key provisioning (test and live) is a tracked lead-time item, same pattern as ADR-0011's SES-production-access note — not a blocker to building against Stripe's documented contract now.

**Architecture review (this session, `architecture-agent`, before this plan was written):**
- Confirmed event-driven CRUD (ADR-0002) — subscription state is current-state-plus-side-effect-events, not an append-only audit history.
- Confirmed the synchronous entitlement-check endpoint (§1.4 below) must be built **now**, not deferred like `activity-service`'s TDEE-consumption situation — this endpoint is the documented compensation path for the `ProUpgradeEntitlementPropagation` saga (`docs/sagas-and-distributed-transactions.md`), owned entirely by `billing-service` on both the producer and fallback side, so there's no "reopening another already-merged service" cost the way there was for `nutrition-calculation-service`. Omitting it would leave the saga's failure path unimplemented while claiming the saga's `billing-service` side is done.
- Confirmed the PCI/compliance boundary (hosted Stripe Checkout, never raw card data reaching this service) is the one thing that cannot be safely retrofitted later — built correctly from the start (§1.1).
- Flagged that ADR-0015's own follow-up action — extending `docs/data-protection-and-privacy.md` with payment-data handling — is not yet done; this plan includes it (§3), not deferred.

**Acceptance criteria:**

1. **`POST /api/v1/billing/checkout-sessions`** — creates a **Stripe Checkout Session** (hosted, redirect-based) for the authenticated user to start a Pro subscription. Never a custom card-collection form posting to this service's own backend — PCI scope minimization (ADR-0015, `billing-agent.md`) depends on this from day one, not as a later hardening pass. Returns the Checkout Session URL for the frontend to redirect to.
2. **`POST /internal/v1/billing/webhooks/stripe`** (or the provider's conventional public webhook path per Stripe's own requirement that webhook endpoints be internet-reachable — document this exception to the "internal-only, never routed through Kong" convention explicitly, since Stripe itself must be able to reach it) — Stripe webhook receiver:
   - Signature-verified using Stripe's documented `Stripe-Signature` header scheme (never trust an unverified payload).
   - Idempotent: dedupe by Stripe's own event `id` (a `processed_webhook_events` table), replaying the same webhook twice must not double-grant/double-charge.
   - Handles: `checkout.session.completed` (→ `SubscriptionStarted` + `EntitlementGranted`), `invoice.paid` (→ `SubscriptionRenewed`), `customer.subscription.deleted` (→ `SubscriptionCancelled`, `EntitlementRevoked` scheduled for period end, not immediate — see §1.5), `invoice.payment_failed` (→ `SubscriptionPaymentFailed`; entitlement stays granted through Stripe's own dunning/retry window, only revoked if Stripe itself ultimately cancels the subscription).
   - Webhook payload logging never persists raw card/payment-method fields (architecture-agent's flagged risk: Stripe's own event payloads for these event types don't include PANs by design, but this must be enforced as an explicit, tested logging-boundary rule, not an assumption that stays true by accident).
3. **`SubscriptionStarted`/`SubscriptionRenewed`/`SubscriptionCancelled`/`SubscriptionPaymentFailed`/`EntitlementGranted`/`EntitlementRevoked`** (all v1, already documented in `docs/events-catalog.md` per ADR-0015's own follow-up) published via Outbox — flip their `Status` to `Active`, producer `billing-service`; consumers `recipe-service`/`social-service`/`analytics-service` marked documented-not-yet-consuming (none exist yet — same deferral pattern as `activity-service`'s `ExerciseLogged`).
4. **`GET /internal/v1/billing/entitlements/{user_id}`** — synchronous, circuit-breaker-guarded (on the *caller's* side, per every prior internal-endpoint precedent) fallback entitlement check, per the saga's documented compensation path. Built now with zero real callers (same pattern as publishing events before any consumer exists) — this is `billing-service`'s own responsibility, not contingent on any Pro-gated service existing yet.
5. **Cancellation retains access through the paid period's end** (`billing-agent.md`'s explicit rule): `customer.subscription.deleted` records the cancellation and schedules `EntitlementRevoked` for the subscription's `current_period_end` (a scheduled/deferred internal event, not fired synchronously from the webhook handler) — never revoke access the moment a user clicks cancel.
6. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).
7. `docs/data-protection-and-privacy.md` extended with `billing-service`'s payment-data handling section (ADR-0015's follow-up action, done here not deferred): what's stored (Stripe customer/subscription/price IDs, subscription status, timestamps), what's never stored (raw card data, full payment tokens beyond what Stripe's own references require), and the SAQ A eligibility rationale (hosted Checkout keeps raw card data off this service's servers entirely).

**Explicitly out of scope for this plan:**
- Any consumer-side wiring in `recipe-service`/`social-service`/`analytics-service` (none exist yet — same deferral pattern as `activity-service`).
- Real Stripe API key provisioning/account setup — tracked lead-time item, not a blocker to building against Stripe's documented contract (ADR-0015-style deferral, matching ADR-0011's SES precedent).
- Trial periods, coupons/discounts, plan tiers beyond a single "Pro" tier, proration on upgrade/downgrade — `docs/product-requirements.md`'s freemium model doesn't require these for an MVP; add via a future addendum if/when the product actually needs them.
- The `EntitlementRevoked`-at-period-end scheduling mechanism's own worker is built (§1.5), but any broader "scheduled jobs" platform pattern beyond what this one feature needs is out of scope — reuse the periodic-worker shape already established by `notification-service`'s `reminder_scan_worker.py`, don't build new infrastructure for it.

## 2. Architectural classification

**Event-driven CRUD** (ADR-0002, confirmed by architecture-agent) — not event-sourced. `Subscription` is stored conventionally (one row per user's subscription, updated in place as Stripe webhooks arrive), events published via Outbox as a side effect, mirroring `catalog-service`'s/`activity-service`'s pattern.

## 3. Files to create or modify

```
services/billing-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_billing_tables.py
      # subscriptions (subscription_id, user_id, stripe_customer_id,
      #   stripe_subscription_id, status [active|past_due|canceled],
      #   current_period_end, cancel_at_period_end bool, created_at, updated_at)
      # processed_webhook_events (stripe_event_id, processed_at) -- idempotency
      # entitlement_revocation_schedule (user_id, revoke_at, processed bool)
      #   -- the deferred-EntitlementRevoked mechanism, §1.5
      # outbox
  domain/
    entities/            # Subscription
    value_objects/         # SubscriptionStatus, StripeCustomerId, StripeSubscriptionId
    events/                # base.py (own copy, CLAUDE.md §2.5), subscription_started.py,
                          # subscription_renewed.py, subscription_cancelled.py,
                          # subscription_payment_failed.py, entitlement_granted.py,
                          # entitlement_revoked.py
    ports/                  # payment_provider_port.py (create_checkout_session,
                          # verify_webhook_signature -- the two operations this
                          # plan's scope needs), subscription_repository_port.py,
                          # processed_webhook_events_repository_port.py,
                          # entitlement_revocation_schedule_repository_port.py,
                          # outbox_repository_port.py
  application/
    commands/               # create_checkout_session.py, handle_checkout_completed.py,
                          # handle_invoice_paid.py, handle_subscription_deleted.py,
                          # handle_payment_failed.py, process_due_revocations.py
                          # (the scheduled-worker use case for §1.5)
    queries/                 # get_entitlement_for_user.py (backs the internal endpoint)
    dto/
    errors.py
  infrastructure/
    http/
      routes/                # checkout_routes.py, stripe_webhook_routes.py,
                          # internal_entitlement_routes.py, health.py
      schemas/
      dependencies.py         # reuses packages/shared-contracts' centralized
                          # JWT auth dependency for checkout_routes.py (user-
                          # facing); internal_entitlement_routes.py uses the
                          # X-Internal-Service-Credential pattern per every
                          # prior internal-endpoint precedent
      error_mapping.py
    external/
      stripe_payment_adapter.py   # implements PaymentProviderPort; circuit
                          # breaker + tenacity retry + timeout around the
                          # Checkout Session creation call; webhook signature
                          # verification uses Stripe's own documented HMAC
                          # scheme (no network call needed for that part)
    persistence/
      models.py, postgres_subscription_repository.py,
      postgres_processed_webhook_events_repository.py,
      postgres_entitlement_revocation_schedule_repository.py,
      postgres_outbox_repository.py
    messaging/
      rabbitmq_event_publisher.py, outbox_relay_worker.py
    scheduling/
      revocation_scan_worker.py   # periodic worker invoking
                          # process_due_revocations.py, same shape as
                          # notification-service's reminder_scan_worker.py
    composition_root.py, main.py
  tests/
    unit/domain/            # SubscriptionStatus/StripeCustomerId/StripeSubscriptionId
                          # value object validation, Subscription entity state
                          # transitions
    unit/application/        # all 6 command handlers + the entitlement query,
                          # mocked ports -- including the "cancel schedules
                          # revocation for period end, doesn't revoke
                          # immediately" case
    integration/infrastructure/  # testcontainers Postgres/RabbitMQ,
                          # StripePaymentAdapter against fixture Stripe API
                          # responses (Checkout Session creation) and fixture
                          # webhook payloads (signature verification: valid,
                          # tampered, wrong-secret cases), repository
                          # round-trips, outbox relay, migration,
                          # revocation_scan_worker
    contract/http/         # checkout endpoint, webhook endpoint (valid/invalid
                          # signature, replayed event_id), internal entitlement
                          # endpoint, all 6 event payload contracts

infra/terraform/environments/dev/billing-service.tf   # mirrors
    activity-service.tf's structure; new secret: Stripe API key + webhook
    signing secret via the shared secrets module (never hardcoded)
infra/k8s/charts/billing-service/     # own chart, correct env-list format +
    envFrom wiring from the start; the Stripe webhook route needs an
    Ingress path Kong routes to WITHOUT JWT validation (Stripe signs its
    own payload differently, not a NutriApp-issued JWT) -- document this
    explicitly in the chart/Kong config comments as the one deliberate
    exception to "every route requires a valid JWT," verified instead by
    Stripe-Signature HMAC per §1.2
.github/workflows/billing-service-ci.yml   # mirrors the other services'
    pipelines, pinned uv/action SHAs per existing convention

docs/events-catalog.md     # flip the 6 billing events' Status to Active,
    producer=billing-service, consumers documented-not-yet-consuming
docs/api-catalog.md        # add the checkout endpoint (public), the
    Stripe webhook endpoint (public but not JWT-gated -- document why),
    and the internal entitlement-check endpoint
docs/data-protection-and-privacy.md   # new section per §1.7 above --
    ADR-0015's own follow-up action, done in this plan
docs/domain-glossary-and-context-map.md   # add billing-service's
    relationship entries (Open Host Service for the entitlement-check
    endpoint; documented-future-Customer-Supplier for the entitlement
    events, same treatment as activity-service's ExerciseLogged)
docs/sagas-and-distributed-transactions.md  # verify ProUpgradeEntitlementPropagation's
    existing description still matches what's actually built; note which
    steps are implemented now (billing-service's own side) vs. still
    pending (the three consumers)
ARCHITECTURE.md            # verify any existing billing-service
    placeholder is still accurate
docker-compose.yml         # add a billing-service block, own database,
    matching catalog-service's/activity-service's pattern
```

## 4. Ports/adapters affected

**New ports:** `PaymentProviderPort` (Stripe adapter — the only implementation), `SubscriptionRepositoryPort`, `ProcessedWebhookEventsRepositoryPort`, `EntitlementRevocationScheduleRepositoryPort`, `OutboxRepositoryPort`. No existing port from another service is reused; `packages/shared-contracts`' centralized JWT auth dependency is reused for the user-facing checkout route, per established precedent.

## 5. Domain events

**Published:** `SubscriptionStarted`, `SubscriptionRenewed`, `SubscriptionCancelled`, `SubscriptionPaymentFailed`, `EntitlementGranted`, `EntitlementRevoked` (all v1) — already documented in `docs/events-catalog.md` per ADR-0015's original acceptance, but not yet marked `Active`; this plan flips them to `Active` with producer=`billing-service` once implemented and contract-tested. Consumers (`recipe-service`/`social-service`/`analytics-service`) marked documented-not-yet-consuming, matching `activity-service`'s `ExerciseLogged` precedent.

**Consumed:** none — this service has no inbound domain-event dependency (its only inbound trigger is Stripe's own webhook, an external HTTP call, not an internal domain event).

## 6. Cross-service impact

**Flagged for `architecture-agent` review, already addressed this session:** no other service's code changes. The entitlement-check endpoint (§1.4) is new but has zero real callers today — adding a real caller in `recipe-service`/`social-service`/`analytics-service` later is each of those services' own future implementation plan's concern, not this one's. `docs/events-catalog.md`'s consumer-list entries for the six billing events are metadata-only (documenting a future contract), same treatment as `ExerciseLogged`.

## 7. Resilience/caching/migration needs

- **Circuit breaker** (one external dependency, Stripe's Checkout Session creation call): named `stripe_checkout`, `tenacity` retry (idempotent — Stripe's own idempotency-key mechanism should be used on the create-call itself, per Stripe's documented best practice, so a retried create-session call can't accidentally create two sessions), explicit timeout, dedicated `httpx.AsyncClient`. Webhook signature verification is local HMAC computation, not a network call, so it needs no circuit breaker of its own.
- **No caching layer needed** for this plan's scope — the entitlement-check endpoint is a single indexed Postgres lookup, not a candidate for Redis at this scale (same reasoning as `bff-service`'s and `notification-service`'s suppression-list lookup).
- **Migration**: one initial Alembic migration creating four new tables, purely additive (new service).

## 8. Test plan reference

`/test-plan` will define concrete test cases next: value object validation, the six command handlers (including the deferred-revocation-not-immediate case and the idempotent-webhook-replay case), the entitlement query, `StripePaymentAdapter`'s circuit-breaker matrix and signature-verification cases (valid/tampered/wrong-secret), repository round-trips, outbox atomicity, `revocation_scan_worker`'s due-vs-not-due cases, and contract tests for all four routes and all six event payloads. Not enumerated further here.

## 9. Risks and open questions

1. **Stripe webhook endpoint's Kong/JWT exception** (§3) — this is the one place a route is intentionally public-but-not-JWT-gated, verified by a different mechanism (Stripe-Signature HMAC) entirely. Flagged explicitly so a reviewer doesn't mistake it for a missing-auth bug; documented inline in the Kong config comments and this service's own README.
2. **Real Stripe credentials** — tracked lead-time item (§1's provider-approach note), not a blocker to this plan; this service is built and tested entirely against fixture Stripe API responses and fixture-signed webhook payloads (a real Stripe test-mode secret key can sign fixture payloads offline for the signature-verification tests without any live API call).
3. No other open questions — the three architecturally significant questions (CRUD classification, entitlement-endpoint timing, PCI boundary) were resolved by `architecture-agent` before this plan was written (§1).
