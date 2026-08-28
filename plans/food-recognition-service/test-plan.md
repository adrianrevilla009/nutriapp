# Test Plan — `food-recognition-service`

**Status:** Approved
**Date approved:** 2026-08-27
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/food-recognition-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD. The evaluation-harness gap (implementation plan §8.1) is treated as settled/deferred here, not re-litigated.

## 1. Unit test cases

**Value objects:**
- `ConfidenceScore(0.0)`, `ConfidenceScore(1.0)` accepted (boundary values); `ConfidenceScore(-0.01)`, `ConfidenceScore(1.01)` raise.
- `PortionRangeGrams(min=50, max=150)` accepted; `PortionRangeGrams(min=150, max=50)` raises; `PortionRangeGrams(min=0, max=100)` raises (portion must be positive); `PortionRangeGrams(min=100, max=100)` raises (a zero-width "range" is a false-precision smell — must be a genuine range).
- `Barcode("...")` — same validation rules as `catalog-service`'s value object (own independent copy, per CLAUDE.md §2.5).

**`AnalyzeFoodPhotoHandler` (fake `VisionRecognitionPort`, fake repository, fake outbox):**
- Provider returns 2 confident candidates → result has `status="detected"`, both candidates present with their confidence scores, `FoodPhotoAnalyzed` published with matching payload.
- Provider returns candidates all below the configured confidence threshold → `status="uncertain"`, candidates still returned (not discarded), event published with `status="uncertain"`.
- Provider raises (simulating exhausted retries / circuit open) → handler returns `status="unavailable"`, no candidates, event still published with `status="unavailable"` (audit trail of the failure itself), no exception escapes to the caller.
- Provider returns unparseable output (malformed JSON) → treated identically to a provider failure (`status="unavailable"`), never a partial/best-effort parse.
- Confirms **no code path ever writes to a `diary-service` client or port** — this handler's only side effects are its own repository write and its own outbox publish (a static/structural assertion — no such port is even injected into the handler, so this is really enforced by the constructor signature test).

**`DecodeBarcodeHandler` (fake `BarcodeDecoderPort`, fake `CatalogLookupPort`, fake repository):**
- Image decodes to a known barcode, catalog lookup finds a match → returns the matched product, lookup record persisted with `matched_product_id` set.
- Image decodes to a barcode with no catalog match → returns explicit "no match," lookup record persisted with `matched_product_id = None`, no exception.
- Image does not contain a decodable barcode at all → returns explicit "no match" (same shape as above, decoder returned `None` before any catalog call was attempted — confirms the catalog lookup is never called when there's nothing to look up).
- Catalog lookup port raises (simulating catalog-service circuit open) → `status="unavailable"`, no exception escapes.

## 2. Integration test cases

- `PyzbarBarcodeDecoder` — decodes each of the small set of locally-generated barcode fixture images (§ fixtures) to the exact expected barcode value; a non-barcode image (e.g. a plain photo fixture) decodes to `None`, not an exception.
- `ClaudeVisionAdapter` — against a mocked/recorded HTTP response fixture (not a live call): well-formed structured-JSON response parses into the expected `FoodCandidate` list; a malformed-JSON fixture response is treated as a parse failure (see unit case above, exercised here at the adapter boundary); a simulated timeout/5xx triggers the adapter's own retry-then-circuit-breaker behavior, verified by call-count assertions against the mock transport.
- `CatalogLookupClient` — against a fixture HTTP server standing in for `catalog-service`'s internal endpoint: valid credential + known barcode → product returned; valid credential + unknown barcode → explicit no-match (`404` mapped, not raised as an unhandled error); simulated repeated failures trip the circuit breaker, verified by call-count assertions (subsequent calls fail fast without hitting the fixture server).
- `PostgresPhotoAnalysisRepository` / `PostgresBarcodeLookupRepository` / `PostgresOutboxRepository` — round-trip persistence via testcontainers Postgres, same convention as every other service.
- Alembic migration `0001` applies cleanly to an empty database.

## 3. Contract test cases

- `POST /api/v1/recognition/photos/analyze` — `200` with `status="detected"` for a mocked confident-provider response; `200` with `status="uncertain"` for a mocked low-confidence response; `200` with `status="unavailable"` for a simulated provider failure (never a `5xx` bubbling to the caller for a *handled* provider failure — that's a designed fallback, not an error); `422` for a request with no image attached or an unsupported content type.
- `POST /api/v1/recognition/barcodes/decode` — `200` with matched product; `200` with explicit no-match shape for an undecodable or unmatched barcode; `422` for a malformed request.
- `FoodPhotoAnalyzed` (v1) — published payload matches `packages/shared-contracts/schemas/food_photo_analyzed.v1.json`, exercised for all three `status` values (`detected`/`uncertain`/`unavailable`), not just the happy path.

## 4. E2E test cases

**None added in this plan**, per implementation plan §7 — journey 2 needs `diary-service`'s confirmation-write flow wired to this service's output on the frontend side, which doesn't exist yet. Deferred, not silently dropped.

## 5. Event-sourcing-specific cases

**Not applicable.** `food-recognition-service` uses conventional persistence + event-driven CRUD (implementation plan §2), not event sourcing.

## 6. Coverage expectation

Domain layer (`ConfidenceScore`, `PortionRangeGrams`, `Barcode`) is small but simple — expect close to 100%, comfortably clearing the ≥90% floor. Application layer's two handlers each have 4 fake-port-driven cases above (≥85% floor, both success and every documented failure/fallback path covered — deliberately not just the happy path, since this service's entire value proposition is graceful degradation on uncertainty/failure). Infrastructure layer's three external adapters (§2's integration matrix) plus the two repositories plus the contract tests are expected to clear the ≥70% infrastructure floor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.

## 7. Fixtures (built, not sourced)

- `tests/fixtures/claude_vision_responses/*.json` — hand-authored synthetic response bodies matching the documented structured-output prompt contract (confident, low-confidence, malformed-JSON variants). Never a real Anthropic API capture.
- `tests/fixtures/barcode_images/*.png` — generated at fixture-build time using a barcode-generation library (e.g. `python-barcode`) encoding a handful of known test GTINs (including ones matching `catalog-service`'s own seeded/fixture products, so the integration test's catalog-lookup path has a real, deterministic match to assert against). Not sourced from any external site or real product photo.
