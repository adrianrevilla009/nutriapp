# Feature Flags

## 1. Purpose

Decouple **deploy** (code reaches production) from **release** (users
experience the new behavior), so that:
- Risky changes (a new core calculation formula, a new AI assistant prompt
  strategy) can ship to prod disabled, then be enabled for a small percentage
  of users before a full rollout.
- A change causing SLO burn (`docs/observability-slo.md`) can be disabled
  instantly, without a rollback/redeploy cycle.
- Backend and frontend halves of a feature can merge independently and be
  switched on together.

## 2. Tooling

**Unleash** (open-source, self-hostable on EKS, avoids a recurring SaaS cost
for a solo/early-stage project) as the flag service. A thin client wrapper
per language (`packages/shared-contracts` or a small dedicated
`packages/feature-flags-client`) so flag-checking code looks identical across
Python services and the Next.js frontend: `is_enabled("new-core-formula",
context)`.

## 3. Flag Types

| Type              | Use case                                                    | Lifespan                  |
|---------------------|------------------------------------------------------------------|-------------------------------|
| Release flag           | Gating an in-progress feature until it's ready for users              | Removed once fully rolled out    |
| Experiment flag           | A/B testing a change (e.g. two variants of the daily-summary UI)          | Removed once the experiment concludes |
| Ops flag                    | Kill switch for a risky or expensive dependency (disable AI chat if the LLM provider is degraded, falling back to a static response) | Long-lived, deliberately kept |
| Permission flag                | Gating a feature by user segment (e.g. early access)                        | Business-lifetime, not code debt |

## 4. Rules

- Every release/experiment flag has a **named owner and a removal date** set
  when it's created, tracked in an issue — a flag with no removal plan is
  tech debt that compounds (this is the single most common way feature-flag
  systems become unmanageable).
- Flag evaluation logic never duplicates business logic on both sides of the
  flag in a way that diverges silently — the disabled path and enabled path
  should differ only in the specific behavior being tested, not in unrelated
  code paths.
- Flags affecting a domain rule (e.g. a new core calculation formula) go
  through the same test-plan/implementation-plan gates as the underlying
  change (CLAUDE.md section 6) — a flag is not a way to skip review, only a
  way to control blast radius.
- Ops (kill-switch) flags are exercised periodically (a "flag day" drill,
  similar in spirit to the DR game day in
  `docs/backup-and-disaster-recovery.md`) to confirm they actually work when
  needed, not just when first written.

## 5. Frontend/Backend Consistency

Flag state for a given user must be consistent across a single session
(don't evaluate a flag once server-side and differently client-side mid-
session) — the flag context (user ID, cohort) is resolved once per request
and threaded through, not re-evaluated ad hoc.
