# nutrition-assistant-service

RAG-grounded conversational assistant over the user's own diary/nutrition/
analytics history (CLAUDE.md section 2.2,
`.claude/agents/nutrition-assistant-agent.md`). The first service in this
system to use Qdrant, and the second (after `food-recognition-service`) to
call an LLM provider.

## Bounded context

See `.claude/agents/nutrition-assistant-agent.md`,
`.claude/skills/rag-conventions/SKILL.md`, and
`/plans/nutrition-assistant-service/implementation-plan.md` /
`/plans/nutrition-assistant-service/test-plan.md`.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001).
**Conventional persistence / event-driven CRUD** (ADR-0002's addendum) --
no event-sourced write aggregate. This service's own state (structured
history projections, entitlement cache, chat audit log) is stored
conventionally; it consumes three upstream services' events and folds
them into denormalized Postgres read tables. It publishes no domain event
of its own this pass.

Retrieval/prompt-assembly orchestration lives entirely in
`application/queries/answer_chat_query.py` (zero framework/HTTP/SDK code)
orchestrating `VectorStorePort`/`ConversationPort`/`EmbeddingPort`/the
three structured-history ports, per the agent doc's non-negotiable
constraint.

## Grounding model

Structured data (diary entries, nutrition recomputations/targets,
analytics signals) is retrieved as structured records and formatted
deterministically into the prompt -- **never** chunked/embedded as free
text (`rag-conventions/SKILL.md`). Qdrant holds ONLY the curated,
non-personalized general-nutrition knowledge base (one collection,
`nutrition_assistant_knowledge_base`) -- no per-user content is ever
embedded or stored in Qdrant this pass.

## Consumed events (v1)

- `FoodEntryLogged`/`FoodEntryCorrected`/`FoodEntryDeleted`,
  `WaterIntakeLogged`/`WaterIntakeRemoved` (`diary-service`) --
  `diary_events_consumer.py`, one idempotency ledger
  (`processed_diary_events`). Projects `food_entry_history`/`water_intake_history`.
- `NutritionValueRecomputed`/`NutritionTargetUpdated`
  (`nutrition-calculation-service`) --
  `nutrition_calculation_events_consumer.py`. Projects
  `nutrition_value_history`/`nutrition_target_history`.
- `NutrientDeficiencyDetected` (`analytics-service`) --
  `analytics_events_consumer.py`. Projects `analytics_signal_history`; the
  event's `disclaimer` field is stored and surfaced VERBATIM in any chat
  response referencing it, never re-worded.
