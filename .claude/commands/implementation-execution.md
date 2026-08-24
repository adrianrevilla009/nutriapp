---
description: Execute an approved implementation plan and approved test plan, writing tests first (TDD). Stage 6 of the human-in-the-loop pipeline in CLAUDE.md section 6.
---
Approved implementation plan and test plan: $ARGUMENTS

1. Write the tests defined in the approved test plan first (red).
2. Implement the minimum code in the correct layer (domain -> application ->
   infrastructure, per `.claude/skills/hexagonal-architecture/SKILL.md`) to
   make those tests pass (green).
3. Refactor for clarity once green, without changing behavior.
4. Follow every relevant skill for the domain touched (domain-calculation
   calculations, scraping ethics, CQRS/event sourcing, resilience patterns,
   caching, messaging conventions, migrations) as applicable to this change.
5. Do not execute any action listed in CLAUDE.md section 7 (git push,
   destructive migration, bulk scraping, data deletion, hook/permission
   changes) without stopping and asking for explicit human confirmation first
   — this is also enforced by `.claude/hooks/pre-bash-guard.sh`.
6. Update `docs/events-catalog.md` in the same change if a new event or event
   version was introduced.
7. Do not commit or open a pull request as part of this command — that is
   `/create-commit` and `/create-pr`, later gates.

When finished, summarize what was implemented, confirm all planned tests pass
locally, and hand off to `/test-execution` for the full suite run.
