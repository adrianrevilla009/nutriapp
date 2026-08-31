---
description: Open a pull request for a committed, reviewed change, with a description auto-generated from the implementation plan and review findings. Stage 12 of the human-in-the-loop pipeline in CLAUDE.md section 6.
---
Committed change: $ARGUMENTS

1. Confirm the change has passed `/implementation-review` and `/test-review`
   with an APPROVED or APPROVED WITH OBSERVATIONS/NOTES verdict — if either
   was BLOCKED, stop and resolve that first.
2. Generate the PR description from:
   - The original spec (from `/plan-feature`).
   - The implementation plan summary.
   - Test coverage results from `/test-execution`.
   - Any observations from `/implementation-review` and `/test-review` that
     the human reviewer should specifically look at.
   - Links to any new/updated ADR or `docs/events-catalog.md` entry.
3. If a GitHub MCP server is connected (see `docs/mcp-servers.md`), use it to
   open the PR directly. Otherwise, print the exact `gh pr create` command
   (or equivalent) for the human to run manually.
4. Update `STATUS.md` (see `docs/project-status-tracking.md`) for the
   service(s) this change touches, reflecting what this change actually
   implements — scaffolded/core-domain/deployed columns and the
   "last significant change" summary (date, PR number once known, one-line
   summary). This step still runs even though the PR isn't merged yet: the
   row is written now, describing the change this PR contains, so the
   record doesn't silently drift the way it has on prior PRs. Include this
   `STATUS.md` update in the same PR (or, if the PR was already opened,
   push a follow-up commit to it) rather than a separate PR, so the record
   and the change it describes land together.
5. Do not merge. Merge approval is a separate, explicit human action per
   CLAUDE.md section 6, step 12, and is never performed by an agent.
