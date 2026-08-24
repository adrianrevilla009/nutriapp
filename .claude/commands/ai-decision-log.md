---
description: Record a non-trivial decision made by an agent during a session, for traceability under docs/ai-agent-governance.md. This is a lightweight decision log, not a substitute for an ADR.
---

Decision to record: $ARGUMENTS

1. Determine whether this decision is actually ADR-worthy per `CLAUDE.md`
   section 9 (changes the stack, service boundaries, messaging backbone,
   or testing strategy). If so, stop and use `/adr` instead — this
   command is for smaller decisions worth tracing but not worth a full
   ADR (e.g. a specific chunking parameter chosen for
   `.claude/skills/rag-conventions/SKILL.md`, a confidence threshold
   chosen for `.claude/skills/media-recognition-conventions/SKILL.md`, a
   model-tier assignment for a subagent).
2. Append an entry to `docs/adr/decision-log.md` (create it from scratch
   with a one-line header if it does not yet exist) with:
   - Date.
   - Which agent or session made the decision.
   - What was decided and the concrete alternative(s) considered.
   - Why (one or two sentences — this is a log, not a full ADR write-up).
   - Link to the relevant skill/doc/service this decision affects.
3. This log entry does not require human approval to be written (it is a
   record of a decision already made within already-approved authority,
   per `docs/ai-agent-governance.md` section 1), but any decision that
   turns out to have exceeded the agent's authority is flagged for human
   review immediately, not just logged after the fact.
4. Do not use this command to retroactively justify a decision that
   should have gone through `/adr` or through explicit human approval —
   if in doubt, escalate per `docs/ai-agent-governance.md` section 1
   rather than logging it here.
