# Sagas and Distributed Transactions

Full rationale: ADR-0019. This document is the living catalog of every
saga in the system — the cross-service equivalent of
`docs/events-catalog.md`, since a saga is defined by a chain of events
across multiple services, not a single service's schema.

## Format per Saga

```
### <SagaName>
- Trigger: <the initiating event/command and originating service>
- Style: Choreography | Orchestration
- Steps:
  1. <service> does <action> -> emits <EventName>
  2. <service> reacts to <EventName> -> does <action> -> emits <EventName>
  ...
- Compensations:
  - If step N fails after step M succeeded: <service> reacts to
    <FailureEvent> -> emits <CompensatingEvent> -> <service that did step M>
    reverses its effect.
- Idempotency: <how each step's consumer deduplicates>
- Observability: <correlation_id used to trace the full saga end-to-end>
```

---

## Planned Sagas

### FoodEntryLoggedRecomputation
*A diary write that must trigger a nutrition-target recomputation and,
above a threshold, a notification — a downstream failure must not leave
the entry silently un-reflected in the user's computed totals.*

- Trigger: user logs a food entry in `diary-service`.
- Style: Choreography (3 steps — within the threshold in ADR-0019 for
  staying choreography-based rather than promoting to orchestration).
- Steps:
  1. `diary-service` validates and records the entry -> emits
     `FoodEntryLogged`.
  2. `nutrition-calculation-service` consumes `FoodEntryLogged` -> recomputes
     the day's nutrient totals -> emits `NutritionValueRecomputed`.
  3. `notification-service` consumes `NutritionValueRecomputed` (if the
     change crosses a threshold worth notifying about, e.g. a target
     significantly exceeded) -> sends a push notification.
- Compensations:
  - If step 2 fails permanently (e.g. the computation is undefined for
    this input after retries are exhausted per
    `.claude/skills/resilience-patterns/SKILL.md`): `nutrition-calculation-service`
    emits `RecomputationFailed`; `diary-service` consumes it and marks the
    entry as "recorded, pending recomputation" in its read model, surfaced
    to the user rather than silently showing a stale total as current.
  - Step 3 has no compensation required — a failed/delayed notification
    is a degraded experience, not a data-consistency problem; it is
    retried per standard resilience patterns, not compensated.
- Idempotency: `nutrition-calculation-service`'s consumer deduplicates on
  `event_id`; recomputation itself is idempotent (recomputing from the
  same recorded entries twice yields the same result), so duplicate
  delivery is safe beyond the dedup check alone.
- Observability: `correlation_id` set at step 1, propagated through
  every subsequent event's metadata (CLAUDE.md section 2.3), letting a
  single trace reconstruct the full saga in Jaeger.

### ProUpgradeEntitlementPropagation
*A subscription purchase that must propagate an entitlement flag to every
Pro-gated service before the user can rely on those features working —
this is the reason `billing-service` publishes entitlement events instead
of every consumer calling it synchronously on every request.*

- Trigger: payment provider webhook confirms a successful charge, received
  by `billing-service`.
- Style: Choreography (fan-out to independent consumers, no shared
  in-flight state to track — each consumer's cached entitlement flag is
  independently correct once its own event is processed).
- Steps:
  1. `billing-service` verifies the webhook signature, records the
     subscription -> emits `SubscriptionStarted` -> emits
     `EntitlementGranted`.
  2. `recipe-service`, `social-service`, and `analytics-service` each
     consume `EntitlementGranted` -> update their locally-cached
     entitlement flag for that user.
- Compensations:
  - If a consumer's entitlement-flag update fails after retries: it falls
    back to `billing-service`'s synchronous entitlement-check endpoint
    (behind a circuit breaker) on the next Pro-feature request, rather
    than serving a stale "not entitled" flag indefinitely.
  - A `SubscriptionCancelled` event schedules `EntitlementRevoked` for the
    subscription's `current_period_end` (never immediately on
    cancellation) — the same fan-out shape, just deferred. A
    `SubscriptionPaymentFailed` event does NOT, by itself, ever lead to
    `EntitlementRevoked`: Stripe's own dunning/retry window determines
    if/when the subscription is ultimately canceled (a later
    `SubscriptionCancelled`, which is what actually schedules the
    revocation) — corrected here from an earlier draft that implied
    `SubscriptionPaymentFailed` also fed the same revocation path
    directly.