- `EntitlementGranted`/`EntitlementRevoked` (`billing-service`) --
  `billing_events_consumer.py`. FOURTH real consumer of these two events
  (after `recipe-service`, `social-service`, `analytics-service`),
  implementing this service's side of the
  `ProUpgradeEntitlementPropagation` saga's fan-out. Own idempotency
  ledger (`processed_entitlement_events`, independent of the other three
  consumers' ledgers). Only flips `entitlement_cache`'s cached flag --
  never touches `diary_history`/`nutrition_history`/`analytics_signals`
  (non-destructive, structurally guarded, see
  `application/commands/handle_entitlement_revoked.py`'s constructor
  signature). See implementation plan addendum, 2026-09-08.

**Deferred this pass**: `FastingWindowStarted/Ended`,
`MealPlanned/Updated/Removed` (diary-service); ALL `profile-service`
events (`WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated` --
AES-256-GCM ciphertext under ADR-0023's per-service key ownership; a real
ADR-worthy decision, not made here); `RecipeCreated/Updated/Published/Unpublished`
(recipe-service).

**Known, flagged gap #1 -- RESOLVED (2026-09-11)**: this service now
consumes `billing-service`'s `EntitlementGranted`/`EntitlementRevoked` via
`billing_events_consumer.py` (the FOURTH real consumer, after
`recipe-service`/`social-service`/`analytics-service`), per the
implementation plan's addendum, 2026-09-08 (`entitlement_cache` live
writer approved, mirroring `analytics-service`'s precedent exactly).
`EntitlementCacheRepositoryPort.set(user_id, entitled)` was widened to
`upsert(user_id, entitled, occurred_at)` so the cache row preserves the
event's own `granted_at`/`revoked_at` timestamp rather than only the
cache-write time. Every chat request is still cache-first
(`application/entitlement_check.is_user_entitled`) and still falls back
to the synchronous `EntitlementCheckPort` call on a genuine cache miss
(e.g. a lagging consumer, or a user who upgraded before this service ever
saw the event) -- that fallback result is still never written back into
`entitlement_cache` (see CLAUDE.md's "Never do this" section, unchanged).

## Published events

None this pass. No other service is documented as consuming anything
from this service anywhere in `docs/events-catalog.md`.
`EventPublisherPort`/`OutboxRepositoryPort`/`OutboxRelayWorker` are
scaffolded for architectural symmetry with every other event-driven-CRUD
service in this repo, but not started as a background task from
`composition_root.py` -- there is no live publisher to relay for.

## Public API

JWT-authenticated (ADR-0022) throughout. `user_id` comes ONLY from the
verified JWT (`get_authenticated_user_id`) -- never from the request
body -- the structural basis for cross-user isolation.

- `POST /api/v1/chat` -- **Pro-gated**. Accepts `{"query": "...",
  "chat_history": [{"role": "user"|"assistant", "content": "..."}]}`.
  Returns `{"response", "had_sufficient_context", "disclaimer_included",
  "retrieved_record_count"}`.

**Entitlement-rejection status code**: `402 Payment Required`, code
`NOT_ENTITLED` -- reuses the repo-wide convention verbatim.

## Professional-advice boundary (CLAUDE.md section 8)

`domain/services/health_topic_classifier.py` is a PURE, rule-based
(keyword/pattern) first cut for flagging a query as health-adjacent --
deliberately NOT an LLM call, so the boundary does not depend on the
model's own judgement. `application/queries/answer_chat_query.py`
structurally enforces the disclaimer: if a flagged query's LLM response
does not literally contain the disclaimer text
(`domain/value_objects/disclaimer_flag.py`'s `DEFAULT_DISCLAIMER_TEXT`),
this handler appends it before returning -- verified by
`tests/unit/application/test_answer_chat_query.py::TestProfessionalAdviceBoundaryReleaseBlocking`
using a fake LLM response that omits the disclaimer entirely.

**This rule-based classifier has real precision/recall limits** (see
`tests/unit/domain/test_health_topic_classifier.py::TestKnownPrecisionRecallGap`,
which documents actual known false negatives) -- flagged for
`security-agent`/`architecture-agent` review before staging/prod, same
posture as `analytics-service`'s deficiency-threshold sign-off.

A 2026-09-08 security review closed three concrete false-negative gaps
in the pattern set: indirect causal/symptom phrasing that avoids the
literal string "caused by" ("could low iron be why I'm so tired"),
pregnancy/breastfeeding/infant-nutrition questions (previously zero
coverage), and restrictive-eating phrasing that avoids the word
"disorder" ("I've been skipping meals and barely eating, is that
okay"). See `TestIndirectCausalPhrasingCoverage`,
`TestPregnancyBreastfeedingInfantCoverage`, and
`TestRestrictiveEatingWithoutDisorderWordCoverage` in the same test
file. `TestKnownPrecisionRecallGap`'s remaining two cases ("I've been
really tired lately", "how am I doing") are still open -- vague
tiredness/wellbeing statements with no symptom, causation, or
restrictive-eating keyword at all resist this rule-based approach
without a much higher false-positive rate; they are not closed by this
pass. Not a
solved problem; a first cut.

## Cross-user isolation

Every structured-history repository call in `answer_chat_query.py` is
parameterized on the authenticated `user_id` only -- this handler never
parses `command.query`'s text looking for a user reference, so it is
structurally incapable of retrieving another user's data regardless of
what the query says. Verified by
`tests/unit/application/test_answer_chat_query.py::TestCrossUserIsolationReleaseBlocking`
(direct requests, indirect references, and prompt-injection-style
attempts to override retrieval scope -- all fail to leak a seeded
second-user marker string).

## Embedding model (implementation plan section 9, resolution 1)

Self-hosted, open-source `sentence-transformers/all-MiniLM-L6-v2`
(**Apache-2.0 license**, 384 dimensions), run in-process via `fastembed`
(ONNX Runtime backend -- lighter footprint than a torch-based
sentence-transformers install). NO external vendor call, NO new DPA
entry. See `infrastructure/vectorstore/local_embedding_adapter.py` and
`docs/vendor-risk-register.md`'s new "Embedding model" entry.

## LLM model (implementation plan section 9, resolution 5)

Starts on **Claude Haiku 4.5** (`claude-haiku-4-5`,
`NUTRITION_ASSISTANT_SERVICE_CONVERSATION_MODEL`, configurable) -- the
smallest/cheapest tier expected to meet the accuracy bar, mirroring
`food-recognition-service`'s `ClaudeVisionAdapter` precedent exactly.
Escalating tiers is a decision to be justified against
`tests/evaluation/fixed_eval_set.py`'s manual/on-demand generation-quality
run (see "Testing" below), not a silent config bump.

## Knowledge base (implementation plan section 9, resolution 2)

`knowledge_base/seed/*.md` -- 9 small, hand-authored, generic,
non-personalized nutrition fact/definition entries (what is a calorie,
macronutrients, fiber, protein, carbohydrates, dietary fat,
micronutrients, hydration, a balanced meal). Every file is headed
`STATUS: DRAFT — pending human/professional review before production
use` -- this content is NOT to be treated as production-ready. Seeded via
`infrastructure/vectorstore/seed_knowledge_base.py` (not a live event
consumer -- run manually/at deploy time). Chunking: one file = one
semantic-unit chunk (see that script's own docstring for the reasoning).

## Resilience

| Integration | Circuit name | fail_max | reset_timeout |
|---|---|---|---|
| Claude Messages API (generation) | `claude_conversation` | 5 | 30s |
| Qdrant (search) | `qdrant_search` | 5 | 30s |
| `billing-service` entitlement check (cache-miss fallback only) | `billing_entitlement_check` | 5 | 30s |

No circuit breaker on the embedding step -- `LocalEmbeddingAdapter` is
local/self-hosted, no network call (implementation plan section 7).

**Fallback behavior**: Qdrant unavailable -> answers from structured data
only, with an explicit note. LLM unavailable -> typed
`AssistantUnavailableError` (`503`, code `ASSISTANT_UNAVAILABLE`), never a
garbage/empty answer presented as real.

## Testing

`docs/testing-strategy.md`,
`/plans/nutrition-assistant-service/test-plan.md`. Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.
Actual (2026-09-07): domain 98.0%, application 100.0%, infrastructure
87.9%, 149/149 tests passing (`ruff check`/`ruff format --check`/
`mypy --strict` all clean).

**`entitlement_cache` live writer addendum (2026-09-11)**: `tests/unit`
re-run after adding `billing_events_consumer.py` +
`HandleEntitlementGranted/RevokedHandler` + the widened
`entitlement_cache_repository_port.py`: 103/103 unit tests passing,
domain 97% / application 100% (`ruff check`/`ruff format --check`/
`mypy --strict domain application infrastructure` all clean). The new
`test_billing_events_consumer.py`, `test_migration_0002.py`, and the
extended `test_postgres_entitlement_cache_repository.py`/
`test_postgres_processed_events_repositories.py` integration tests were
**not executed in the implementing sandbox** -- no Docker daemon was
reachable there (neither a native Linux daemon nor the Windows-host
Docker Desktop via WSL interop), a pre-existing environment constraint
that blocks every testcontainers-based suite in this service, not
something introduced by this change. They collect cleanly under
`pytest --collect-only` (import/fixture wiring verified) and mirror
already-CI-green precedent (`test_diary_events_consumer.py`,
`test_migration_0001.py`) closely enough that a green result is expected,
but this is flagged explicitly rather than claimed as a verified number
-- run `uv run pytest tests/integration tests/contract -q` plus the
coverage-gate command in a Docker-capable environment (this repo's CI)
before merge.

**Both RELEASE-BLOCKING test categories pass**: cross-user isolation
(`TestCrossUserIsolationReleaseBlocking`, 4 cases) and the
professional-advice boundary (`TestProfessionalAdviceBoundaryReleaseBlocking`,
7 cases across 6 parametrized health-adjacent probes + 1 non-duplication
case).

**Evaluation harness execution-mode split** (test plan section 8): the
two release-blocking categories are fully automated in CI (fake
`ConversationPort`, no live LLM call). The three answer-*quality*
categories (grounded-factual, out-of-scope, ambiguous) genuinely need a
real LLM call to judge and are NOT run against the live Anthropic API in
CI, per `ClaudeVisionAdapter`'s "never a live API call in CI" precedent --
run manually/on-demand before a release and on any prompt/model change.
This means this plan does not produce a validated answer-quality number,
same caveat `food-recognition-service`'s plan carried for its own vision
pipeline.

**Deviation from the persisted test plan, flagged honestly**: of the four
message consumers, `diary_events_consumer.py` and (as of the 2026-09-11
addendum) `billing_events_consumer.py` have a full, real-AMQP
(testcontainers RabbitMQ) integration test
(`tests/integration/infrastructure/test_diary_events_consumer.py`,
`test_billing_events_consumer.py`, mirroring `analytics-service`'s
identical precedent for each). The other two
(`nutrition_calculation_events_consumer.py`,
`analytics_events_consumer.py`) are tested at the dispatch-function level
against a real Postgres, bypassing a real RabbitMQ channel -- since they
share the exact same `ResilientTopicConsumer` base class already proven
end-to-end by the diary/billing consumers' tests, and their own dispatch
logic is independently unit-tested at the application layer. This was a
deliberate, time-scoped choice made during implementation, not part of
the original test plan's own description.

## Known gaps (flagged, not silently worked around)

1. ~~`entitlement_cache` has no live writer this pass~~ -- RESOLVED
   2026-09-11, see "Consumed events" above.
2. Qdrant client (`qdrant-client==1.19.0`) is one minor version ahead of
   the server image pinned in `infra/k8s/charts/qdrant/values.yaml`
   (`qdrant/qdrant:v1.11.3`) -- surfaced as a `UserWarning` during this
   plan's own test run, harmless today but should be reconciled (bump the
   server image tag, or pin the client older) before this reaches a real
   environment.
3. The system-instruction prompt text is duplicated between
   `domain/services/prompt_assembler.py`'s `_SYSTEM_INSTRUCTIONS` Python
   constant (the actual runtime source, since the domain layer must stay
   I/O-free) and `infrastructure/prompts/system_prompt_v1.md` (the
   versioned, human-reviewable artifact `prompt-engineering-standards`
   SKILL.md calls for) -- kept in sync manually, flagged in both files for
   a cleaner resolution later.
4. `LocalEmbeddingAdapter`'s model weights are downloaded from Hugging
   Face Hub on first use, not pre-baked into the Docker image this pass
   (`Dockerfile`'s own comment) -- first request after a fresh pod start
   pays a one-time download+load cost, and prod pods need egress to
   `huggingface.co`.
5. No Terraform footprint exists anywhere in this repo for RabbitMQ
   itself (a pre-existing gap this plan's own `infra/terraform/modules/qdrant/`
   does not attempt to fix, flagged for `architecture-agent`).
