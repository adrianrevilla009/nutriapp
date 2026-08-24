---
description: How system prompts used by nutrition-assistant-service and food-recognition-service must be written, versioned, and tested. Use whenever creating or changing a prompt that is part of the product (not Claude Code's own agent prompts).
---

# Prompt Engineering Standards

This skill governs **product prompts** — the system/instruction prompts
`nutrition-assistant-service` sends to its LLM and any prompt-based configuration of
`food-recognition-service`'s model calls. It is unrelated to `.claude/agents/*`
(those are Claude Code development-time agents, not product prompts).

## Prompts Are Code
- Every product prompt lives in version control as a plain-text/markdown
  file under the owning service (e.g.
  `nutrition-assistant-service/infrastructure/prompts/`), never inline as a string
  literal buried in application logic — this keeps prompts reviewable and
  diffable like any other artifact.
- Every prompt file has a header comment: purpose, the model(s) it is
  designed for, the date/author of the last substantive change, and a
  link to the evaluation set it must pass (see
  `.claude/skills/rag-conventions/SKILL.md` and
  `.claude/skills/media-recognition-conventions/SKILL.md`).

## Versioning
- Prompts are versioned explicitly (e.g. `v3`), not silently overwritten.
  A new version is a new file or a tagged revision, not an in-place edit,
  until the old version is confirmed safe to retire.
- Every LLM call logs which prompt version was used (see
  `.claude/skills/observability-audit/SKILL.md`), so a change in output
  quality can be correlated with a specific prompt version.
- A prompt change is reviewed the same way a code change is: implementation
  plan -> human approval -> evaluation run -> review, per `CLAUDE.md`
  section 6. A prompt is not a "just tweak it" artifact exempt from the
  pipeline.

## Structure & Content Rules
- Instructions are explicit and unambiguous; avoid relying on the model to
  infer unstated constraints (e.g. state the medical-boundary rule
  explicitly in the prompt rather than assuming the model will infer it).
- Any user-supplied content injected into a prompt (user notes, chat
  messages) is treated as untrusted input for prompt-injection purposes —
  the prompt must be structured (e.g. clear delimiters, explicit
  instruction to treat injected content as data, not instructions) to
  resist a user trying to override system behavior through their own
  input.
- Prompts must not encode secrets, internal infrastructure details, or
  anything that would be sensitive if leaked through a model output.

## Testing Prompts (regression prevention)
- Every prompt has an associated fixed evaluation set (see the RAG and
  vision skills) run before any change to that prompt is accepted.
- Golden/expected outputs are reviewed for drift on every model-version
  upgrade from the LLM provider, not just on prompt changes — a provider
  model update can change behavior even with an identical prompt.

## Model & Cost Awareness
- Prompt length and structure choices should be made with
  `.claude/skills/llm-cost-and-model-selection/SKILL.md` in mind — a
  verbose prompt repeated on every call has a direct, recurring cost.
