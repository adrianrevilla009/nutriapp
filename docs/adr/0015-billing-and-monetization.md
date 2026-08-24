# ADR-0015: Billing & Monetization

## Status
Accepted

## Date
2026-08-23

## Context
NutriApp is a paid product: a freemium model with a Pro subscription tier
gating data sharing/export, report generation, social features, and
recipe publishing/cross-user search (`docs/product-requirements.md`). The
decision matters architecturally because it determines that a new bounded
context (`billing-service`) and a payment processor integration are
needed, and because payment data handling has compliance implications
(`docs/data-protection-and-privacy.md`, PCI-DSS scope) distinct from the
health-adjacent personal data already handled carefully there.

## Decision
- Introduce a dedicated **`billing-service`** (own bounded context, owned
  by `billing-agent`) rather than embedding subscription/payment logic in
  `identity-service` — keeps PCI-DSS-relevant surface isolated to one
  service, following the same isolation logic already applied to
  `notification-service` (ADR-0011).
- **Stripe** as the payment processor: Stripe Billing handles subscription
  lifecycle (trials, upgrades/downgrades, dunning for failed payments)
  without the project ever handling raw card data directly (Stripe.js /
  Stripe Elements tokenizes on the client), keeping the project **out of
  full PCI-DSS scope** (SAQ A eligibility) rather than in it.
- `billing-service` emits events (`SubscriptionStarted`,
  `SubscriptionRenewed`, `SubscriptionCancelled`,
  `SubscriptionPaymentFailed`, `EntitlementGranted`, `EntitlementRevoked`)
  that `recipe-service`, `social-service`, and `analytics-service` react
  to by updating a locally-cached entitlement flag — never a synchronous
  "check if paid" call on every request, consistent with the event-driven
  pattern already used for cross-service reactions elsewhere in the
  system (CLAUDE.md section 2.4) and the Saga pattern for the full
  propagation flow (ADR-0019, `docs/sagas-and-distributed-transactions.md`'s
  `ProUpgradeEntitlementPropagation` saga).

## Considered Alternatives
- **Paddle / LemonSqueezy (merchant-of-record)** — these act as the seller
  of record and handle sales-tax/VAT compliance globally, which Stripe
  Billing alone does not (Stripe Tax is a separate add-on). Worth
  reconsidering specifically if the product sells directly to consumers
  across many tax jurisdictions from day one; Stripe remains the default
  recommendation for a first launch given broader ecosystem maturity and
  documentation.
- **No payment processor abstraction, call Stripe directly from
  `identity-service`** — rejected per the Context above: mixes
  PCI-relevant surface into a service that also owns authentication,
  widening the blast radius of any billing-related incident or audit.
- **No monetization at all (fully free product)** — rejected: the product
  owner's feature list (`docs/product-requirements.md`) explicitly
  specifies a Pro plan gating several features, so this alternative does
  not apply to NutriApp.

## Consequences
### Positive
- Stripe.js tokenization keeps the project out of full PCI-DSS scope.
- Isolating billing logic in its own service keeps a compliance-sensitive
  surface small and auditable.

### Negative / Trade-offs
- A new service and agent to maintain.
- Subscription state becomes another thing `bff-service` aggregates for
  frontend screens (e.g. showing plan status), adding one more upstream
  dependency to that aggregation layer.

### Follow-up actions
- `billing-agent` and `billing-service` are already added to CLAUDE.md
  section 5 and `.claude/agents/` as part of this ADR's acceptance.
- `SubscriptionStarted`/`SubscriptionRenewed`/`SubscriptionCancelled`/
  `SubscriptionPaymentFailed`/`EntitlementGranted`/`EntitlementRevoked`
  are already added to `docs/events-catalog.md`.
- Extend `docs/data-protection-and-privacy.md` with payment-data handling
  in `billing-service`'s own implementation plan (even though Stripe holds
  the actual card data, subscription/billing history is still personal
  data).

## References
- `docs/data-protection-and-privacy.md`
- ADR-0011 (same isolation pattern applied to a compliance-sensitive
  concern)
