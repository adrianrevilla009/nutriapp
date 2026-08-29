# Data Protection & Privacy

Expands `docs/security-and-compliance.md` section 3 into the full
data-protection posture.

**Fill in section 0 for your domain before relying on the rest of this
document** — the erasure/crypto-shredding mechanism (section 5) is fully
generic and reusable regardless of your answer; sections 1-3 and 5 need
your domain's actual data categories.

## 0. Does This Product Handle Sensitive Personal Data?

**Yes.** `profile-service` holds biometric/health data (weight, height,
age, sex, activity level, goal) — GDPR Article 9 "special category" data
(ADR-0020, Accepted: GDPR baseline). `food-recognition-service` also
processes uploaded food photos, which are personal data by virtue of being
user-submitted, though not themselves special-category unless they
incidentally reveal health information. Sections 1-3 below apply in full.

## 1. Legal Basis

- Processing of sensitive personal data (if applicable per section 0)
  relies on **explicit, informed consent**, collected at signup with a
  specific (not bundled-into-generic-ToS) consent screen describing
  exactly what is collected (list your domain's actual data categories
  here) and why (which features need it).
- Consent is granular where features are optional: retaining any
  optional/richer data (e.g. uploaded media) beyond the minimum needed for
  the core feature is a **separate opt-in**, not bundled with account
  creation (per `docs/security-and-compliance.md` section 3).
- Consent state is itself an auditable record (who consented, to what
  version of the consent text, when) — stored in `identity-service`, treated
  with the same immutability requirement as other audit records
  (`docs/observability-and-audit.md`).
- Withdrawing consent triggers the deletion flow in section 5 below, not just
  a flag flip that leaves data in place.

## 2. Data Minimization

- `food-recognition-service` processes uploaded food photos, extracts the
  needed values, and **discards the media** by default immediately after
  processing succeeds, unless the user has opted in to retaining it.
- No data is collected "in case it's useful later" — every field stored maps
  to a stated feature; new data collection requires a new consent scope, not
  a silent schema addition.

## 3. Third-Party AI Processing (Media Recognition API, LLM Provider)

If the product calls an external vision/LLM provider, this is the
highest-risk data flow in the system: user data leaves the infrastructure
to reach an external provider.

- A **Data Processing Agreement (DPA)** must be in place with any such
  provider before it processes real user data, not just at launch —
  verify this before wiring up any new provider, and record it in
  `docs/mcp-servers.md` or a dedicated vendor register.
- Prefer providers contractually committing to **not** training on submitted
  data, or offering a zero-data-retention tier; document which guarantee each
  integrated provider offers.
- **PII/PHI minimization before the external call**: strip anything not
  needed for the specific inference (e.g. send an uploaded image for
  extraction without attaching the user's name, email, or full profile —
  the external call should be as anonymous as the task allows).
- Log which external calls were made with which data categories (not the
  data itself) as part of the audit trail, so a future access-request or
  breach investigation can reconstruct exposure.

## 4. Third-Party Payment Processing (Stripe, `billing-service`)

ADR-0015's own follow-up action, completed here per
`/plans/billing-service/implementation-plan.md` section 1 acceptance
criterion 7 (not deferred). `billing-service` is the one service in this
codebase that touches payment data — see `.claude/agents/billing-agent.md`
for the full bounded-context rules this section summarizes the compliance
rationale for.

### What is stored

Only Stripe's own opaque references and derived subscription state, in
`billing-service`'s own `subscriptions` table:

- `stripe_customer_id` (`cus_...`), `stripe_subscription_id` (`sub_...`)
  — Stripe's own object identifiers, meaningless outside a call to
  Stripe's API with this service's own secret key.
- Subscription `status` (`active`/`past_due`/`canceled`),
  `current_period_end`, `cancel_at_period_end`, `created_at`/`updated_at`.
- Stripe's own webhook event `id`s, in `processed_webhook_events`, kept
  only for idempotency deduplication (never the full webhook payload body
  — event `id` and a processed timestamp only).

### What is never stored

- **No raw card number, CVV, expiry date, or cardholder name.** This
  service never receives them in the first place: `POST /api/v1/billing/checkout-sessions`
  returns a Stripe-hosted Checkout Session URL, and the browser is
  redirected there — card entry happens entirely on Stripe's own domain.
  Card data physically never reaches this service's servers, request
  logs, or database at any point in the flow.
- **No full payment token or payment-method reference beyond what Stripe's
  own webhook payloads already scope to a customer/subscription.** This
  service does not call `POST /v1/payment_methods` or any endpoint that
  would hand it a reusable card-charging credential — it only ever
  triggers Stripe's own recurring-billing engine via the Subscription
  object Stripe itself manages.
- **No raw webhook payload body is logged.** Structured log lines record
  the event `type` and `id` only (`.claude/agents/billing-agent.md`'s
  explicit "never log a raw card number, CVV, or full payment token"
  rule, enforced as a tested logging-boundary rule in
  `tests/contract/http/test_stripe_webhook_routes.py`, not an assumption
  that stays true by accident).

### SAQ A eligibility rationale

