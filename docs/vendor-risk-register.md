# Vendor / Third-Party Risk Register

`docs/data-protection-and-privacy.md` section 3 requires a DPA before any
vendor processes real user data, particularly the GDPR special-category
biometric/health data in `profile-service` (ADR-0020). This document is
the single tracked register that requirement points to — without a
register, "we have a DPA with our vendors" is an unverifiable claim during
an audit.

## Format per Vendor

```
### <Vendor name>
- Purpose: <what this vendor is used for, and which service integrates it>
- Data shared: <which data categories this vendor receives — reference
  docs/data-protection-and-privacy.md section 0/5's categories>
- Data processing agreement: <in place? date signed? link to the document>
- Data retention/training policy: <does the vendor retain submitted data?
  train on it? zero-retention tier available and used?>
- Compliance relevance: <which framework(s) from docs/compliance-mapping.md
  this vendor's agreement supports>
- Risk tier: Low | Medium | High (based on data sensitivity shared + how
  critical the vendor is to core function)
- Review cadence: <how often this entry is re-verified — annual minimum
  for any Medium/High tier vendor>
- Owner: <which agent/human is responsible for this vendor relationship>
```

---

## Registered Vendors

### LLM/Vision Provider (used by `nutrition-assistant-service` and `food-recognition-service`)
- Purpose: RAG assistant response generation, and food-photo/barcode
  recognition (`.claude/agents/food-recognition-agent.md`).
- Data shared: the user's own retrieved diary/profile context (assistant),
  and uploaded food photos (recognition) — per
  `docs/data-protection-and-privacy.md` section 3.
- Data processing agreement: status to be confirmed once a specific
  provider is selected during `nutrition-assistant-service`'s and
  `food-recognition-service`'s implementation plans — do not assume one
  exists until verified and linked here.
- Data retention/training policy: document the provider's actual policy
  here once selected — do not assume a zero-retention/no-training tier
  without verifying it against the provider's current terms.
- Compliance relevance: GDPR (ADR-0020) — processor agreement required
  before any real user data (including photos) is sent.
- Risk tier: High (core-function-critical + processes user data directly)
- Review cadence: Annual, or on any provider policy change
- Owner: `nutrition-assistant-agent` / `food-recognition-agent` (technical
  integration), `security-agent` (agreement review)

### AWS (infrastructure: EKS, RDS, S3, Secrets Manager, SES, SNS)
- Purpose: Core infrastructure hosting (CLAUDE.md section 2.9)
- Data shared: All operational data (infrastructure-level, not a
  third-party API integration in the usual sense, but still a vendor
  relationship requiring its own DPA/BAA depending on data sensitivity)
- Data processing agreement: AWS's standard DPA (accept as part of AWS
  account setup) — sufficient for the GDPR baseline selected in ADR-0020.
- Data retention/training policy: N/A (infrastructure provider, not a
  model-training concern)
- Compliance relevance: GDPR (ADR-0020)
- Risk tier: High
- Review cadence: Annual
- Owner: `infra-agent`, `security-agent`

### Payment Processor (Stripe recommended — see `.claude/agents/billing-agent.md`)
- Purpose: Pro subscription billing/payment handling (ADR-0015).
- Data shared: ideally none — cardholder data must never reach
  `billing-service`'s own infrastructure; the integration uses the
  provider's hosted checkout/Elements so card data goes directly from the
  client to the provider (`.claude/agents/billing-agent.md`'s PCI
  scope-minimization rule).
- Data processing agreement: status to be confirmed once
  `billing-service`'s implementation plan selects and integrates a
  specific provider — do not assume one exists until verified and linked
  here.
- Compliance relevance: PCI-DSS (scope minimized via tokenization/hosted
  checkout, not eliminated), GDPR (ADR-0020).
- Risk tier: High
- Review cadence: Annual
- Owner: `billing-agent` (technical integration), `security-agent`
  (agreement review)

### Wearable Providers (Apple Health, Google Fit, Fitbit, Garmin) -- `activity-service`
- Purpose: (future, not yet built) syncing exercise/calorie-burn data into
  `activity-service` to adjust TDEE-based nutrition targets
  (`.claude/agents/activity-agent.md`). **Not yet integrated** --
  `/plans/activity-service/implementation-plan.md`'s MVP scope is manual
  exercise logging only. `WearableProviderPort` is defined in the domain
  layer (interface only: `connect`/`sync`/`disconnect`); zero of the four
  providers below have a concrete adapter.
- Data shared: none today (no adapter exists to share anything with).
  Once built, each provider's own OAuth scope would determine exactly
  which activity/calorie-burn fields are shared -- to be documented per
  provider at that time, not assumed now.
- Data processing agreement: not applicable yet -- no data is exchanged
  with any of these vendors. A DPA (or equivalent developer-terms
  acceptance) must be reviewed and linked here before any adapter goes
  live, per this file's standing requirement.
- Data retention/training policy: not applicable yet -- document each
  provider's actual policy when its adapter is built, not assumed now.
- Compliance relevance: GDPR (ADR-0020) -- synced activity data is
  linked to a User and would need the same lawful-basis/consent review
  as any other personal data source before going live.
- Risk tier: not yet assessed (no live integration) -- assess per
  provider at the time a real adapter is planned; a provisional estimate
  is Medium (activity/fitness data, not GDPR Article 9 special-category
  health data on its own, but user-identifying and behaviorally
  sensitive).
- Review cadence: re-assess whenever a new, separately human-approved
  plan proposes building an adapter for any of the four providers below
  (per `.claude/agents/activity-agent.md`: "Any change to which
  providers are supported is significant enough to warrant noting in
  `docs/vendor-risk-register.md`" -- recorded here even in the
  "not yet supported" state so it isn't rediscovered from scratch
  later).
- Owner: `activity-agent` (technical integration, when built),
  `security-agent` (agreement review)
- Per-provider status:
  - **Apple Health** -- not yet integrated. No developer account
    registered.
  - **Google Fit** -- not yet integrated. No developer account
    registered. (Note: Google Fit's public API is in a documented
    sunset/migration path toward Health Connect as of this entry's
    writing -- whichever is current at the time an adapter is actually
    planned must be re-verified, not assumed from this note.)
  - **Fitbit** -- not yet integrated. No developer account registered.
  - **Garmin** -- not yet integrated. No developer account registered.

---

## Ownership & Review

`security-agent` maintains this register and flags, during any
`/implementation-plan` that introduces a new external API integration,
whether a new vendor entry is required before the integration ships —
adding a new third-party dependency without a corresponding entry here is
treated as an incomplete implementation, not a follow-up task.
