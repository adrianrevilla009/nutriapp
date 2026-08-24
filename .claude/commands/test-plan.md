---
description: Define concrete test cases before any implementation code is written (TDD). Stage 4 of the human-in-the-loop pipeline in CLAUDE.md section 6.
---
Approved implementation plan: $ARGUMENTS

Following `docs/testing-strategy.md` and
`.claude/skills/testing-strategy/SKILL.md`, produce a test plan with:

1. **Unit test cases** (domain layer) — one line per case: scenario and
   expected outcome, including edge cases and failure modes, not just the
   happy path.
2. **Integration test cases** (infrastructure layer) — adapters against real
   (containerized) dependencies.
3. **Contract test cases** — required whenever the change touches a public
   API or a domain event schema; reference the relevant entry in
   `docs/events-catalog.md`.
4. **E2E test cases** — only if this change is part of a critical user
   journey listed in `docs/testing-strategy.md` section 2.4; otherwise state
   explicitly that none are needed for this change.
5. **Event-sourcing-specific cases** — if the touched service is
   `diary-service` or `nutrition-calculation-service`, include a rebuild-from-events
   test case and, if a new consumer is introduced, an idempotency test case.
6. **Coverage expectation** — state which layer(s) this change touches and
   confirm the plan is sufficient to meet the thresholds in
   `docs/testing-strategy.md` (domain >= 90%, application >= 85%,
   infrastructure >= 70%).

Do not write any test code yet. Stop here for human approval before
`/implementation-execution` begins.
