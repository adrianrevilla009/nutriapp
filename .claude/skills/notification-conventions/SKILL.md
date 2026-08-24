---
description: Notification (email + push) conventions for NutriApp. Use whenever adding a new triggering event, a new template, or touching notification-service.
---

# Notification Conventions — NutriApp

Full policy: `docs/notifications.md`. Agent: `notification-agent`.

## Rules
- Never send a notification synchronously from within a domain service's
  request/command handling path — always via an emitted event that
  `notification-service` consumes asynchronously. A slow or down email
  provider must never slow down or fail an unrelated user action (e.g.
  the core write action must never wait on SES).
- Transactional (account verification, password reset, security alerts)
  and non-transactional (reminders, anomaly alerts) channels are
  strictly separated: transactional is never suppressed by user preference
  or quiet hours; non-transactional always respects both.
- All notification content is rendered through a versioned template, never
  string-built inline from an event payload — see `docs/notifications.md`
  section 3 for the templating convention.
- Deduplicate on `(event_id, channel)` — replaying the same event must never
  double-send.
- A hard bounce or explicit unsubscribe is honored immediately and
  permanently for that channel; re-subscription requires new explicit
  consent, never an automatic reset.

## When adding a new triggering event
1. Confirm the *decision* to notify lives in the emitting domain service,
   not in `notification-agent` — this service only turns an already-decided
   event into a delivery.
2. Add the event to `docs/events-catalog.md` if not already documented.
3. Add or version the template in `docs/notifications.md` section 3.
4. Write the idempotency test first (per
   `.claude/agents/notification-agent.md` testing requirements) before the
   delivery logic.
