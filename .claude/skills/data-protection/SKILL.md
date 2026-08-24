---
description: Personal/health data handling conventions for NutriApp. Use whenever a change touches user data collection, storage, third-party AI data transmission, consent, or deletion/export flows.
---

# Data Protection Conventions — NutriApp

Full policy: `docs/data-protection-and-privacy.md`. Any sensitive personal
data your domain handles is treated with the
higher bar that implies, not the generic-PII bar.

## Rules
- New data collection requires a stated feature purpose and, if it's a new
  category of health-adjacent data, a new explicit consent scope — never
  add a field "in case it's useful."
- Any call to an external vision/LLM provider: strip unnecessary PII before
  the call (name, email, unrelated profile fields), and confirm a DPA exists
  for that provider before it touches real user data.
- Deletion/erasure must satisfy the crypto-shredding checklist in
  `docs/data-protection-and-privacy.md` section 4 — for event-sourced
  services this means shredding the user's data key, not deleting events.
- Any weakening of a data-protection control (shorter consent flow, wider
  retention, less redaction before an external call) requires explicit human
  approval and a documented reason, same as any other security control.
- `security-agent` reviews any change matching the above.
