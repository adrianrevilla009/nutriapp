---
description: Review test quality, not just pass/fail — checks tests actually assert behavior and cover the approved test plan. Stage 9 of the human-in-the-loop pipeline in CLAUDE.md section 6. Ideally run by qa-agent, not the agent that wrote the tests.
---
Change to review: $ARGUMENTS

1. Compare the tests actually written against the approved `/test-plan` — is
   every planned case covered? Is anything missing without explanation?
2. Check for tautological tests: does each test assert real behavior (input
   -> expected output/state change), rather than asserting implementation
   details or trivially re-asserting a mock's return value?
3. Verify coverage meets the thresholds in `docs/testing-strategy.md` for
   every layer touched (domain >= 90%, application >= 85%,
   infrastructure >= 70%) — inspect what was actually exercised, not just the
   percentage.
4. If the touched service is `diary-service` or `nutrition-calculation-service`, verify
   a rebuild-from-events test exists and is meaningful (covers more than a
   single trivial event).
5. If a new message consumer was introduced, verify an idempotency test
   exists.
6. If `nutrition-calculation-service` domain logic was touched, note whether a mutation
   testing run would be valuable here and whether it was done.

Return a verdict: **APPROVED**, **APPROVED WITH NOTES**, or **BLOCKED**, with
specific findings tied to the test plan and to `docs/testing-strategy.md`.
