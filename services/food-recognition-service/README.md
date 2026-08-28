# food-recognition-service

NutriApp's photo-based AI food detection (Claude vision) and barcode-based
product detection service. Detects candidate food items and estimated
portion ranges from an uploaded photo, or decodes a barcode from a photo
and looks up the matching product in `catalog-service`. Never writes to
`diary-service` -- every detection is a suggestion pending the user's own
confirmation via their own, separate `diary-service` log call. Completes
CLAUDE.md's E2E journey 2: "Upload a food photo -> AI detects the item ->
logged with computed nutrients."

## Bounded context

Pure detection/suggestion service -- owns no logging state, no product
reference data, and no nutrient-calculation logic. See
`.claude/agents/food-recognition-agent.md` and
`.claude/skills/media-recognition-conventions/SKILL.md` (mandatory
reading before touching the domain/application layers).

## Architecture

- Hexagonal (ADR-0001): `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only.
- **Event-driven CRUD** (ADR-0002 exception, per this service's agent
  doc), not event-sourced: `photo_analyses`/`barcode_lookups` are
  append-only audit records (one row per request, success or failure
  alike), written conventionally, never replayed to reconstruct state.
- `FoodPhotoAnalyzed` is published via the Outbox after **every** photo
  analysis attempt (including `"unavailable"` ones) -- an audit trail of
  failures is itself a useful signal. Barcode lookups publish no event
  (either the barcode matched a product or it didn't -- no ambiguity to
  resolve downstream).

## Technology choice

- **Photo detection**: a multimodal Claude vision API call (Anthropic
  Messages API), not a custom-trained model -- no in-house training data
  exists and general-purpose vision-model accuracy on food identification
  is already strong (see `.claude/skills/llm-cost-and-model-selection/SKILL.md`).
  Starting model tier: **Claude Haiku 4.5** (`FOOD_RECOGNITION_SERVICE_VISION_MODEL`,
  default `claude-haiku-4-5`) -- the smallest/cheapest tier expected to
  meet the accuracy bar. Escalating to a larger model is a future,
  ADR-gated decision, not a silent config bump.
- **Barcode detection**: `pyzbar` (wrapping the system `libzbar` shared
  library) decodes a barcode locally from the uploaded image, followed by
  a synchronous call to `catalog-service`'s internal lookup endpoint. No
  external barcode-recognition API.

## Data handling (media-recognition-conventions SKILL.md)

- **Uploaded images are processed in memory only and discarded
  immediately after the request returns.** Never persisted to disk, S3,
  or any blob storage in this plan. No request-logging middleware in this
  service captures the raw multipart body.
- **Anthropic API data-retention policy** (reviewed 2026-08-27, must be
  re-verified against Anthropic's current commercial terms before this
  feature is trusted at scale, and on any major terms update): Anthropic
  does not use content submitted via the commercial Messages API to train
  its models by default, and retains API inputs/outputs only transiently
  (typically up to 30 days) for abuse monitoring/trust & safety, not model
  improvement. No additional opt-in consent flow is required for the base
  recognition feature itself under this policy.
- No opt-in "keep my food photos" feature exists yet -- that would be a
  separate, explicit consent surface (CLAUDE.md section 8), not built
  here.

## Confidence threshold and feature flag

- `FOOD_RECOGNITION_CONFIDENCE_THRESHOLD` (default `0.6`) -- below this,
  a photo analysis response is `status="uncertain"`: candidates are still
  returned (never discarded), but the response never implies a confident
  match.
- `FOOD_RECOGNITION_PHOTO_ANALYSIS_ENABLED` (default `true`) -- an ops
  kill switch (implementation plan section 8.3, acceptance criterion 9)
  capable of disabling the metered Claude vision call without a deploy if
  cost or accuracy runs away. When disabled, `AnalyzeFoodPhotoHandler`
  never calls the vision provider at all and returns
  `status="unavailable"` immediately. Barcode lookup is free/local and is
  never gated by this flag. A full Unleash SDK integration
  (`.claude/skills/feature-flags/SKILL.md`) is deferred until
  `packages/feature-flags-client` exists -- no service in this repo wires
  Unleash yet; this env-var-based flag has the same boolean-gate shape and
  is a drop-in swap later.

## Resilience configuration (`.claude/skills/resilience-patterns/SKILL.md`)

Two independent external dependencies, each with its own named circuit
breaker/retry/timeout. Both fall back to an explicit
`"status": "unavailable"` response on circuit-open or persistent failure
-- never a stale/cached guess presented as fresh.

| Dependency | Circuit breaker | Retry | Timeout |
|---|---|---|---|
| Claude vision API (`ClaudeVisionAdapter`) | `purgatory`, `fail_max=5`, `reset_timeout=30s` | `tenacity`, 3 attempts, exponential backoff+jitter, on connection/timeout/5xx errors only | 5s connect / 20s read |
| `catalog-service` internal lookup (`CatalogLookupClient`) | `purgatory`, `fail_max=5`, `reset_timeout=30s` | `tenacity`, 3 attempts, exponential backoff+jitter, transient transport errors only | 2s connect / 5s read |

`PyzbarBarcodeDecoder` is pure, local, synchronous decoding -- no
external call, no circuit breaker needed.

Only a genuine service-health signal (a transport failure or a 5xx
response) counts toward either breaker's failure threshold -- a 404 ("no
match") or 401/403 (bad credential) is a normal, well-formed business
response and does not itself trip the breaker.

## The `catalog-service` internal lookup endpoint

`CatalogLookupClient` calls `catalog-service`'s
`GET /internal/v1/catalog/lookup?barcode={barcode}`
(`/plans/catalog-service/implementation-plan.md` Addendum 2), sending the
per-caller credential as `X-Internal-Service-Credential`
(env `FOOD_RECOGNITION_SERVICE_CATALOG_LOOKUP_CREDENTIAL`). Response body
reuses the same shape as catalog-service's public
`GET /api/v1/catalog/products/{id}`. This client's own tests mock this
HTTP call entirely (`httpx.MockTransport`) -- they never depend on
catalog-service's actual code/availability.

## Running locally

```
docker compose up food-recognition-service food-recognition-db rabbitmq
```

`pyzbar` requires the system `libzbar0` shared library at runtime --
already installed in this service's Docker image and by
`.github/workflows/food-recognition-service-ci.yml`'s integration-test
job. If running the test suite directly on a bare host (not via Docker),
install it first (Debian/Ubuntu: `apt-get install libzbar0`).

## Testing

```
cd services/food-recognition-service
uv sync --extra dev
uv run pytest tests/unit                 # domain + application, no I/O
uv run pytest tests/integration          # testcontainers: Postgres, RabbitMQ
                                          # + httpx.MockTransport for Claude/catalog-lookup (never live)
