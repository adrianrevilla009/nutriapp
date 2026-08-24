# Compliance Mapping

Full rationale: ADR-0020 (Accepted — GDPR baseline only). This document
maps GDPR's control families to the existing engineering doc/practice
that implements them — one set of engineering controls, referenced by the
compliance narrative, not a duplicate policy document.

## 1. GDPR (Active — the applicable framework)

| Requirement | Implemented by |
|---|---|
| Lawful basis & explicit consent for special-category data | `docs/data-protection-and-privacy.md` section 1 (biometric/health data in `profile-service` is Article 9 special-category) |
| Data minimization | `docs/data-protection-and-privacy.md` section 2 |
| Right to erasure | `docs/data-protection-and-privacy.md` section 4 (crypto-shredding) |
| Data subject access requests (export) | `docs/data-protection-and-privacy.md` section 6 |
| Processor agreements (DPAs) with vendors handling personal data | `docs/vendor-risk-register.md` |
| Access control & audit controls | `docs/authorization-model.md`, `docs/observability-and-audit.md` |
| Encryption at rest & in transit | `docs/secrets-management.md`, `docs/security-and-compliance.md` |
| Breach notification | `docs/incident-response.md` |
| International transfer safeguards (if any vendor processes data outside the EU) | `docs/vendor-risk-register.md` (documented per vendor, not assumed) |

## 2. SOC 2 — N/A

Not pursued (ADR-0020): NutriApp is B2C with no enterprise customer asking
for a SOC 2 report. Revisit if the product direction shifts toward B2B.

## 3. HIPAA — N/A

Does not apply: NutriApp is a consumer wellness/nutrition app, not a
covered entity or business associate handling US-regulated protected
health information (ADR-0020).

## 4. PCI-DSS — scope minimized, not pursued as a certification

`billing-service` delegates all cardholder-data handling to Stripe
(ADR-0015) — the project never stores or transmits raw card data, which
keeps scope to Self-Assessment Questionnaire A rather than a full PCI-DSS
audit. See `.claude/agents/billing-agent.md`'s PCI scope-minimization
rule.

## 5. ISO 27001 — N/A

Not pursued (ADR-0020): no EU-enterprise or government-contract target
market exists.

## 6. Evidence Collection

- Every GDPR control above must have **collectible evidence**, not just a
  policy statement — e.g. consent evidence is an actual per-user consent
  record with timestamp and text version (`docs/data-protection-and-privacy.md`
  section 1), not just the existence of this document.
- Evidence retention periods are defined in
  `docs/backup-and-disaster-recovery.md`'s retention table.
- `security-agent` is responsible for flagging, in any implementation
  review, when a change affects a control mapped above.

## 7. Ownership & Review Cadence

Reviewed whenever ADR-0020 is revisited (e.g. if a future B2B direction
reopens SOC 2, or a healthcare integration reopens HIPAA) or a new service
is scaffolded that touches a mapped control family. `security-agent` owns
keeping this mapping current as the underlying docs evolve.
