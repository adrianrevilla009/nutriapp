# Notifications: Email & Push

Full rationale: ADR-0011. Agent: `notification-agent`. Skill:
`.claude/skills/notification-conventions/SKILL.md`.

## 1. Channels & Events

| Channel   | Example trigger event         | Transactional? | Suppressible by preference? |
|-----------|----------------------------------|-------------------|---------------------------------|
| Email     | `UserRegistered` (verification)  | Yes               | No                               |
| Email     | `PasswordResetRequested`         | Yes               | No                               |
| Email     | `NewDeviceLoginDetected`         | Yes               | No                               |
| Push      | Meal/water/fasting reminder due  | No                | Yes                              |
| Push      | `NutrientDeficiencyDetected`     | No                | Yes (but on by default)          |
| Push      | `UserFollowed` (social-service)  | No                | Yes                              |

Any new event added to either row of the "No" column requires explicit
sign-off in an ADR update, not a silent addition — transactional-vs-not is
a legal/UX classification, not an implementation detail. `UserFollowed`'s
sign-off is recorded as a dated addendum to ADR-0011 rather than a new ADR
number: it applies the already-established push
(non-transactional/suppressible/quiet-hours-respecting) classification
unchanged, it does not introduce a new classification of its own.

## 2. User Preferences & Quiet Hours

- Users control non-transactional push categories independently
  (meal/water/fasting reminders can be off while nutrient-deficiency
  alerts stay on, or vice versa).
- Quiet hours (default 22:00–08:00 local time, user-adjustable) delay
  non-transactional sends to the next allowed window — never drop them
  silently; a delayed reminder still fires once quiet hours end, unless it
  has become stale (see suppression rule below).
- A reminder whose relevance window has passed (e.g. a "perform the core
  action" reminder well after its usual time) is suppressed rather than sent late and
  confusing — this rule lives in the domain layer of
  `notification-service`, not the provider adapter.
- For a **periodic** trigger (meal/water/fasting reminders), a quiet-hours
  delay is naturally retried on the next scheduled scan of the
  `reminder_schedule` projection. For a **one-shot** trigger with no next
  occurrence (e.g. `UserFollowed`), the delayed send is persisted as a
  `pending_push_dispatch` row instead and retried by its own periodic scan
  worker until the recipient's quiet hours end — same guarantee (delayed,
  never dropped), different mechanism, because the two triggers have no
  natural "next occurrence" in common.

## 3. Templating

- Every notification is rendered through a versioned template
  (`template_id@version`), never string-built inline from the triggering
  event's payload.
- Templates live under `notification-service`'s own repo path, reviewed
  like code (they are code) — content changes go through the same
  human-in-the-loop pipeline as any other change (CLAUDE.md section 6).
- All user-supplied values interpolated into an email template are
  HTML-escaped by the templating engine by default — never manually
  string-concatenated into HTML.

## 4. Delivery Log & Suppression

- Every send attempt is recorded in a delivery-log read model:
  `sent | delivered | bounced | failed`, per channel, per user.
- A hard bounce (email) or explicit unsubscribe adds the address/device to
  a permanent suppression list, checked before every send — re-addition
  requires new explicit user consent, never automatic.
- Soft bounces are retried with backoff (`tenacity`, per CLAUDE.md section
  4) up to a bounded number of attempts before being logged as `failed`.

## 5. Testing & Sandbox

- CI and local development never send real email/push — SES sandbox mode
  and a local fake push endpoint are used in integration tests, per
  `.claude/agents/notification-agent.md` testing requirements.
- `staging` uses real SES/SNS but restricted to an allowlist of internal
  test addresses/devices until `identity-service`'s user base in that
  environment is trusted test data only.
