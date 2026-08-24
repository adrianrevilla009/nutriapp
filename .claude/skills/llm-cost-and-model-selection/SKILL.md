---
description: How to choose which Claude model to use per task (Claude Code subagents) and per LLM call (product features like nutrition-assistant-service), and how to keep both within budget. Use when configuring a subagent, writing a product LLM call, or reviewing cost.
---

# LLM Cost & Model Selection

This skill covers two distinct concerns that must not be conflated:
1. **Development-time cost** — which model each Claude Code subagent
   (`.claude/agents/*`) uses while building NutriApp.
2. **Product-time cost** — which model `nutrition-assistant-service` and
   `food-recognition-service` call in production, per user request.

## 1. Development-Time: Claude Code Subagents

- Not every subagent needs the most capable model for every task.
  Model choice per agent must be documented in that agent's own
  definition file (`.claude/agents/{name}.md`), with a stated reason —
  never left as an unstated default.
- General guidance for assigning a tier:
  - **Cross-cutting, high-stakes review** (`architecture-agent`,
    `security-agent`, `reviewer-agent`): highest-capability tier
    available — these gate correctness and safety, cost is secondary.
  - **Domain implementation agents** (`identity-agent`,
    `catalog-agent`, `transaction-agent`, `core-domain-agent`,
    `media-recognition-agent`, `analytics-agent`, `ai-assistant-agent`): mid/high tier,
    scaled to the complexity of the specific task at hand rather than
    fixed permanently — a small, well-scoped change does not need the
    same tier as designing a new bounded context.
  - **Mechanical/repetitive tasks** (`qa-agent` running a known test
    suite, `devops-agent` generating boilerplate CI config from an
    established template, `/create-commit`, `/create-pr`): lowest tier
    that reliably produces correct output.
- A session or task expected to consume unusually large context (e.g. a
  full-repo audit) is flagged before running, so the human can decide
  whether the cost is justified rather than discovering it after the
  fact.

## 2. Product-Time: LLM Calls Inside NutriApp

- Every LLM-backed feature (`nutrition-assistant-service`'s RAG assistant,
  `food-recognition-service`'s recognition calls if LLM-based) must state, in its
  implementation plan, which model tier it targets and why — this is an
  explicit design decision, not an incidental default.
- Prefer the smallest/cheapest model that meets the accuracy bar defined
  in that feature's evaluation set (see
  `.claude/skills/rag-conventions/SKILL.md` and
  `.claude/skills/media-recognition-conventions/SKILL.md`) — capability
  upgrades are justified by a failed evaluation, not by default caution.
- Per-request cost must be estimable before release: token budget per
  call (prompt + expected completion) is documented, and an unexpectedly
  large input (e.g. a very long chat history) must be truncated or
  summarized deterministically rather than sent unbounded to the model.
- Caching (per `.claude/skills/caching-strategy/SKILL.md`) is the first
  lever for reducing LLM cost before reaching for a cheaper model —
  identical or near-identical requests (e.g. repeated general domain
  questions) should not re-invoke the model when a cached answer is
  still valid and clearly not user-specific.

## Budget Visibility
- Per `docs/cost-management.md`, any metered external API — including
  LLM provider usage — must be tagged and trackable per environment
  (dev/staging/prod) and, where feasible, per feature, so a cost spike
  can be attributed to a specific change.
- A feature flag (per `.claude/skills/feature-flags/SKILL.md`) must exist
  for any new LLM-backed feature capable of materially increasing spend,
  so it can be throttled or disabled without a deploy if cost runs away.

## Review
- Model-tier choices (both development-time and product-time) are
  revisited whenever a new model generation becomes available or actual
  usage data shows a mismatch between assigned tier and task complexity —
  this is a periodic review item, not a one-time decision frozen at
  project start.
