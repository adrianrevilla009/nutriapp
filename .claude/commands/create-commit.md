---
description: Create a conventional commit for an approved, reviewed change. Stage 11 of the human-in-the-loop pipeline in CLAUDE.md section 6. Only runs after explicit human final approval.
---
Approved change: $ARGUMENTS

1. Confirm explicit human final approval was given for this change (per
   CLAUDE.md section 6, step 10) before proceeding — if not confirmed, stop
   and ask instead of committing.
2. Stage only the files belonging to this logical change — never a blanket
   `git add .` if unrelated changes exist in the working tree.
3. Write a Conventional Commits message:
   `<type>(<scope>): <short description>`
   where `<type>` is one of `feat`, `fix`, `refactor`, `test`, `docs`,
   `chore`, `perf`, and `<scope>` is the service or cross-cutting concern
   touched (e.g. `feat(diary-service): add correction event`).
4. Include a commit body summarizing: what changed, which ADR/skill it
   follows if architecturally relevant, and a reference to the events catalog
   entry if a new event was introduced.
5. Do not push. Pushing requires a separate, explicit human confirmation per
   CLAUDE.md section 7, and is out of scope for this command.
