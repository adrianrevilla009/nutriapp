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
- Purpose: RAG assistant response generation (Claude Messages API, model
  `claude-haiku-4-5` starting tier per
  `/plans/nutrition-assistant-service/implementation-plan.md` section 9
  resolution 5), and food-photo/barcode recognition
  (`.claude/agents/food-recognition-agent.md`).
- Provider selected: Anthropic (same vendor `food-recognition-service`
  already uses for `ClaudeVisionAdapter`; `nutrition-assistant-service`'s
  `ClaudeConversationAdapter` is a separate metered API-key container per
  service, never a shared credential).
- Data shared: the user's own retrieved diary/nutrition/analytics context
  assembled into the prompt (assistant), and uploaded food photos
  (recognition) — per `docs/data-protection-and-privacy.md` section 3.
  **Embeddings are NOT sent to this vendor** — `nutrition-assistant-service`'s
  embedding step is a separate, self-hosted, open-source model with no
  external network call at all (see the new entry below); only the final
  generation call (structured context + query) goes to Anthropic.
- Data processing agreement: status still to be formally confirmed/signed
  — implementation carries the same Anthropic commercial-API data
  handling assumption `food-recognition-service`'s own entry already
  documents (reviewed 2026-08-27 per that service's README, due for
  re-verification on any terms update) — do not treat this as a signed
  DPA until `security-agent` confirms one exists.
- Data retention/training policy: same as `food-recognition-service`'s
  existing entry — Anthropic's commercial Messages API does not train on
  submitted content by default and retains inputs/outputs only
  transiently for abuse monitoring, per that service's README (verified
  2026-08-27) — re-verify on any major terms update, not treated as
  permanently settled for this service either.
- Compliance relevance: GDPR (ADR-0020) — processor agreement required
  before any real user data is sent.
- Risk tier: High (core-function-critical + processes user data directly)
- Review cadence: Annual, or on any provider policy change
- Owner: `nutrition-assistant-agent` / `food-recognition-agent` (technical
  integration), `security-agent` (agreement review)

### Embedding model (used by `nutrition-assistant-service`)
- Purpose: embeds the curated knowledge-base corpus and chat queries for
  Qdrant similarity search (`domain/ports/embedding_port.py`).
