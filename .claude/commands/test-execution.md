---
description: Run the full test suite for the affected service(s) and report results with coverage. Stage 7 of the human-in-the-loop pipeline in CLAUDE.md section 6.
---
Affected service(s): $ARGUMENTS

1. Run unit tests, then integration tests, then contract tests, for each
   affected service, in that order (fail fast on the cheapest layer first).
2. Run E2E tests only if this change touches a critical user journey listed
   in `docs/testing-strategy.md` section 2.4.
3. Report per layer: pass/fail counts, any flaky test observed, and coverage
   percentage with the delta from before this change.
4. Compare coverage against the thresholds in `docs/testing-strategy.md`
   (domain >= 90%, application >= 85%, infrastructure >= 70%) for every layer
   touched. Explicitly flag any layer below threshold.
5. If `nutrition-calculation-service`'s domain layer was touched, note whether mutation
   testing was run and report the mutation score if available.
6. Do not proceed to `/implementation-review` or `/test-review` automatically
   if any test fails or any touched layer is below its coverage threshold —
   surface this to the human first.
