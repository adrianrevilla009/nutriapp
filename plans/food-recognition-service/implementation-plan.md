# Implementation Plan — `food-recognition-service`

**Status:** Approved
**Date approved:** 2026-08-27
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — conventional persistence, event-driven CRUD), ADR-0004 (messaging backbone), ADR-0022 (JWT/JWKS), `.claude/agents/food-recognition-agent.md`, `.claude/skills/media-recognition-conventions/SKILL.md` (mandatory), `.claude/skills/llm-cost-and-model-selection/SKILL.md` (mandatory), `.claude/skills/resilience-patterns/SKILL.md`, `docs/data-protection-and-privacy.md`, `docs/domain-glossary-and-context-map.md`, `docs/events-catalog.md`, `docs/api-catalog.md`, `/plans/catalog-service/implementation-plan.md` Addendum 2 (the internal lookup endpoint this service calls), `/plans/identity-service/implementation-plan.md` (structural precedent for conventional persistence + platform scaffolding)

## 1. Scope

Build `food-recognition-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding (`infra/k8s/charts/_lib/`, shared RDS instance, shared ElastiCache cluster, root `docker-compose.yml`/`Makefile`). No new platform-level infra needed except one new metered-external-API secret (Anthropic API key) and one new cross-service credential (this service calling `catalog-service`'s internal lookup endpoint).

**Bounded context** (per `.claude/agents/food-recognition-agent.md` / CLAUDE.md §2.2): recognition of food items in user-submitted photos, and barcode-based product detection, plus estimation of any derived nutrient value pending `diary-service` confirmation. This service owns no logging state (it never writes to `diary-service` directly), no product reference data (`catalog-service`'s job), and no nutrient-calculation logic (`nutrition-calculation-service`'s job) — it is purely a detection/suggestion service. Completes CLAUDE.md's E2E journey 2: "Upload a food photo → AI detects the item → logged with computed nutrients."

**Technology choice (already pinned by `.claude/agents/food-recognition-agent.md`, not reopened here):** food-photo detection uses a multimodal Claude vision API call (Anthropic's Messages API with an image content block), not a custom-trained model and not a third-party food-recognition SaaS (LogMeal, Clarifai, etc.) — no in-house training data exists and general-purpose vision-model accuracy on food identification is already strong. Barcode detection uses a standard server-side barcode-decoding library (`pyzbar`, wrapping `libzbar`) against the uploaded image, followed by a lookup against `catalog-service`'s new internal endpoint — no external barcode-recognition API needed, decoding is local and deterministic.

**Model tier (per `llm-cost-and-model-selection/SKILL.md` — "prefer the smallest/cheapest model that meets the accuracy bar"):** start with **Claude Haiku 4.5** for the vision call. This is a starting default, not a permanent commitment — `media-recognition-conventions/SKILL.md` §Evaluation requires a fixed, versioned test-media set; if/when real usage data or that evaluation set shows Haiku's accuracy is insufficient, escalating to Sonnet is a documented model-lifecycle change (new ADR per the skill's "Model Lifecycle" section — a provider/model change is ADR-worthy), not a silent bump. This plan does not build that evaluation harness with real photos (none available) — see §9.1.

**Data handling (per user's explicit request this session):** before this plan is implemented, the data-handling section below documents Anthropic's commercial API data-retention/training policy for submitted images, satisfying `media-recognition-conventions/SKILL.md`'s "any third-party recognition API used must have its data-retention policy... reviewed and documented before use."

> **Anthropic API data policy (as documented at api reference / commercial terms, reviewed 2026-08-27):** Anthropic does not use content submitted via the commercial API (Messages API, which is what this service calls) to train its models, by default and without a separate opt-in. API inputs/outputs are retained only transiently for abuse monitoring and trust & safety purposes (typically up to 30 days), not for model improvement. This satisfies the "no third-party training on user media without explicit, separate, opt-in consent" requirement — no additional consent flow is needed for the base recognition feature itself. This policy statement must be re-verified against Anthropic's current commercial terms at actual implementation time (terms can change) and the verified reference kept in this service's `README.md` "Data Handling" section, not just in this plan.

**Acceptance criteria:**

1. **Photo → food item detection.** `POST /api/v1/recognition/photos/analyze` (multipart image upload) → calls Claude's vision API with a structured prompt requesting: item name(s), an estimated portion **range** (never a single number, per `media-recognition-conventions/SKILL.md`), and a confidence score per candidate (0.0–1.0). Response returns the **top 3 candidates maximum**, each with its own confidence — never silently collapsed to one guess.
2. **Confidence threshold**, tunable via config (`FOOD_RECOGNITION_CONFIDENCE_THRESHOLD`, not a hardcoded magic number), documented in `README.md` once implemented. Below threshold: response is explicitly marked `"status": "uncertain"` — the API contract still returns the low-confidence candidates (frontend decides how to present them), but never implies a confident match.
3. **Barcode → product lookup.** `POST /api/v1/recognition/barcodes/decode` (multipart image upload) → `pyzbar` decodes the barcode value locally → calls `catalog-service`'s `GET /internal/v1/catalog/lookup?barcode={barcode}` (implementation plan: `/plans/catalog-service/implementation-plan.md` Addendum 2) → returns the matched product, or an explicit "no match" (never a guess) if the barcode isn't decodable or isn't in the catalog.
4. **Every detection publishes `FoodPhotoAnalyzed`** (photo path) via the Outbox — audit/traceability record only (item candidates, confidence scores, portion ranges, `model_version` = the exact Claude model string used). This event is **not** consumed synchronously by anything to auto-write to `diary-service` — the actual diary entry is created by the user's own subsequent, ordinary `diary-service` log call (frontend-orchestrated, referencing this detection's id in `correlation_id` for traceability), per `media-recognition-conventions/SKILL.md`'s "never auto-write" rule and `food-recognition-agent.md`'s "requiring user confirmation" rule. Barcode lookups are logged for audit but do not publish a domain event (no ambiguity to resolve — either the barcode matched a product or it didn't).
5. **Resilience**: two independent external dependencies, each with its own named circuit breaker/retry/timeout (`resilience-patterns/SKILL.md`) — the Claude API call, and the `catalog-service` internal lookup call. Circuit-open or total failure on either path falls back to **manual entry** (an explicit `"status": "unavailable"` response), never a stale/cached guess presented as fresh.
6. **Media retention**: the uploaded image is processed in memory and **discarded immediately after the recognition call returns** — never persisted to disk/S3/blob storage in this plan. (A future "let the user keep their food photos" feature is a separate, explicitly opt-in consent surface per CLAUDE.md §8, not built here.)
7. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).
8. Every user-facing estimate is framed as a suggestion pending confirmation, never implied as an exact/authoritative value (CLAUDE.md §8 — this service must never claim to provide medical nutrition therapy or diagnose anything; it identifies food items and estimates portions only).

**Explicitly out of scope for this plan:**
- The versioned real-photo evaluation harness required by `media-recognition-conventions/SKILL.md` §Evaluation — no real food photos are available to this session; the harness's *structure* is built (see §4/test-plan) using synthetic/documented fixture responses, with a clear `README.md` note that real-media calibration is a follow-up before this feature is trusted at accuracy-sensitive scale.
- Escalating to Sonnet or any other model tier — Haiku 4.5 is the starting tier; escalation is a future ADR-gated decision (§ above).
- Any opt-in "keep my food photos" retention feature.
- `diary-service` migrating any of its own catalog lookups to the new internal endpoint — unrelated to this plan (see catalog-service Addendum 2's own scope note).
- A dedicated barcode-scanning mobile SDK/client-side decode path — this plan decodes server-side from an uploaded image, consistent with the photo-upload flow it shares infrastructure with.

## 2. Architectural classification

**Event-driven CRUD**, per `.claude/agents/food-recognition-agent.md` — not event-sourced (ADR-0002). Detection results are written conventionally (one row per analysis request, for audit/traceability), never replayed to reconstruct state. `FoodPhotoAnalyzed` is published via the Outbox after every photo analysis, mirroring `catalog-service`'s and `nutrition-calculation-service`'s pattern.

## 3. Files to create or modify

```
services/food-recognition-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_food_recognition_tables.py
      # photo_analyses (append-only audit record: analysis_id, submitted_at,
      #   candidates JSONB [{name, portion_range_min_g, portion_range_max_g,
      #   confidence}], model_version, status)
      # barcode_lookups (append-only audit record: lookup_id, submitted_at,
      #   decoded_barcode, matched_product_id nullable, status)
      # outbox
  domain/
    entities/          # PhotoAnalysis, BarcodeLookup (simple records, no
                        # aggregate/event-sourcing behavior needed)
    value_objects/      # ConfidenceScore (0.0-1.0, validated), PortionRangeGrams
                        # (min < max, both > 0), Barcode (mirrors catalog-service's
                        # value object -- no shared code across services, own copy)
    events/              # base.py (own copy, per CLAUDE.md 2.5), food_photo_analyzed.py
    ports/               # vision_recognition_port.py, barcode_decoder_port.py,
                        # catalog_lookup_port.py, photo_analysis_repository_port.py,
                        # barcode_lookup_repository_port.py, outbox_repository_port.py
  application/
    commands/            # analyze_food_photo.py, decode_barcode.py
    dto/
    errors.py
  infrastructure/
    http/
      routes/            # recognition_routes.py, health.py
      schemas/
      dependencies.py
      error_mapping.py
    external/
      claude_vision_adapter.py   # implements VisionRecognitionPort; circuit
                                   # breaker + tenacity retry + timeout around
                                   # the Anthropic Messages API call
      catalog_lookup_client.py   # implements CatalogLookupPort; circuit
                                   # breaker + retry + timeout around the
                                   # internal HTTP call to catalog-service,
                                   # sends X-Internal-Service-Credential
    recognition/
      pyzbar_barcode_decoder.py  # implements BarcodeDecoderPort
    persistence/
      models.py, postgres_photo_analysis_repository.py,
      postgres_barcode_lookup_repository.py, postgres_outbox_repository.py
    messaging/
      rabbitmq_event_publisher.py, outbox_relay_worker.py
    composition_root.py, main.py
  tests/
    unit/domain/ , unit/application/
    integration/infrastructure/   # fixture-based Claude response fixtures
                                    # (never a live API call), fixture barcode
                                    # images, testcontainers Postgres/Redis/RabbitMQ
    contract/http/
    fixtures/
      claude_vision_responses/     # hand-authored, documented synthetic
                                    # response fixtures (JSON), NOT real photos
      barcode_images/              # small set of locally-generated barcode
                                    # images (encode a few known GTINs with a
                                    # barcode-generation library at fixture-build
                                    # time, not sourced externally)

