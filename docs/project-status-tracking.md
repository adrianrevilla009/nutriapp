# Project Status Tracking

## Purpose
With eight domain services, cross-cutting agents, and a strict
plan-approve-implement pipeline, it must always be possible for a new
agent session (or a human returning after time away) to answer, without
re-reading the whole codebase: **what actually exists right now, versus
what is only specified?**

`CLAUDE.md` and the ADRs capture *decisions*. This document specifies how
the project must maintain a separate, lightweight record of *current
state*, kept current as implementation proceeds.

This is a specification of the mechanism. The actual status file/log
described below is created and maintained once implementation begins —
it does not exist yet, consistent with the repository's current
specification-only phase (`README.md`, `CLAUDE.md` section 14).

## What Must Be Tracked

A single status record (`STATUS.md` at the repo root, once created) must
answer, per service:
- **Scaffolded?** — does the service directory exist with its hexagonal
  skeleton (domain/application/infrastructure/tests)?
- **Core domain implemented?** — are the primary entities/use cases for
  that bounded context implemented and tested?
- **Deployed to dev?** — does a working container exist and run in the
  local/dev environment?
- **Deployed to staging/prod?** — per
  `docs/environments-and-promotion.md`.
- **Last significant change** — date and one-line summary, not a full
  changelog (git history already covers that).

At the cross-cutting level, the same record tracks:
- Which Terraform modules exist and against which environment they have
  actually been applied (by a human, per `CLAUDE.md` section 7).
- Which MCP servers are currently connected versus only specified (see
  `docs/mcp-servers.md`).
- Which ADRs are "Proposed" versus "Accepted" versus "Superseded."

## What Must Not Be Tracked Here
- Anything git history or the ADR log already covers in full detail —
  this record is a **summary index**, not a duplicate changelog.
- In-progress implementation detail that belongs in an active
  implementation plan — this record reflects completed, merged state
  only.

## Update Trigger
- `STATUS.md` is updated as part of `/create-pr` (see
  `.claude/commands/create-pr.md`) whenever a merged change moves a
  service from one status to another (e.g. scaffolded -> core domain
  implemented). This keeps the record current without a separate manual
  step a human has to remember to do.
- The `/project-status` command (see
  `.claude/commands/project-status.md`) reads and renders this record
  on demand — it does not maintain a second source of truth.

## Format
- Plain markdown table, one row per service plus a cross-cutting section,
  so it stays diffable in PRs and readable without tooling.
- No automation is assumed beyond what `/create-pr` and `/project-status`
  do explicitly — this stays a simple, human-readable file, not a
  generated dashboard, unless a future ADR decides otherwise.
