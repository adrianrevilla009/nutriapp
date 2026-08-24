---
description: Scaffold a new NutriApp service following the hexagonal architecture layout, and prepare it for isolated work in its own git worktree.
---
Service to create: $ARGUMENTS

1. Confirm the name does not collide with an existing service (identity,
   catalog, core, computation, media, analytics, ai-assistant) or a
   cross-cutting concern.
2. Propose the bounded context definition: what this service owns, and what
   it explicitly does not own (to avoid boundary creep into an existing
   service).
3. Propose whether this service needs full event sourcing, CQRS-read-only, or
   conventional persistence (see ADR-0002 and
   `.claude/skills/cqrs-event-sourcing/SKILL.md`) — this is an architectural
   decision, flag `architecture-agent` for review before proceeding.
4. Propose the directory layout following
   `.claude/skills/hexagonal-architecture/SKILL.md` exactly
   (`domain/`, `application/`, `infrastructure/`, `tests/`).
5. Propose whether this service needs a dedicated Claude Code subagent in
   `.claude/agents/` — create it, following the format of existing domain
   agents, if so.
6. Add the service to `ARCHITECTURE.md`'s service map and to
   `docker-compose.yml` (delegate to `devops-agent` for the compose/Dockerfile
   work).
7. State the worktree command to run manually:
   `claude --worktree <service-name>`. Do not launch the worktree yourself —
   that is executed by the human from their terminal.
8. Stop here for human approval before any file is created.
