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
  method at all; keep it that way. This rule is about the synchronous
  fallback path specifically -- it does NOT apply to
  `billing_events_consumer.py`'s `HandleEntitlementGranted/RevokedHandler`,
  which is the one sanctioned writer of `entitlement_cache` (approved
  2026-09-08, built 2026-09-11 -- see the next bullet's history).
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
- `billing_events_consumer.py` was deliberately left out of the original
  approved implementation plan's file list, not simply forgotten -- it
  required its own genuine human review, given 2026-09-08 in
  `/plans/nutrition-assistant-service/implementation-plan.md`'s addendum,
  and was built 2026-09-11 per that addendum's 9-item scope (mirroring
  `analytics-service`'s precedent exactly, including widening
  `EntitlementCacheRepositoryPort.set()` to `upsert(user_id, entitled,
  occurred_at)`). It is now live -- do not re-remove it or re-narrow the
  port signature without an equally explicit, separately-reviewed
  decision; this bullet's history stands as the record that adding it was
  reviewed, not skipped.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s):
  `DiaryHistoryRepositoryPort`, `NutritionHistoryRepositoryPort`,
  `AnalyticsSignalsRepositoryPort`, `EntitlementCacheRepositoryPort`,
  `EntitlementCheckPort`, four `Processed*EventsRepositoryPort`s (diary,
  nutrition_calculation, analytics, entitlement),
  `ChatAuditRepositoryPort`, `VectorStorePort`, `ConversationPort`,
  `EmbeddingPort`, `EventPublisherPort`/`OutboxRepositoryPort` (unused
  this pass).
- Adapters: `infrastructure/external/claude_conversation_adapter.py`,
  `infrastructure/external/billing_entitlement_client.py`,
  `infrastructure/vectorstore/qdrant_vector_store_adapter.py`,
  `infrastructure/vectorstore/local_embedding_adapter.py`,
  `infrastructure/persistence/` (ten Postgres repositories),
  `infrastructure/messaging/` (four topic consumers -- diary,
  nutrition_calculation, analytics, billing (`billing_events_consumer.py`,
  added 2026-09-11 per the implementation plan addendum) -- sharing
  `resilient_topic_consumer.py`'s retry/DLQ plumbing).
- Composition root: `infrastructure/composition_root.py`.
- Shared cross-handler helper (not a port, not a command):
  `application/entitlement_check.py`.
- Core orchestration: `application/queries/answer_chat_query.py`.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/fakes.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3). Actual as of 2026-09-08: 98.0% / 100.0% / 87.9%, 164/164
tests passing (excludes `tests/evaluation`, which is a fixed-set RAG
retrieval-quality eval, not a pass/fail coverage-contributing suite).

**2026-09-11 addendum (`entitlement_cache` live writer)**: `tests/unit`
re-run domain 97% / application 100%, 103/103 unit tests passing. The new
integration tests (`test_billing_events_consumer.py`,
`test_migration_0002.py`, extended
`test_postgres_entitlement_cache_repository.py`/
`test_postgres_processed_events_repositories.py`) require Docker
(testcontainers Postgres/RabbitMQ), unavailable in the implementing
sandbox -- not run there, flagged rather than assumed passing; see
README.md's "Testing" section for the full caveat. Run the full suite
including these before merge.