Because card data is entered exclusively on Stripe's own hosted Checkout
page and never transits, is processed by, or is stored on any
NutriApp-controlled system, `billing-service`'s PCI DSS scope qualifies
for **SAQ A** (the lightest PCI Self-Assessment Questionnaire tier,
applicable when card data is fully outsourced to a PCI-validated
third-party processor via a redirect/hosted-fields integration; see
Stripe's own SAQ A eligibility documentation,
https://stripe.com/docs/security). This is exactly why the implementation
plan and `.claude/agents/billing-agent.md` mandate hosted Checkout as a
day-one architectural constraint (not a later hardening pass) — any
alternative that collects card data through a NutriApp-controlled form,
even one that forwards it immediately to Stripe (Stripe Elements embedded
client-side without a redirect, or any custom card form), moves this
service into a materially heavier SAQ tier and is out of scope without a
new ADR.

### DPA / vendor status

Stripe's processing of NutriApp's payment data (customer/subscription
metadata, never raw card data) is covered under Stripe's own standard
merchant Data Processing Agreement — tracked in
`docs/vendor-risk-register.md` alongside every other third-party
processor. Real production Stripe account setup (API keys, webhook
registration) is a tracked lead-time item (implementation plan section 9,
risk 2), not a blocker to this section's compliance posture, which holds
regardless of whether the underlying keys are live or placeholder.

## 5. Right to Erasure ("Right to be Forgotten")

This interacts non-trivially with Event Sourcing (ADR-0002), because the
event store is meant to be immutable and append-only, while erasure requires
that personal data actually become unreadable. This mechanism is fully
domain-agnostic — keep it as-is.

**Resolution: crypto-shredding.** Personal data fields inside event payloads
that must be erasable (not the whole event, just the personal fields) are
encrypted per-user with a user-specific data key. Erasure deletes the
user's data key, not the event — the event remains structurally intact
(aggregate IDs, event types, timestamps) for system integrity, but its
personal-data fields become permanently unreadable ciphertext.

**Key ownership: per-service, not centralized** (ADR-0023, formalizing the
decision originally made in
`/plans/profile-service/implementation-plan.md` Addendum 1 — this line
previously said "identity-service's key store," which never existed:
`identity-service`'s approved implementation plan and its test suite
contain no key store, no KMS integration, and no account-deletion
endpoint at all). Each event-sourced service that holds erasable personal
data owns its own per-user data-key table, KMS-wrapped (envelope
encryption) — e.g. `profile-service`'s `profile_data_keys` table
(`services/profile-service/infrastructure/persistence/models.py`). This is
consistent with CLAUDE.md section 2.5's "no shared schemas across service
boundaries" principle already applied to every other per-service table
(outbox, event store: every service gets its own, never a shared one). A
future cross-cutting initiative may consolidate key ownership into a
shared capability if/when a concrete need for that emerges; nothing today
depends on that consolidation happening first. **Note:** `profile-service`
currently implements the encrypted-storage half of this (crypto-shredding-
*ready*) but not the erasure trigger itself — no upstream
`AccountDeletionRequested`-style event exists yet anywhere in the system,
so the deletion consumer/endpoint is explicitly out of scope until that
trigger exists (see that plan's section 9.2). The checklist below still
describes the target end-to-end flow once a trigger exists.

Erasure checklist, verified end-to-end (not just "delete the users row"):
1. Delete/expire the user's data key (crypto-shred), making event-store
   personal fields unreadable.
2. Delete the user's row from every service's write-model database that
   holds it directly (not event-sourced services, which use step 1).
3. Trigger rebuild or targeted deletion of the user's data from every read
   model / projection.
4. Delete the user's vectors from Qdrant (`nutrition-assistant-service`, if applicable).
5. Delete any retained uploaded media from object storage (respecting the
   backup retention window in `docs/backup-and-disaster-recovery.md` — note
   to the user that backups purge on their own schedule, not instantly).
6. Record the erasure request and its completion in the audit trail (the
   audit record of "erasure happened on this date" is itself retained, since
   it is not personal data about the user, just a compliance record).
7. Confirm to the user, within the legally required window (typically 30
   days), that erasure is complete.

## 6. Data Retention Defaults

| Data category                                    | Default retention                          |
|----------------------------------------------------|-------------------------------------------------|
| Diary entries (food, water, fasting, meal plans)    | Retained while the account is active + 90 days after deletion (grace period for accidental deletion recovery), then erased |
| Profile biometric/health metrics                     | Same as diary entries; erasure via crypto-shredding is mandatory given GDPR Art. 9 status (section 5) |
| Uploaded food photos                                  | Discarded immediately after `food-recognition-service` processing succeeds, unless the user opts in to retention (then: per user setting, default 1 year, user-configurable) |
| Audit records (auth, admin actions, subscription/payment events) | 3 years (compliance-driven, not personal-data-driven) |
| Subscription/entitlement records (`billing-service`: Stripe customer/subscription IDs, status, timestamps — never raw card data, see section 4) | Retained while the account is active + 90 days after cancellation (mirrors the diary-entry grace period), then erased; Stripe's own record of the underlying charges is retained per Stripe's own compliance obligations, independent of this service's copy |
| Consent records                                        | Retained as long as the account exists + statute-of-limitations window after deletion |

## 7. Data Subject Access Requests (DSAR)

- Users can request an export of their data (a first-class feature per
  CLAUDE.md section 8, not an afterthought) — a single endpoint aggregating
  across every service that holds their data, assembled asynchronously and
  delivered via a signed, expiring download link.
- Response time target: 30 days maximum, tracked as an SLA in
  `docs/observability-slo.md`.

## 8. Ownership

`security-agent` reviews any change touching personal data handling,
consent flow, or third-party data transmission, using this document and
`docs/security-and-compliance.md` as the reference. Any weakening of a
protection here requires explicit human approval and a documented reason,
per the same rule as security controls generally (CLAUDE.md /
`security-agent.md`).