- Provider selected: NONE — self-hosted, open-source
  `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0 license), run
  in-process via `fastembed` (ONNX Runtime backend). No third-party
  vendor, no network call, no new DPA needed — implementation plan
  section 9 resolution 1's explicit reasoning for avoiding a second
  vendor relationship.
- Data shared: none (no external call at all).
- Data processing agreement: not applicable — no vendor involved.
- Data retention/training policy: not applicable.
- Compliance relevance: none — flagged here only so a future reviewer
  doesn't assume embeddings are silently going to Anthropic or another
  third party.
- Risk tier: Low (no data leaves the cluster for this step)
- Review cadence: revisit if this pass's small hand-authored knowledge
  base ever grows enough to need a different/larger model.
- Owner: `nutrition-assistant-agent`

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

### Payment Processor (Stripe — selected and integrated, `billing-service`)
- Purpose: Pro subscription billing/payment handling (ADR-0015).
  `/plans/billing-service/implementation-plan.md` built `StripePaymentAdapter`
  against Stripe's real, publicly documented API contract (Checkout
  Sessions, webhook signature verification); real API key/webhook-secret
  provisioning remains a tracked lead-time item (implementation plan
  section 9, risk 2) — not a blocker to the integration being built and
  tested (fixture-only, never a live call).
- Data shared: none — cardholder data never reaches `billing-service`'s
  own infrastructure. The integration uses Stripe's hosted Checkout so
  card data goes directly from the client to Stripe
  (`.claude/agents/billing-agent.md`'s PCI scope-minimization rule,
  `docs/data-protection-and-privacy.md` section 4 for the full
  what's-stored/what's-never-stored breakdown and SAQ A eligibility
  rationale).
- Data processing agreement: covered under Stripe's standard merchant DPA
  (`docs/data-protection-and-privacy.md` section 4) — confirm the
  specific signed agreement reference once a real (non-placeholder)
  Stripe account is provisioned.
- Compliance relevance: PCI-DSS (SAQ A — card data fully outsourced to
  Stripe via hosted Checkout, never touching a NutriApp-controlled
  system), GDPR (ADR-0020).
- Risk tier: High
- Review cadence: Annual
- Owner: `billing-agent` (technical integration), `security-agent`
  (agreement review)

### Wearable Providers (Apple Health, Google Fit, Fitbit, Garmin) -- `activity-service`
- Purpose: syncing exercise/calorie-burn data into `activity-service` to
  adjust TDEE-based nutrition targets (`.claude/agents/activity-agent.md`).
  **Fitbit only, as of the 2026-09-11 addendum to
  `/plans/activity-service/implementation-plan.md`**: a `FitbitProviderAdapter`
  (`services/activity-service/infrastructure/external/fitbit_provider_adapter.py`)
  now exists code-wise, implementing `WearableProviderPort`'s
  `connect`/`sync`/`disconnect` against Fitbit's real, publicly documented
  OAuth 2.0 Authorization Code / Activity Logs List API. It is
  **structurally tested against `httpx.MockTransport` fixtures only --
  never a live Fitbit call -- and is UNVERIFIED against the real Fitbit
  API**, because no real Fitbit developer account/OAuth credentials exist
  in this environment. It is also **gated behind an explicit,
  defaults-off feature flag** (`ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED`,
  `Container.fitbit_provider` in `infrastructure/composition_root.py`)
  that additionally refuses to construct the adapter unless real-looking
  `ACTIVITY_SERVICE_FITBIT_CLIENT_ID`/`_CLIENT_SECRET` values are also
  configured -- so there is no way for this adapter to activate in any
  real deployment of this repo today. Apple Health, Google Fit, and
  Garmin remain not yet integrated (interface-only, zero adapters).
- Data shared: **none today** -- the adapter has never made a real
  network call (feature-flag gated off, no real credentials configured).
  Once activated with a real Fitbit developer account, Fitbit's own OAuth
  scope (`activity`, per the adapter's token-exchange request) would
  determine exactly which activity/calorie-burn fields are shared -- this
  must be re-confirmed against the real account's granted scope at
  activation time, not assumed from the code alone. No data is shared
  with Apple Health, Google Fit, or Garmin (no adapter exists for any of
  the three).
- Data processing agreement: **not yet in place for Fitbit** -- no real
  Fitbit developer account exists, so no developer-terms acceptance has
  happened yet. A DPA (or equivalent Fitbit developer-terms acceptance)
  must be reviewed and linked here BEFORE a human provisions real
  credentials and flips `ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED` in any
  real environment -- this is a precondition of activation, not a
  follow-up. Not applicable yet for Apple Health, Google Fit, or Garmin.
- Data retention/training policy: not yet documented for Fitbit -- review
  Fitbit's actual developer-terms retention/training policy at the same
  time as the DPA review above, before activation. Not applicable yet for
  the other three providers.
- Compliance relevance: GDPR (ADR-0020) -- synced activity data would be
  linked to a User and needs the same lawful-basis/consent review as any
  other personal data source before going live; this review has not yet
  happened because the adapter has never gone live.
- Risk tier: **Medium (provisional, unchanged from the prior assessment)**
  -- activity/fitness data is user-identifying and behaviorally sensitive
  but not GDPR Article 9 special-category health data on its own. Confirm
  or revise this tier as part of the pre-activation compliance review
  above, not assumed unchanged forever.
- Review cadence: re-assess before any human flips
  `ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED` on in a real environment, and
  whenever a new, separately human-approved plan proposes building an
  adapter for Apple Health, Google Fit, or Garmin (per
  `.claude/agents/activity-agent.md`: "Any change to which providers are
  supported is significant enough to warrant noting in
  `docs/vendor-risk-register.md`").
- Owner: `activity-agent` (technical integration), `security-agent`
  (agreement review, pre-activation compliance review)
- Per-provider status:
  - **Apple Health** -- not yet integrated. No developer account
    registered.
  - **Google Fit** -- not yet integrated. No developer account
    registered. (Note: Google Fit's public API is in a documented
    sunset/migration path toward Health Connect as of this entry's
    writing -- whichever is current at the time an adapter is actually
    planned must be re-verified, not assumed from this note.)
  - **Fitbit** -- adapter code exists (`FitbitProviderAdapter`), tested
    exclusively against `httpx.MockTransport` fixtures, **unverified
    against the real Fitbit API**, gated behind a defaults-off feature
    flag with a hard credential-presence check. No developer account
    registered; DPA/developer-terms review still outstanding. Obtaining
    a real developer account and completing that review are human
    actions, out of scope for the 2026-09-11 addendum that authorized
    building this adapter against fixtures.
  - **Garmin** -- not yet integrated. No developer account registered.

---

## Ownership & Review

`security-agent` maintains this register and flags, during any
`/implementation-plan` that introduces a new external API integration,
whether a new vendor entry is required before the integration ships —
adding a new third-party dependency without a corresponding entry here is
treated as an incomplete implementation, not a follow-up task.
