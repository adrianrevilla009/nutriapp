---
description: Turn a raw requirement into a scoped spec and route it to the right domain agent, as the first step of the human-in-the-loop pipeline defined in CLAUDE.md section 6.
---
Requirement: $ARGUMENTS

1. Identify which service/domain owns this requirement (identity, catalog,
   core, computation, media, analytics, ai-assistant) or whether it is
   cross-cutting (architecture, qa, devops, security).
2. Write a short spec: what is being built, why, and explicit acceptance
   criteria.
3. Identify architectural implications: does this touch a port/adapter
   boundary, introduce or consume a domain event, require a migration, or
   cross a service boundary? If so, flag `architecture-agent` for review.
4. Recommend whether to delegate to the owning domain subagent or handle it in
   the main session, and whether this warrants its own git worktree (see
   CLAUDE.md workflow notes).
5. Stop here and present the spec for human approval. Do not proceed to
   `/implementation-plan` automatically.
