# ADR-0011: `notification-service`, Transactional Email, and Push Notification Providers

## Status
Accepted

## Date
2026-08-23

## Context
Several already-specified features have no delivery mechanism:
`identity-service` needs to send account verification and password-reset
emails; `analytics-service` emits `NutrientDeficiencyDetected` (see
`.claude/agents/analytics-agent.md`) with no consumer that turns it into
anything the user sees outside the app; meal/water/fasting reminders are
implied by the product description but nothing sends them. Without a
dedicated service, this logic would otherwise leak into `identity-service`
or `analytics-service` directly, coupling unrelated business services to
specific delivery providers — exactly what the hexagonal/ports-and-adapters
rule in ADR-0001 exists to prevent.

## Decision
- Introduce **`notification-service`** as a new bounded context (added to
  the service map in ARCHITECTURE.md and CLAUDE.md section 5), owned by
  `notification-agent`. It consumes events from other services and owns no
  business decision-making of its own — see
  `.claude/agents/notification-agent.md`.
- **Transactional email**: **Amazon SES**. Chosen for AWS-stack consistency
  (already the deployment target per ADR-0006) and low cost at this scale
  (pay-per-email, no platform fee).
- **Push notifications**: **Amazon SNS** as the fan-out layer to APNs
  (iOS) and FCM (Android), rather than calling APNs/FCM directly — SNS
  handles device token/endpoint management and is already inside the AWS
  account boundary the project operates in.
- Both are added to `docs/mcp-servers.md`'s pattern of "specified,
  activated only when its condition is met": neither is provisioned until
  `identity-service` (for email) or a mobile client (for push, see
  ADR-0013 discussion) actually exists to trigger the first real send.

## Considered Alternatives
- **SendGrid / Postmark for email** — better deliverability tooling and
  analytics out of the box than raw SES, but a second vendor and a second
  bill outside the AWS account, for a capability SES covers adequately at
  current scale. Rejected for now; revisit via a new ADR if deliverability
  issues (spam-folder rates) become a measured problem SES's tooling can't
  diagnose.
- **Firebase Cloud Messaging directly for both iOS and Android** (skipping
  APNs/SNS split) — simpler if the client is ever Flutter/cross-platform
  only, but the project's frontend stack (ADR/CLAUDE.md section 4) is
  React/Next.js web-first; if a native mobile client is built (pending
  product decision, see `docs/mobile-app-strategy.md`), SNS's dual-fan-out
  keeps the delivery layer provider-agnostic regardless of which native
  stack is chosen later.
- **No dedicated service, inline sending from each domain service** — what
  exists today (nothing). Rejected per the Context above: couples unrelated
  services to delivery-provider specifics and duplicates
  retry/bounce-handling logic across every emitting service.

## Consequences
### Positive
- Every domain service stays ignorant of *how* a user is notified — it only
  emits an event.
- Bounce/unsubscribe/quiet-hours logic exists in exactly one place.

### Negative / Trade-offs
- One more service to operate, test, and keep available (though its
  criticality is lower than write-path services — a delayed notification is
  degraded, not broken, product behavior).
- SES requires production-access approval from AWS (sandbox mode limits
  sending) — a lead-time item to track in
  `docs/project-status-tracking.md`, not a blocker to specifying the
  architecture now.

### Follow-up actions
- Add `notification-service` to the service map in ARCHITECTURE.md and
  CLAUDE.md section 5 (done).
- Request AWS SES production access ahead of `identity-service` needing it.
- Write `docs/events-catalog.md` entries for every event
  `notification-service` consumes as each emitting service is built.

## References
- `docs/notifications.md`
- `.claude/agents/notification-agent.md`
- ADR-0001, ADR-0006
