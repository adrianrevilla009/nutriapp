---
description: Render a summary of the project's actual current state (what is implemented vs. only specified), per docs/project-status-tracking.md. Use at the start of a new session or before planning new work.
---

1. Read `STATUS.md` at the repo root. If it does not exist yet, state
   clearly that the project is still in the specification-only phase
   (per `README.md` and `CLAUDE.md` section 14) and that no status
   record exists to summarize — do not fabricate status for services
   that have not been scaffolded.
2. If `STATUS.md` exists, summarize:
   - Per service: scaffolded / core domain implemented / deployed to
     dev / deployed to staging-prod, and the date of last significant
     change.
   - Cross-cutting: which Terraform modules have actually been applied
     (by a human) and to which environment; which MCP servers from
     `docs/mcp-servers.md` are currently connected versus only
     specified; which ADRs are Proposed vs. Accepted vs. Superseded.
3. Flag any inconsistency noticed between `STATUS.md` and what actually
   exists in the repo (e.g. a service marked "scaffolded" with no
   directory present) rather than silently trusting the file — this
   command reports state, it does not blindly repeat a stale record.
4. Do not modify `STATUS.md` as part of this command — updates happen
   only via `/create-pr`, per `docs/project-status-tracking.md`.