uv run pytest tests/contract             # HTTP + event schema contracts
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage targets (CLAUDE.md section 3): domain >= 90%, application >= 85%,
infrastructure >= 70%. Mutation testing (`mutmut`, domain layer only) is
advisory/non-blocking in CI, kept even though this service's domain is
simpler than e.g. `nutrition-calculation-service`'s formulas -- the
confidence/portion-range boundary validation is exactly the kind of logic
a mutant can silently break while every existing test still passes.

**`ClaudeVisionAdapter` and `CatalogLookupClient` tests never make a live
call** -- exercised against `httpx.MockTransport` fixture responses only,
per the test plan's explicit "never a live call" requirement.
`tests/fixtures/claude_vision_responses/*.json` are hand-authored
synthetic response bodies, never a real Anthropic API capture.
`tests/fixtures/barcode_images/*.png` are generated locally with
`python-barcode` (see `tests/fixtures/generate_barcode_images.py`), never
sourced from any external site or real product photo.

## Real-media evaluation (not built in this plan)

No real food photos are available in this environment. The domain
responsibilities (confidence surfacing, portion ranges, graceful
degradation) are validated against fixture data only. Before this feature
is promoted from "available" to "trusted for accuracy-sensitive use",
someone needs to run it against a real, curated, varied photo set and
record the result, per `.claude/skills/media-recognition-conventions/SKILL.md`'s
"Evaluation" section -- tracked as a follow-up, not blocking this plan.

## Owned events (see docs/events-catalog.md)

- `FoodPhotoAnalyzed` (v1) -- published after every photo analysis
  attempt (`status`: `"detected"` | `"uncertain"` | `"unavailable"`).

## Consumed events

None -- this service has no inbound event dependency on any other
service.

## Dependencies

- PostgreSQL (own logical database within the shared RDS instance).
- RabbitMQ (outbox relay -> `food-recognition.events` exchange). No inbound
  consumers.
- Anthropic's Messages API (metered, external, circuit-breaker-guarded).
- `catalog-service`'s internal barcode-lookup endpoint (synchronous,
  circuit-breaker-guarded).
