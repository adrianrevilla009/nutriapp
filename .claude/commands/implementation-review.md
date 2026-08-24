---
description: Review a completed implementation against CLAUDE.md and the relevant skills. Stage 8 of the human-in-the-loop pipeline in CLAUDE.md section 6. Should be run by reviewer-agent and/or architecture-agent, not the agent that wrote the code.
---
Change to review: $ARGUMENTS

Review `git diff` for this change against:

1. **Hexagonal boundaries** (ADR-0001,
   `.claude/skills/hexagonal-architecture/SKILL.md`) — any domain-layer import
   of infrastructure code?
2. **CQRS/event sourcing conventions** (ADR-0002,
   `.claude/skills/cqrs-event-sourcing/SKILL.md`), if the touched service uses
   them — event immutability, outbox usage, rebuildable read models.
3. **Service boundaries** (ADR-0003) — no direct cross-service database access.
4. **Messaging conventions** (ADR-0004,
   `.claude/skills/messaging-conventions/SKILL.md`) — naming, idempotency.
5. **Resilience patterns** (`.claude/skills/resilience-patterns/SKILL.md`) —
   present on every new synchronous/external call.
6. **Security** (`docs/security-and-compliance.md`) — no hardcoded secrets, no
   raw SQL interpolation, no sensitive data in logs.
7. **Human-in-the-loop guardrails** (CLAUDE.md section 7) — no destructive
   action executed without a clear approval trail.
8. **Documentation** (`docs/documentation-standards.md`) — was
   `docs/events-catalog.md`, an ADR, or a service `README.md` updated where
   required?

Return a verdict: **APPROVED**, **APPROVED WITH OBSERVATIONS**, or
**BLOCKED**, with specific, actionable findings citing the exact document or
skill each relates to. Do not restate the whole diff.
