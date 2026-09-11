# Implementation Plan — `nutrition-assistant-service`

**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-07, by adrianrg1996@gmail.com.

**Related:** ADR-0001 (hexagonal), ADR-0002 + its addendum (conventional persistence / event-driven CRUD, no event sourcing), ADR-0015 (billing/entitlements), CLAUDE.md §2.2/§2.5/§8/§13, `.claude/agents/nutrition-assistant-agent.md`, `.claude/skills/rag-conventions/SKILL.md`, `.claude/skills/prompt-engineering-standards/SKILL.md`, `.claude/skills/llm-cost-and-model-selection/SKILL.md`, `docs/events-catalog.md`, `docs/api-catalog.md`, `docs/product-requirements.md` (feature 19), `docs/domain-glossary-and-context-map.md`, `docs/vendor-risk-register.md`, `docs/mcp-servers.md` §5, `ARCHITECTURE.md`. Structural precedent: `/plans/analytics-service/implementation-plan.md` (scaffolding/CI/Terraform/Helm), `services/food-recognition-service/infrastructure/external/claude_vision_adapter.py` (LLM-calling adapter resilience), `services/recipe-service`/`services/social-service`'s entitlement-check pattern.

This is the last unbuilt bounded context in the system — every other service (13 of 14) is already implemented and merged to `main`. It is also the first service to use Qdrant and the second (after `food-recognition-service`) to call an LLM provider.

---

## 1. Scope

Build `nutrition-assistant-service` end-to-end (domain → application → infrastructure → tests) plus its Terraform/Helm/CI wiring.

**What "grounded in the user's own diary/profile data" means concretely, and how data gets into Qdrant:**

Per `rag-conventions/SKILL.md`, the user's structured history (diary entries, computed nutrition values, targets, trend/deficiency signals) is retrieved as structured records and deterministically formatted into the prompt — **not** chunked/embedded as free text. Qdrant is reserved for unstructured content: a curated, versioned general-nutrition knowledge base (see resolution 2 below). No user-specific unstructured content exists anywhere in the codebase today, so this pass's Qdrant usage is a thin, provably-rebuildable pipeline seeded with a small hand-authored corpus, not a large unstructured corpus that doesn't exist yet.

**Indexing pipeline**: three idempotent event consumers (`diary_events_consumer.py`, `nutrition_calculation_events_consumer.py`, `analytics_events_consumer.py`) each write/update exactly the rows touched by the single event received — no scheduled full-history reprocessing anywhere in this plan. The curated knowledge-base documents are chunked once (semantic-unit chunking, one tip/fact per chunk), embedded, and upserted into Qdrant by content ID — idempotent on re-run.

**Retrieval/prompt assembly**: on a chat request, the application layer (a) reads the requesting user's own structured history for a bounded recent window, scoped on `user_id` from the authenticated JWT only — never client input, never another user's data, (b) does a Qdrant similarity search scoped to the general-knowledge collection only, and (c) assembles both into a single deterministic, versioned prompt template keeping "what your data shows" and "general guidance" in clearly separate, labeled sections.

