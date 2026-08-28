# food-recognition-service — agent-scoped notes

This file is scoped guidance for any agent working inside
`services/food-recognition-service/`. It does not replace the root
`/CLAUDE.md` (architecture, workflow, guardrails) or
`.claude/agents/food-recognition-agent.md` (bounded context, domain
responsibilities, rules) — read both first, and read
`.claude/skills/media-recognition-conventions/SKILL.md` before touching
anything in `domain/` or `application/commands/analyze_food_photo.py` —
it is mandatory, non-negotiable reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, anthropic, or pyzbar.
- Event-driven CRUD (ADR-0002 exception) + Outbox — not event-sourced.
  `photo_analyses`/`barcode_lookups` are append-only audit records, one
  row per request.
- No inbound event consumers, no `diary-service` client/port anywhere in
  this codebase (enforced structurally: neither handler's constructor
  accepts one — see
  `tests/unit/application/test_analyze_food_photo.py::test_constructor_never_accepts_a_diary_service_port`
  and the equivalent for `DecodeBarcodeHandler`).

## Never do this

- Never collapse multiple detected candidates into a single guess, and
  never return more than `MAX_CANDIDATES` (3) from
  `AnalyzeFoodPhotoHandler` — see
  `.claude/skills/media-recognition-conventions/SKILL.md`.
- Never return a single precise portion number. Every quantitative
  estimate is a `PortionRangeGrams` — a zero-width or inverted range
  raises `InvalidPortionRangeError` at construction, it is never silently
  allowed through.
- Never treat a malformed/unparseable Claude response as a partial
  success. `ClaudeVisionAdapter._parse_candidates` raises
  `VisionRecognitionUnavailableError` on ANY parse failure — the caller
  falls back to `status="unavailable"`, never a best-effort guess.
- Never add a `diary-service` client, port, or HTTP call anywhere in this
  service. This service only detects and returns suggestions; the user's
  own subsequent `diary-service` log call is what actually writes an
  entry.
- Never persist the uploaded image bytes to disk, S3, or any blob
  storage. `recognition_routes.py` reads the upload into memory
  (`await file.read()`) and passes it directly as `bytes` — it must go
  out of scope at the end of the request function, never written anywhere
  else first.
- Never let the Claude vision system prompt (`SYSTEM_PROMPT` in
  `claude_vision_adapter.py`) drift into asking for a health/dietary
  judgement ("is this food healthy?") — it identifies food and estimates
  portion only (CLAUDE.md section 8, implementation plan section 6(d)).
  Changing the prompt is a reviewed, versioned change
  (`SYSTEM_PROMPT_VERSION`), per
  `.claude/skills/prompt-engineering-standards/SKILL.md`.
- Never make a live call to the real Anthropic API or a real
  `catalog-service` instance in this service's own test suite —
  `ClaudeVisionAdapter`/`CatalogLookupClient` tests use
  `httpx.MockTransport` fixtures exclusively.
- Never bump `ClaudeVisionAdapter`'s model tier, or swap the vision
  provider/barcode library, without a new ADR (CLAUDE.md section 9,
  media-recognition-conventions SKILL.md's "Model Lifecycle").

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s):
  `VisionRecognitionPort`, `BarcodeDecoderPort`, `CatalogLookupPort`,
  `PhotoAnalysisRepositoryPort`, `BarcodeLookupRepositoryPort`,
  `OutboxRepositoryPort`.
- Adapters: `infrastructure/external/claude_vision_adapter.py`,
  `infrastructure/external/catalog_lookup_client.py`,
  `infrastructure/recognition/pyzbar_barcode_decoder.py`,
  `infrastructure/persistence/`, `infrastructure/messaging/`.
- Composition root: `infrastructure/composition_root.py` — the only place
  concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3). Mutation testing (`mutmut`, domain layer only, `tests/unit`
scope) is recommended, advisory/non-blocking in CI
(`.github/workflows/food-recognition-service-ci.yml`'s `mutation-testing`
job).