infra/k8s/charts/food-recognition-service/   # mirrors nutrition-calculation-service's chart
infra/terraform/environments/dev/food-recognition-service.tf
  # RDS logical DB via db-provision Job, IRSA role, app-secrets (DATABASE_URL,
  # ANTHROPIC_API_KEY, catalog lookup credential read via the
  # cross_service_reveal_credential mechanism (owner=catalog-service,
  # caller=food-recognition-service) already generalized in
  # infra/terraform/modules/secrets by profile-service's Addendum 2
.github/workflows/food-recognition-service-ci.yml   # mirrors nutrition-calculation-service-ci.yml exactly (SHA-pinned actions, --frozen --extra dev, --no-build only if this service has no local path dependency needing a build -- it depends on packages/shared-contracts for JWT verification on its public routes, so NO --no-build on its own uv sync steps, same as diary/profile/nutrition-calculation-service)
docs/api-catalog.md, docs/events-catalog.md, docs/domain-glossary-and-context-map.md   # new entries
```

## 4. Ports and adapters (the anticorruption-layer boundary this plan flags for `architecture-agent`/`security-agent` review)

- `VisionRecognitionPort` — `async def analyze(image_bytes: bytes) -> list[FoodCandidate]`. Concrete adapter: `ClaudeVisionAdapter`, wraps the Anthropic Messages API with a vision content block, a versioned system prompt (per `.claude/skills/prompt-engineering-standards/SKILL.md` — prompts are versioned/reviewed like code), and structured-output parsing (the prompt requests strict JSON; a parse failure is treated as a total detection failure → manual-entry fallback, never a best-effort partial parse).
- `BarcodeDecoderPort` — `def decode(image_bytes: bytes) -> Barcode | None`. Concrete adapter: `PyzbarBarcodeDecoder`. Pure, local, no external call, no circuit breaker needed (matches `open_food_facts_source_adapter`'s "no I/O" precedent for why this stays synchronous internally even though the port method it's called from is async).
- `CatalogLookupPort` — `async def lookup_by_barcode(barcode: Barcode) -> CatalogProduct | None`. Concrete adapter: `CatalogLookupClient`, an `httpx.AsyncClient`-based HTTP client calling `catalog-service`'s new internal endpoint, circuit breaker + tenacity retry + explicit timeout, sends the shared cross-service credential header.
- `PhotoAnalysisRepositoryPort` / `BarcodeLookupRepositoryPort` — conventional CRUD repositories (append-only writes only in this plan; no update/delete use case exists).

## 5. Domain events

- `FoodPhotoAnalyzed` (v1) — `payload`: `analysis_id`, `candidates` (list of `{name, portion_range_min_g, portion_range_max_g, confidence}`), `model_version`, `status` (`"detected"` | `"uncertain"` | `"unavailable"`). Published via Outbox after every photo analysis attempt (including failed/unavailable ones, for observability — a run of failures is itself a signal worth having in the event stream, distinguishable by `status`).
- No event for barcode lookups (see §1 acceptance criterion 4's rationale).
- JSON Schema added to `packages/shared-contracts/schemas/food_photo_analyzed.v1.json`, contract-tested per `messaging-conventions/SKILL.md`.

## 6. Security & privacy review points (flagging `security-agent`)

(a) Uploaded photo handling: in-memory only, discarded after the request — verify no accidental persistence via a request-logging middleware capturing the raw multipart body (a common accidental-retention bug). (b) The Anthropic API key is a metered external-API secret — Terraform-managed, IRSA-scoped to this service only, tagged for cost-attribution per `docs/cost-management.md`. (c) The cross-service credential to `catalog-service` follows the already-established, already-reviewed `cross_service_reveal_credential` pattern — no new security design needed there, just one more entry in an existing list. (d) Confirm the Claude vision prompt does not ask the model to infer anything health-adjacent beyond food identification (e.g., no "does this food look unhealthy" framing) — stays strictly within "identify the food and estimate portion," consistent with CLAUDE.md §8's assistant/media boundary even though this isn't `nutrition-assistant-service`.

## 7. Testing strategy

- Unit tests: domain value objects (`ConfidenceScore` rejects out-of-range values, `PortionRangeGrams` rejects `min >= max`), `AnalyzeFoodPhotoHandler`/`DecodeBarcodeHandler` against fake ports (success, low-confidence, provider-unavailable, barcode-not-found paths).
- Integration tests: `PyzbarBarcodeDecoder` against a small set of locally-generated barcode images (generated at fixture-build time with a barcode-generation library — not sourced from any external site, avoiding any `external-data-ethics` concern); `ClaudeVisionAdapter` tested against recorded/mocked HTTP responses only, **never a live Anthropic API call in CI** (mirrors `catalog-service`'s VCR-cassette convention for external APIs); `CatalogLookupClient` tested against a fixture HTTP server standing in for `catalog-service`'s internal endpoint, including its circuit-breaker-open path.
- Contract tests: `FoodPhotoAnalyzed` schema; both public HTTP routes' request/response shapes, including the `"uncertain"`/`"unavailable"` status branches (not just the happy path — this is exactly the kind of edge case `qa-agent` must not let slide per its own rules).
- No E2E test added in this plan, same reasoning as `catalog-service`'s §4: journey 2 needs `diary-service`'s confirmation-write flow wired to this service's output on the frontend side, which doesn't exist yet.

## 8. Risks and open questions

**8.1 — No real food-photo evaluation set exists.** Explicitly out of scope (§1). This plan ships the detection pipeline and its fixture-based tests, not a validated accuracy number. Before this feature is promoted from "available" to "trusted for accuracy-sensitive use," someone needs to run it against a real, curated, varied photo set and record the result — tracked as a follow-up, not blocking this plan's merge.

**8.2 — Anthropic API data-retention policy needs periodic re-verification.** The statement in §1 is accurate as documented at plan-approval time but commercial API terms can change; `README.md`'s "Data Handling" section should note the verification date and be re-checked on any major terms update, not treated as permanently settled.

**8.3 — Cost-per-scan is not yet empirically measured.** Per `llm-cost-and-model-selection/SKILL.md`'s "per-request cost must be estimable before release" — this plan documents the mechanism (Haiku 4.5, one vision call per photo-analysis request, a bounded system prompt) but actual $/scan is only knowable once real usage data exists. A feature flag (per `.claude/skills/feature-flags/SKILL.md`) gating this feature is recommended so it can be throttled without a deploy if cost runs away — added in this plan's scope (§1 doesn't currently list it explicitly; adding it now): **acceptance criterion 9: this feature is gated behind a feature flag capable of disabling photo analysis (barcode lookup, being free/local, is not gated).**

**Human authorization for straight-through execution.** The product owner approved this plan and the accompanying test plan together (alongside `catalog-service`'s Addendum 2, which this plan depends on) and authorized proceeding directly through `/implementation-execution` and `/test-execution` without an additional per-stage pause, to be reviewed as a completed body of work afterward. This does **not** waive CLAUDE.md §7: no `git push`, no PR, no merge happen as part of this authorization — the branch is left committed locally, unpushed, for human review.
