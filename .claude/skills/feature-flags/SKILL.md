---
description: Feature flag conventions for NutriApp (Unleash). Use whenever gating new or risky behavior behind a flag, on either backend or frontend.
---

# Feature Flag Conventions — NutriApp

Full policy: `docs/feature-flags.md`.

## Rules
- Every release/experiment flag has a named owner and a removal date, tracked
  in an issue at creation time — no flag without a stated removal plan.
- A flag gating a domain-rule change (e.g. a new core formula) still
  goes through the full implementation-plan/test-plan gates (CLAUDE.md
  section 6) — the flag controls blast radius, it does not replace review.
- Evaluate the flag once per request/session and thread the decision through
  — never re-evaluate ad hoc mid-flow, which can produce inconsistent
  behavior within a single user session.
- Ops (kill-switch) flags are long-lived by design — don't "clean these up."
  Release/experiment flags ARE cleaned up once resolved; leaving them is the
  bug to flag in review.
