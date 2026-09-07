# nutrition-assistant-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/nutrition-assistant-service/`. It does not replace the root
`/CLAUDE.md` (architecture, workflow, guardrails) or
`.claude/agents/nutrition-assistant-agent.md` (bounded context, domain
responsibilities, rules) -- read both first, plus
`.claude/skills/rag-conventions/SKILL.md`,
`.claude/skills/prompt-engineering-standards/SKILL.md`, and
`.claude/skills/llm-cost-and-model-selection/SKILL.md` before touching
`domain/services/prompt_assembler.py`, `domain/services/health_topic_classifier.py`,
or `application/queries/answer_chat_query.py`.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, anthropic, qdrant_client,
  or fastembed.
- **Conventional persistence / event-driven CRUD** (ADR-0002's addendum)
  -- no event-sourced write aggregate. Every structured-history table
  this service owns is a read projection fed by consuming another
  service's events, except `entitlement_cache`/`chat_audit_log`/`outbox`
  (this service's own bookkeeping).
- Structured data is NEVER chunked/embedded as free text -- only the
  curated knowledge base (`knowledge_base/seed/*.md`) is embedded into
  Qdrant. Mixing the two would violate rag-conventions SKILL.md's
  access-control-isolation rule.

## Never do this

- Never let `AnswerChatQueryHandler` derive a `user_id` for any
  repository call from anything other than the authenticated
  `command.user_id` -- never parse `command.query`'s text for a user
  reference. This is the entire structural basis for cross-user
  isolation; see
  `tests/unit/application/test_answer_chat_query.py::TestCrossUserIsolationReleaseBlocking`.
- Never trust the LLM's own response to include the mandatory
  professional-advice disclaimer -- `AnswerChatQueryHandler` must always
  verify/append it in code when `health_topic_classifier.is_health_adjacent`
  flags the query. See
  `tests/unit/application/test_answer_chat_query.py::TestProfessionalAdviceBoundaryReleaseBlocking`.
- Never write a fallback `EntitlementCheckPort` result back into
  `entitlement_cache` -- `application/entitlement_check.py`'s
  `is_user_entitled` has no reference to the cache repository's write
  method at all; keep it that way.
- Never treat the knowledge-base seed content
  (`knowledge_base/seed/*.md`) as production-ready -- every file is
  headed `STATUS: DRAFT — pending human/professional review before
  production use`. Do not remove that header without an actual review.
- Never make a live call to the real Anthropic API, a real Qdrant
  instance's public endpoint, or a real `billing-service` instance in
  this service's own unit/contract test suite -- `httpx.MockTransport`
  fixtures for `ClaudeConversationAdapter`/`BillingEntitlementClient`;
  testcontainers Qdrant only in `tests/integration/`.
- Never bump `ClaudeConversationAdapter`'s model tier or swap the
  embedding model, without re-running `tests/evaluation/fixed_eval_set.py`
  and updating `README.md`'s documented choice + reasoning
  (`llm-cost-and-model-selection` SKILL.md, `prompt-engineering-standards`
  SKILL.md).
- Never add a `billing_events_consumer.py` without first re-reading
  README.md's "Known, flagged gap" #1 and getting this genuinely
  reviewed/approved -- it was deliberately left out of the approved
  implementation plan's file list, not simply forgotten.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s):
  `DiaryHistoryRepositoryPort`, `NutritionHistoryRepositoryPort`,
  `AnalyticsSignalsRepositoryPort`, `EntitlementCacheRepositoryPort`,
  `EntitlementCheckPort`, three `Processed*EventsRepositoryPort`s,
  `ChatAuditRepositoryPort`, `VectorStorePort`, `ConversationPort`,
  `EmbeddingPort`, `EventPublisherPort`/`OutboxRepositoryPort` (unused
  this pass).
- Adapters: `infrastructure/external/claude_conversation_adapter.py`,
  `infrastructure/external/billing_entitlement_client.py`,
  `infrastructure/vectorstore/qdrant_vector_store_adapter.py`,
  `infrastructure/vectorstore/local_embedding_adapter.py`,
  `infrastructure/persistence/` (nine Postgres repositories),
  `infrastructure/messaging/` (three topic consumers sharing
  `resilient_topic_consumer.py`'s retry/DLQ plumbing).
- Composition root: `infrastructure/composition_root.py`.
- Shared cross-handler helper (not a port, not a command):
  `application/entitlement_check.py`.
- Core orchestration: `application/queries/answer_chat_query.py`.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/fakes.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3). Actual as of 2026-09-07: 98.0% / 100.0% / 87.9%, 149/149
tests passing.
