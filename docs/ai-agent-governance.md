# AI Agent Governance

This document specifies the governance model for AI involvement in NutriApp
at two distinct layers, which must not be conflated:

1. **Development-time agents** — Claude Code subagents
   (`.claude/agents/*`) that write specification, plans, code, and tests
   for this repository.
2. **Product-time AI** — the LLM/vision features shipped *inside*
   NutriApp itself (`nutrition-assistant-service`, `food-recognition-service`).

Both are already constrained by technical guardrails (`CLAUDE.md` section
7, `.claude/hooks/`). This document specifies the **decision-making and
review policy** around those guardrails — what an agent is and is not
authorized to decide unilaterally, and how those decisions are made
reviewable after the fact.

## 1. Development-Time Agent Authority

### What an agent may decide unilaterally
- Implementation details within an already-approved plan (variable names,
  file organization within the agreed structure, which existing utility
  to reuse).
- Test case design within an already-approved test plan.
- Wording of documentation, commit messages, and PR descriptions.

### What requires explicit human approval before proceeding
(This restates and consolidates `CLAUDE.md` sections 6 and 7 as a
governance policy, not just a technical gate.)
- Any change to service boundaries, event contracts, or the technology
  stack listed in `CLAUDE.md` section 4.
- Any new ADR-worthy decision (`CLAUDE.md` section 9).
- Any change to a **product prompt** (see
  `.claude/skills/prompt-engineering-standards/SKILL.md`) — a prompt
  change alters product behavior and is treated as a behavioral change,
  not a copy edit.
- Any change to which LLM model tier a feature or subagent uses (see
  `.claude/skills/llm-cost-and-model-selection/SKILL.md`), since it has
  direct cost and quality implications.
- Everything already listed as a hard guardrail in `CLAUDE.md` section 7.

### Escalation on ambiguity
If an agent is uncertain whether a decision falls inside or outside its
authority, the default is to **stop and ask**, not to proceed and flag it
afterward. A wrong guess that turns out fine is still a process failure —
the pipeline in `CLAUDE.md` section 6 exists precisely so agents do not
need to guess.

## 2. Product-Time AI Decision Review

Unlike development-time agents (which are supervised interactively),
`nutrition-assistant-service` and `food-recognition-service` make user-facing decisions
autonomously at runtime. Governance here is about **traceability and
review after the fact**, not per-request human approval.

- Every AI-generated response or detection logs enough context to
  reconstruct why it was produced: prompt version, model version, and
  (for RAG) which records were retrieved — per
  `.claude/skills/observability-audit/SKILL.md`.
- A sampling process (frequency to be defined per environment in the
  implementation plan) periodically reviews real production
  outputs against the evaluation-set expectations in
  `.claude/skills/rag-conventions/SKILL.md` and
  `.claude/skills/media-recognition-conventions/SKILL.md`, to catch drift that
  a fixed evaluation set alone would miss.
- Any user-reported incorrect or harmful AI output is logged as an
  incident per `docs/incident-response.md` if it crosses a safety boundary
  (e.g. the medical-advice boundary), and as a normal bug otherwise.

## 3. Boundaries That Are Never Delegated to Any Agent

Regardless of layer, the following are always a human decision:
- Whether a given AI feature ships at all (feature-flag rollout, per
  `.claude/skills/feature-flags/SKILL.md`).
- Any interpretation of ambiguous legal/ethical scope (e.g. whether a new
  data source is acceptable to scrape, whether a new use of user data
  requires new consent) — an agent may research and present options, per
  `CLAUDE.md` section 8, but does not resolve the ambiguity itself.
- Final sign-off on anything reaching `staging`/`prod`, per
  `docs/environments-and-promotion.md`.

## 4. Review Cadence

This document is reviewed whenever a new AI-backed feature is proposed,
and at minimum alongside any ADR that changes agent responsibilities
(`CLAUDE.md` section 5) or the human-in-the-loop pipeline (`CLAUDE.md`
section 6).
