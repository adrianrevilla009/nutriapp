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
  - A `SubscriptionCancelled` or `SubscriptionPaymentFailed` event follows
    the same fan-out shape via `EntitlementRevoked`, applied at the end of
    the paid period per `docs/sla-and-contracts.md`, not immediately on
    cancellation.
- Idempotency: each consumer deduplicates by `event_id`; a lagging or
  duplicate-processing consumer fails safe (treats the user as
  not-yet-entitled) rather than fail open.
- Observability: `correlation_id` set at the webhook-receipt step,
  propagated through `SubscriptionStarted`/`EntitlementGranted` and every
  consumer's processing, so a support investigation ("why can't this user
  publish a recipe") can trace the full fan-out in one trace.

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
