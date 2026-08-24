---
description: Create a new Architecture Decision Record when a change affects the stack, service boundaries, messaging backbone, or testing strategy. Referenced throughout CLAUDE.md section 9.
---
Decision to document: $ARGUMENTS

1. Determine the next ADR number (check `docs/adr/` for the highest existing
   number and increment).
2. Copy `docs/adr/template.md` to `docs/adr/{number}-{short-slug}.md`.
3. Fill in: Context (the forces at play), Decision (stated clearly), Considered
   Alternatives (at least one genuine alternative with its trade-offs), and
   Consequences (positive and negative, plus follow-up actions).
4. Cross-reference the relevant CLAUDE.md section(s) this ADR relates to or
   changes.
5. If this ADR supersedes a previous one, update the superseded ADR's
   **Status** field to `Superseded by ADR-{new-number}` rather than deleting
   it.
6. Flag `architecture-agent` to review the ADR for consistency with existing
   decisions before it is considered final.
7. Stop here for human approval — an ADR is itself a decision that requires
   sign-off, not just documentation of one already made unilaterally by an
   agent.