**Acceptance criteria:**
1. Three consumers idempotently project events into local structured history tables; never double-counts on redelivery; never reprocesses full history for one new event.
2. `POST /api/v1/chat` (flips `docs/api-catalog.md`'s existing `planned` row to `active`) — **Pro-gated**, cache-first entitlement check against `billing-service`, structurally identical to `recipe-service`'s/`social-service`'s pattern.
3. Every response touching a health-adjacent topic carries a visible "not a medical diagnosis, consult a qualified professional" disclaimer (CLAUDE.md §8), enforced structurally — mirroring `analytics-service`'s `NutrientDeficiencyDetected.disclaimer` field precedent.
4. If retrieved context is insufficient, the response says so explicitly rather than generalizing from the model's training knowledge.
5. Cross-user isolation is a hard boundary: every retrieval query is parameterized on the authenticated `user_id` only; a contract/unit test attempts to retrieve another user's data and asserts it never appears in the assembled prompt or response.
6. A fixed evaluation set (grounded factual, out-of-scope, ambiguous, adversarial cross-user-isolation, professional-advice-boundary probes) exists and passes.
7. Coverage: domain ≥90%, application ≥85%, infrastructure ≥70%.

**Explicitly deferred**: `FastingWindowStarted/Ended`, `MealPlanned/Updated/Removed` (diary-service); all `profile-service` events (ciphertext, see resolution below); `recipe-service` events; persisted multi-turn conversation history beyond a single request's supplied history; a large curated knowledge-base corpus; `bff-service` chat UI wiring.

---

## 2. Architectural classification

Conventional persistence / event-driven CRUD per ADR-0002's addendum — no event-sourced write aggregate. Publishes no domain event of its own this pass (no other service is documented as consuming anything from this service). Pure consumer of three upstream services' events. The Qdrant-held knowledge-base collection is a CQRS-style read model — rebuildable by re-running the seed job against version-controlled source files, never an unrecoverable source of truth. Retrieval/prompt-assembly orchestration lives entirely in the application layer, zero framework/HTTP/SDK-specific code, per hexagonal-architecture conventions.

---

## 3. Files to create or modify

```
services/nutrition-assistant-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_nutrition_assistant_tables.py
      # diary_history, nutrition_history, analytics_signals, entitlement_cache,
      # processed_diary_events, processed_nutrition_calculation_events,
      # processed_analytics_events, chat_audit_log, outbox
  domain/
    value_objects/    # retrieved_record.py, grounded_context.py, chat_message.py,
                       # disclaimer_flag.py, retrieval_gap.py
    services/          # prompt_assembler.py (pure), health_topic_classifier.py
                       # (pure, rule-based first cut)
    ports/             # diary_history_repository_port.py, nutrition_history_repository_port.py,
                       # analytics_signals_repository_port.py, entitlement_cache_repository_port.py,
                       # entitlement_check_port.py, processed_*_events_repository_port.py (x3),
                       # chat_audit_repository_port.py, vector_store_port.py, conversation_port.py,
                       # embedding_port.py, event_publisher_port.py, outbox_repository_port.py
  application/
    commands/          # handle_food_entry_logged.py, handle_food_entry_corrected.py,
                       # handle_food_entry_deleted.py, handle_water_intake_logged.py,
                       # handle_water_intake_removed.py, handle_nutrition_value_recomputed.py,
                       # handle_nutrition_target_updated.py, handle_nutrient_deficiency_detected.py
    queries/           # answer_chat_query.py
    dto/, entitlement_check.py, errors.py
  infrastructure/
    http/routes/       # chat_routes.py, health.py
    http/schemas/, dependencies.py, error_mapping.py
    external/          # billing_entitlement_client.py, claude_conversation_adapter.py
    persistence/       # models.py + one repository per port above
    messaging/         # diary_events_consumer.py, nutrition_calculation_events_consumer.py,
                       # analytics_events_consumer.py, outbox_relay_worker.py
    vectorstore/        # qdrant_vector_store_adapter.py, qdrant_collection_schema.py,
                       # local_embedding_adapter.py (self-hosted, resolution 1 below)
    prompts/            # system_prompt_v1.md
    composition_root.py, main.py
  knowledge_base/
    seed/               # small, hand-authored, dated general-nutrition corpus
                       # (resolution 2 below), infrastructure/vectorstore/seed_knowledge_base.py
  tests/
    unit/domain/, unit/application/, integration/infrastructure/,
    contract/http/, contract/events/, evaluation/fixed_eval_set.py

infra/terraform/environments/dev/nutrition-assistant-service.tf
infra/terraform/modules/qdrant/               # new module, first Qdrant footprint
infra/k8s/charts/nutrition-assistant-service/  # mirrors analytics-service's chart
infra/k8s/charts/qdrant/                       # new chart, self-hosted per CLAUDE.md §2.5
.github/workflows/nutrition-assistant-service-ci.yml

docker-compose.yml, docs/api-catalog.md, docs/events-catalog.md,
docs/domain-glossary-and-context-map.md, docs/vendor-risk-register.md, ARCHITECTURE.md
```

---

## 4. Ports/adapters affected

New ports, all local to this service: `VectorStorePort` (→ `QdrantVectorStoreAdapter`), `ConversationPort` (→ `ClaudeConversationAdapter`, structured on `food-recognition-service`'s `ClaudeVisionAdapter` precedent — own circuit breaker, retry, timeouts, bulkhead), `EmbeddingPort` (→ `LocalEmbeddingAdapter`, self-hosted per resolution 1, no external vendor call), `DiaryHistoryRepositoryPort`, `NutritionHistoryRepositoryPort`, `AnalyticsSignalsRepositoryPort`, three `Processed*EventsRepositoryPort`s, `EntitlementCacheRepositoryPort`, `EntitlementCheckPort` (→ `billing-service`'s existing endpoint, no change there), `ChatAuditRepositoryPort`, `EventPublisherPort`/`OutboxRepositoryPort` (scaffolded for symmetry, unused this pass).

---

## 5. Domain events

**Consumed**: `FoodEntryLogged`, `FoodEntryCorrected`, `FoodEntryDeleted`, `WaterIntakeLogged`, `WaterIntakeRemoved` (diary-service); `NutritionValueRecomputed`, `NutritionTargetUpdated` (nutrition-calculation-service); `NutrientDeficiencyDetected` (analytics-service, its `disclaimer` field projected as-is and surfaced verbatim, never re-worded). All already documented in `docs/events-catalog.md` with this service pre-listed as a not-yet-live consumer — flipping to live, no upstream code change.

**Published**: none this pass. No other service names this service as a producer anywhere.

---

## 6. Cross-service impact

No code change to `diary-service`, `nutrition-calculation-service`, `analytics-service`, or `billing-service`. No `bff-service` change (chat UI wiring deferred). `docs/api-catalog.md`'s `/api/v1/chat` flips `planned` → `active`.

This is the first plan to introduce new shared infrastructure (Qdrant) rather than just a new per-service database. Proceeding with resolution 3 below (shared platform-level instance). `architecture-agent` review recommended once implemented, on: the Qdrant topology choice, the `VectorStorePort`/`EmbeddingPort` design, and whether the rule-based health-topic classifier is an acceptable enforcement mechanism given CLAUDE.md §8's zero-tolerance framing (flagged, not resolved, in resolution 4 below). `security-agent` review recommended on cross-user retrieval isolation and the knowledge-base content itself before any production use.

---

## 7. Resilience/caching/migration needs

Circuit breaker `claude_conversation` (own instance, mirrors `claude_vision`'s `fail_max=5`/`reset_timeout=30s` starting default). No `embedding` circuit breaker needed — local/self-hosted, no network call to an external vendor (resolution 1). Explicit fallback: if Qdrant is unavailable, the assistant still answers from structured data only, with an explicit note; if the LLM provider is unavailable, a typed "assistant temporarily unavailable" response, never a stale cached answer presented as fresh. Caching: a Redis cache-aside layer for non-user-specific repeated questions is a should-build-if-time-allows item, not blocking, given the thin knowledge base this pass. One initial additive Alembic migration, no destructive changes. Exactly one Qdrant collection this pass (the curated knowledge base) — a future per-user-content collection is a reserved seam, not implemented. A feature flag gates the chat endpoint's LLM call (cost kill-switch, per `llm-cost-and-model-selection/SKILL.md`). Per-request token budget documented once the model tier is chosen (resolution 5); long chat history is truncated/summarized deterministically, never sent unbounded.

---

## 8. Test plan reference

`/test-plan` defines concrete cases next. Must include at minimum: the incremental-indexing test (one new event never triggers full-history reprocessing), the fixed retrieval-quality evaluation set, the cross-user-isolation adversarial test, and the professional-advice-boundary redirect test — the latter two release-blocking.

---

## 9. Risks and open questions — resolved at approval time (2026-09-07)

1. **Embedding provider — RESOLVED: self-hosted, open-source model.** No new third-party vendor, no new DPA entry in `docs/vendor-risk-register.md`. `LocalEmbeddingAdapter` runs a small, well-established open-source sentence-embedding model in-process or as a lightweight in-cluster sidecar (the implementing agent selects a specific well-established model, e.g. an MiniLM-class sentence-transformer, and documents the exact choice + its license in the service's `README.md`). No external network call for embeddings.
2. **Knowledge-base content — RESOLVED: a small hand-authored draft seed, explicitly marked pending human review.** The implementing agent drafts a handful (roughly 5-10) of short, generic, non-controversial, non-personalized nutrition fact/definition entries (e.g. "what is a calorie," "what are macronutrients," "what is fiber and why does it matter") — general consensus knowledge, no specific numeric dosage/intake recommendations, no claims that could read as personalized medical advice. Every seed file carries a header marking it `STATUS: DRAFT — pending human/professional review before production use`, consistent with `rag-conventions/SKILL.md`'s "reviewed and dated" requirement. This unblocks building and testing the full indexing pipeline now; the content itself is not to be treated as production-ready until explicitly reviewed.
3. **Qdrant deployment topology — RESOLVED: shared platform-level instance.** One Qdrant instance provisioned in `infra/terraform/modules/qdrant/` and `infra/k8s/charts/qdrant/`, since only one service uses it under the current spec — a per-service dedicated instance has no isolation benefit yet. Revisit if a second Qdrant consumer is ever added.
4. **Health-topic-classification enforcement — PROCEED with the rule-based first cut, flagged for review, not resolved as final.** A keyword/pattern-based classifier is a structural guard for the mandatory disclaimer, deliberately not relying on the LLM's own judgment alone. Its precision/recall limits are a real product risk given CLAUDE.md §8's zero-tolerance framing — explicit `security-agent`/`architecture-agent` review required before staging/prod, same posture as `analytics-service`'s deficiency-threshold sign-off. Build it now; do not treat it as a solved problem.
5. **LLM model tier — PROCEED with the cheapest/smallest tier as the starting default, revisit against the evaluation set.** Mirrors `food-recognition-service`'s precedent (start cheap, escalate only on a failed evaluation). The implementing agent documents the exact model chosen and the reasoning in the service's `README.md`, and this must be validated against acceptance criterion 6's fixed evaluation set before being considered adequate — if the evaluation set fails at this tier, escalate and re-run, don't ship a failing eval.
6. **Conversation persistence scope — PROCEED as scoped (no `conversations`/`messages` table this pass).** `chat_audit_log` remains write-only, for traceability (which retrieved records backed each response), not a queryable resume feature. A real resumable-chat product decision is deferred, flagged rather than silently built or omitted.
7. **`profile-service` grounding — stays deferred, structurally, not just by scope choice.** `WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated` are AES-256-GCM ciphertext under ADR-0023's per-service key ownership. A future pass needing this would require either a synchronous reveal-call to `profile-service` (mirroring `nutrition-calculation-service`'s existing consumer of `/internal/v1/profile/{user_id}/reveal-metrics`) or a new key-sharing arrangement — a real ADR-worthy decision, not made here.

---

## Addendum — 2026-09-08, by adrianrg1996@gmail.com: `entitlement_cache` live writer approved

`README.md`'s "Known, flagged gap" #1 and `services/nutrition-assistant-service/CLAUDE.md`'s corresponding "Never do this" rule required genuine human review before adding a `billing_events_consumer.py` — this addendum is that review, given directly by the human, not inferred from an agent's task description. The implementing agent was correct to hold the gate and ask rather than proceed on a task brief alone.

**Approved to proceed**: build `billing_events_consumer.py` + `handle_entitlement_granted.py`/`handle_entitlement_revoked.py`, mirroring `analytics-service`'s precedent exactly, per the 9-item plan the agent proposed in its research report (new `processed_entitlement_events_repository_port.py` + Postgres repository + additive migration `0002`, idempotent consumer on `ResilientTopicConsumer`, wired into `composition_root.py`, `docs/events-catalog.md` updated to list `nutrition-assistant-service` as a fourth real consumer of `EntitlementGranted`/`EntitlementRevoked` — the agent correctly found this pair isn't listed there at all yet, not even as documented-not-live, unlike the analogous `RecipeCreated`/etc. entries; fix that as part of this work).

**Port-signature decision, resolved**: widen `EntitlementCacheRepositoryPort.set(user_id, entitled)` to `upsert(user_id, entitled, occurred_at)`, matching `analytics-service`'s `upsert` signature exactly, rather than keeping the narrower `set()` and dropping the event's own timestamp. Reasoning: the event's `granted_at`/`revoked_at` is real information worth preserving for audit/debugging (when did billing-service actually grant/revoke, vs. when did this service's cache happen to catch up) — dropping it to keep a narrower interface saves nothing and costs real traceability. This is a small, additive-compatible interface widening (nothing else calls `set()`/`upsert()` yet).

Once implemented: persist a test plan, run the full TDD cycle, and report real test/coverage numbers, same as every other fix in this session. No git push/commit — the orchestrating session handles that after independent verification.