- Idempotency: each consumer deduplicates by `event_id`; a lagging or
  duplicate-processing consumer fails safe (treats the user as
  not-yet-entitled) rather than fail open.
- Observability: `correlation_id` set at the webhook-receipt step,
  propagated through `SubscriptionStarted`/`EntitlementGranted` and every
  consumer's processing, so a support investigation ("why can't this user
  publish a recipe") can trace the full fan-out in one trace.
- **Implementation status** (`/plans/billing-service/implementation-plan.md`,
  `/plans/recipe-service/implementation-plan.md`,
  `/plans/social-service/implementation-plan.md`):
  `billing-service`'s own side of this saga is built —
  webhook-signature-verified, idempotent (dedupes by Stripe's own event
  `id`) `checkout.session.completed`/`invoice.paid`/
  `customer.subscription.deleted`/`invoice.payment_failed` handling, the
  Outbox-published `SubscriptionStarted`/`SubscriptionRenewed`/
  `SubscriptionCancelled`/`SubscriptionPaymentFailed`/`EntitlementGranted`/
  `EntitlementRevoked` events (all `Status: Active` in
  `docs/events-catalog.md`), the deferred-revocation scheduling mechanism
  (`entitlement_revocation_schedule` + `revocation_scan_worker.py`), and
  the synchronous fallback endpoint
  (`GET /internal/v1/billing/entitlements/{user_id}`). Step 2 is now
  PARTIALLY built: `recipe-service` is the FIRST of the three documented
  consumers to actually implement its side of the fan-out --
  `billing_events_consumer.py` subscribes to `billing.events` (routing
  key `billing.entitlement.*`), idempotently (by `event_id`) upserting
  its local `entitlement_cache` table, checked cache-first by
  `PublishRecipeHandler`/`SearchPublishedRecipesHandler` before falling
  back to the synchronous endpoint on a genuine cache miss (own
  `billing_entitlement_check` circuit breaker, never sharing state with
  the separate `catalog_product_lookup` breaker used for ingredient
  resolution). `social-service` is now the SECOND of the three documented
  consumers to implement its side of the fan-out -- its own
  `billing_events_consumer.py` (own queue/DLQ names, own `entitlement_cache`
  table, own `processed_entitlement_events` idempotency ledger) is
  structurally identical to `recipe-service`'s, checked cache-first by
  `FollowUserHandler`/`UnfollowUserHandler`/`GetFeedHandler` before falling
  back to the synchronous endpoint on a genuine cache miss (own,
  independently-named `billing_entitlement_check` circuit breaker --
  social-service has no `catalog_product_lookup`-equivalent breaker at
  all, since it makes no other synchronous external call).
  `HandleEntitlementRevokedHandler` is structurally non-destructive: it has
  no reference to `FollowRepositoryPort` at all, so revocation can never
  delete/hide an existing follow or feed entry. `analytics-service` remains
  pending: that service doesn't exist yet, same deferral pattern as
  `activity-service`'s `ExerciseLogged` consumers. This saga's choreography
  is now fully exercised end-to-end for two of its three documented
  consumers (`recipe-service`, `social-service`); the remaining consumer
  will exercise the same already-proven pattern once built.

---

Add new sagas above this line as new cross-service business transactions
are introduced. Every saga listed here must also have its individual
events already documented in `docs/events-catalog.md` — this document
adds the *sequence and compensation* view on top, it does not replace the
per-event schema documentation.

## Ownership

`architecture-agent` reviews any new multi-step cross-service flow to
determine whether it constitutes an undocumented saga per ADR-0019's
definition (2+ services, ordered steps, an all-or-nothing business
outcome) before approving an `/implementation-plan` that introduces it.
