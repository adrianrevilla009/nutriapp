# ADR-0020: Target Compliance Framework

## Status
Accepted

## Date
2026-08-23

## Context
`docs/security-and-compliance.md` and `docs/data-protection-and-privacy.md`
already specify strong practices (encryption, audit trails, consent,
crypto-shredding, SAST/SBOM). None of them are currently **mapped to a
named compliance framework's actual control list** — which matters
because "we follow good security practice" and "we can produce evidence
for a SOC 2 Type II audit" are different claims requiring different
artifacts (control ownership, evidence collection cadence, an actual
audit).

## Decision
- **GDPR baseline only. No formal certification (SOC 2, HIPAA, ISO 27001)
  pursued at this stage.** NutriApp is a B2C consumer product (ADR-0018),
  not B2B SaaS, so the SOC 2-first default that applies to enterprise
  procurement doesn't apply here — there is no enterprise customer asking
  for a SOC 2 report. What does apply unconditionally is GDPR: the
  biometric/health metrics in `profile-service` are Article 9
  "special category" data (`docs/data-protection-and-privacy.md` section
  0), which requires explicit consent, a documented lawful basis, and
  data minimization regardless of company size or market — this is a
  legal requirement for any EU user, not an optional certification.
- **PCI-DSS scope is minimized, not eliminated**, by `billing-service`
  delegating card handling entirely to Stripe (ADR-0015) — the project
  never touches raw card data, keeping PCI-DSS scope to "self-assessment
  questionnaire A."
- **HIPAA does not apply**: NutriApp does not handle US-regulated
  protected health information as a covered entity or business associate
  — it is a consumer wellness/nutrition app, not a healthcare provider
  integration. Revisit only if a future feature integrates with a covered
  entity (e.g. a clinician-facing view).
- **ISO 27001 does not apply**: no EU-enterprise or government-contract
  target market exists.
- Map GDPR's control families to the existing doc that implements them
  (see `docs/compliance-mapping.md`), rather than writing a duplicate
  policy document.

## Considered Alternatives
- **Pursue SOC 2 Type II now** — rejected for this stage: SOC 2 exists
  primarily to satisfy enterprise B2B procurement, which doesn't apply to
  a B2C product with no enterprise customer (ADR-0018). Revisit the
  moment a business customer's procurement process actually asks for a
  SOC 2 report or security questionnaire — retrofitting evidence
  collection after months of undocumented practice is far more expensive
  than starting the evidence trail from `identity-service`'s first
  implementation, so this should be revisited proactively if the product
  direction shifts toward B2B, not left until the request arrives.
- **No privacy compliance rigor at all, GDPR included** — rejected: unlike
  SOC 2/HIPAA/ISO 27001 (all optional certifications a business chooses to
  pursue), GDPR compliance for the special-category biometric data in
  `profile-service` is a legal requirement for any EU user, not an
  optional posture — this is why GDPR is treated differently from the
  other three frameworks in the Decision above.

## Consequences
### Positive
- Every security/privacy practice already in this repo (encryption, audit
  trails, consent, crypto-shredding) maps directly to GDPR's actual legal
  requirements, without the overhead of maintaining a parallel SOC 2/
  HIPAA/ISO 27001 evidence program the product doesn't need yet.

### Negative / Trade-offs
- If the product direction shifts toward B2B or a US healthcare
  integration, this ADR must be revisited and superseded — it is not
  written to silently cover that case if it arrives.

### Follow-up actions
- `docs/compliance-mapping.md` is updated to a GDPR-only scope, with
  HIPAA/SOC 2/PCI-DSS rows marked N/A rather than left as if pending.
- `security-agent` treats any weakening of a control mapped to GDPR
  (consent, minimization, erasure) as requiring not just human approval
  (already mandatory, CLAUDE.md section 7) but an explicit compliance-
  impact note in that approval.

## References
- `docs/compliance-mapping.md`
- `docs/security-and-compliance.md`
- `docs/data-protection-and-privacy.md`
- `docs/vendor-risk-register.md`
- ADR-0015 (billing — PCI-DSS trigger)
