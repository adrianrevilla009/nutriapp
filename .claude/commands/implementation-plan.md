---
description: Produce a concrete implementation plan for an approved spec, without writing any code. Stage 2 of the human-in-the-loop pipeline in CLAUDE.md section 6.
---
Approved spec: $ARGUMENTS

Produce a plan with the following sections. Do not write or edit any code as
part of this command.

1. **Scope** — restate what is being built and its acceptance criteria.
2. **Architectural classification** — per `.claude/skills/hexagonal-architecture/SKILL.md`
   and ADR-0002: does this service use event sourcing, CQRS-read-only, or
   conventional persistence? Which layers (domain/application/infrastructure)
   are touched?
3. **Files to create or modify** — concrete paths, grouped by layer.
4. **Ports/adapters affected** — new ports introduced, existing ports reused,
   adapters implementing them.
5. **Domain events** — any event introduced or consumed; note if
   `docs/events-catalog.md` needs a new entry.
6. **Cross-service impact** — does this change what another service consumes
   or calls? If yes, flag `architecture-agent` for review before proceeding.
7. **Resilience/caching/migration needs** — does this require a circuit
   breaker, a new cache key namespace, or a database migration? Reference the
   relevant skill.
8. **Test plan reference** — note that `/test-plan` will define concrete test
   cases next; do not enumerate them here in detail.
9. **Risks and open questions** — anything ambiguous that needs a human
   decision before implementation starts.

Stop here and present the plan for human approval. Do not proceed to
`/test-plan` or `/implementation-execution` automatically.

Once the human approves, persist the plan verbatim to
`/plans/<service-or-initiative>/implementation-plan.md` (create the
directory if it doesn't exist) before moving on — see CLAUDE.md section 6,
"Plan Persistence". If this is a revision of an already-persisted plan,
append a dated addendum rather than overwriting the original approved
text.
