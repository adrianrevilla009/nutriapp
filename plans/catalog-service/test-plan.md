# Test Plan — `catalog-service`

**Status:** Approved
**Date approved:** 2026-08-26
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/catalog-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD (`.claude/skills/testing-strategy/SKILL.md`). Conflict-resolution and Redis-topology assumptions are pinned down in the implementation plan's Addendum 1 and are treated as settled here, not re-litigated.

## 1. Unit test cases

### Domain layer (no mocking, no I/O)

**Value objects**
- `Barcode`: valid EAN-13/UPC-A (correct check digit) accepted.
- `Barcode`: invalid check digit raises `InvalidBarcodeError`.
- `Barcode`: `None`/absent is a valid state (not every source provides one) — represented as `Barcode | None` at the entity level, not as an empty-string sentinel.
- `NutrientPanel`: all-zero panel accepted (a genuinely zero-calorie product, e.g. water); negative value in any field raises `InvalidNutrientPanelError`.
- `NutrientPanel`: missing (`None`) optional micronutrient fields accepted; missing calories/protein/carbs/fat (the macro core) raises `IncompleteNutrientPanelError`.
- `PackageSize`: positive value + supported unit accepted; zero/negative value raises; unsupported unit string raises `InvalidPackageSizeError`.
- `Price`: positive amount + ISO 4217 currency code accepted; negative amount raises; `None` (source has no price) is a valid state.
- `DietaryTags`/`AllergenTags`: constructing from a raw label list dedups and normalizes case; an unrecognized raw label is dropped (logged, not raised) rather than failing ingestion for an otherwise-valid product — a single unknown allergen string must never block cataloguing.

**`Product` aggregate**
- Constructing a `Product` from a complete, valid set of normalized fields succeeds.
- Constructing a `Product` with no barcode and no name raises `InvalidProductError` (name is the minimum required identity when no barcode exists).
- `Product.merge(existing, incoming)` where `incoming`'s source is the same as one already recorded: incoming values win for that source's fields, no `changed_fields` diff needed if identical.
- `Product.merge(existing, incoming)` where `incoming` is from a *new* source and the two sources agree on `nutrition_per_100g`: merged product keeps the value, `sources` set gains the new source, no conflict recorded.
- `Product.merge(existing, incoming)` where the two sources *disagree* on `nutrition_per_100g` for the same barcode: per Addendum 1's rule, the most-recently-updated source's value wins on the live `Product`, and both sources' raw values remain independently retrievable (via `product_sources`, exercised at the integration level, but the domain-level merge result exposes which source "won" for the resulting `ProductUpdated.changed_fields`).
- `Product.merge` produces no event/mutation when the incoming record is byte-for-byte identical to the currently stored one for that source (no-op ingestion, no spurious `ProductUpdated`).

**`product_normalizer`** (wide malformed/partial-input fixture matrix, per implementation-plan acceptance criterion 7)
- Well-formed Open Food Facts raw record → complete `RawProductRecord`.
- Well-formed USDA Branded Foods raw record → complete `RawProductRecord`.
- Raw record missing barcode entirely → `RawProductRecord` with `barcode=None`, ingestion proceeds (not rejected outright — see `Product` aggregate case above).
- Raw record with a barcode that fails the check digit → normalized with `barcode=None` and the raw invalid value logged/discarded, not raised up as a hard failure (a bad barcode from a third-party source degrades gracefully, per `external-data-ethics` SKILL.md's "source fragility" guidance).
- Raw record with nutrient values as strings (`"12.5"` instead of `12.5`) → coerced numerically.
- Raw record with nutrient values that are non-numeric garbage (`"n/a"`) → that specific field normalized to `None`, not a hard failure for the whole record.
- Raw record with nutrient units inconsistent with "per 100g" (e.g. per-serving-only data with no serving size to convert) → normalizer either converts (if serving size is present) or marks the panel incomplete, never silently mislabels per-serving data as per-100g.
- Raw record entirely missing the nutrition panel → `RawProductRecord` with `nutrient_panel=None`; downstream `Product` construction allowed if name/barcode are present (a name-only catalog entry is still useful for search, per acceptance criterion 3/4 not depending on nutrient completeness).
- Empty/`None` raw record → normalizer raises `EmptyRawRecordError` (nothing to normalize) rather than producing a garbage `RawProductRecord`.

**`product_deduplicator`**
- Two `RawProductRecord`s with the same barcode from different sources → identified as the same dedup key, routed to `Product.merge`.
- Two records with no barcode and different names → never merged (name-only records are never fuzzy-matched, per Addendum 1's "no fuzzy name+brand matching" rule).
- Two records with no barcode and the *same* name from the *same* source on a re-sync → treated as an update to the same product (source-scoped identity for barcode-less products is the source's own product id, tracked via `product_sources`, not the name).

**`allergen_tag_deriver`**
- Raw OFF `allergens_tags`-style list → correct `AllergenTags` set.
- Raw USDA-style allergen/label fields (different vocabulary than OFF) → correctly mapped to the same internal `AllergenTags` enum (cross-source vocabulary reconciliation is the actual point of this service — must be tested explicitly, not just per-source in isolation).
- Conflicting allergen info between two sources for the same barcode (one says contains gluten, the other doesn't mention it) → union, not intersection (never silently drop a safety-relevant allergen tag one source reported) — a deliberate conservative default, worth a dedicated test asserting union behavior.

## 2. Integration test cases (infrastructure layer, testcontainers)

- `PostgresProductRepository`: upsert-by-dedup-key round-trip (insert new, then update same barcode, confirm single row).
- `PostgresProductRepository`: two products with no barcode never collide (distinct rows even with identical names).
- `PostgresSearchReadModel`: exact name match returns the product.
- `PostgresSearchReadModel`: typo-tolerant partial match (`pg_trgm`) returns the product for a close misspelling.
- `PostgresSearchReadModel`: dietary/allergen filter combined with a text query narrows results correctly (both conditions applied, not OR'd).
- `PostgresSearchReadModel`: p95 latency smoke check against a seeded few-thousand-row fixture dataset stays comfortably under ADR-0012's 300ms activation threshold (a smoke assertion, not a load test — real load testing is `docs/performance-testing.md`'s separate concern).
- `OpenFoodFactsSourceAdapter`: parses a recorded sample export file (`fixtures/open_food_facts_export_samples/`) end-to-end into `RawProductRecord`s, including at least one malformed row in the sample that must be skipped-and-logged, not crash the whole batch.
- `UsdaFdcSourceAdapter`: VCR cassette of a successful paginated response → correct `RawProductRecord`s + correct next-cursor.
- `UsdaFdcSourceAdapter`: VCR cassette of a 429 (rate-limited) response → adapter backs off per the token-bucket limiter, does not raise up as a hard ingestion failure.
- `UsdaFdcSourceAdapter` circuit breaker: 5 consecutive VCR-simulated failures trips the breaker (`purgatory`); a subsequent call within `reset_timeout` short-circuits without attempting a network call; a call after `reset_timeout` half-opens and, on cassette success, closes the breaker again.
- `RedisSearchCache`: cache miss → populates cache; subsequent identical query → cache hit (no repository call); `ProductUpdated` event → targeted `catalog:product:{id}` key invalidated.
- `OutboxRelayWorker`: a row inserted into `outbox` in the same transaction as a product upsert is picked up and published; a publish failure leaves the row unpublished for retry (at-least-once, never silently dropped).
- Alembic migration `0001`: applies cleanly to an empty database; `pg_trgm` extension creation succeeds (validates the RDS-parameter-group risk flagged in the implementation plan's §7, at least for the local/dev Postgres image — a real RDS parameter-group check is an infra-execution-time concern, not resolvable in this test).

## 3. Contract test cases

- `GET /api/v1/catalog/products/search` — response schema (paginated product list) matches the documented OpenAPI contract; a request with an unsupported filter value returns `422`, not a `500`.
- `GET /api/v1/catalog/products/{id}` — `200` with full product shape for an existing id; `404` for a non-existent id.
- `ProductCatalogued` (v1) — published payload matches `packages/shared-contracts/schemas/product_catalogued.v1.json`.
- `ProductUpdated` (v1) — published payload matches `packages/shared-contracts/schemas/product_updated.v1.json`, including a non-empty `changed_fields` list whenever the event is emitted (an event with an empty `changed_fields` should never be published — that's a no-op, per §1's `Product.merge` no-op case).

## 4. E2E test cases

**None added in this plan.** `catalog-service`'s search endpoint is one component of critical journey #1 (`docs/testing-strategy.md` §2.4: "Register → log a food item from catalog search → see macro/micro totals"), but a true end-to-end test of that journey requires `identity-service` (done), `catalog-service` (this plan), `diary-service` (being built in parallel), and `nutrition-calculation-service` (not yet planned) all live together. Adding a partial/mocked "E2E" test now that fakes the missing services would test the fakes, not the journey — explicitly deferred until all four services exist, per `docs/testing-strategy.md`'s "critical user journeys only" scope, not silently dropped.

## 5. Event-sourcing-specific cases

**Not applicable.** `catalog-service` uses conventional persistence + event-driven CRUD (implementation plan §2), not event sourcing — no rebuild-from-events test applies. The equivalent guarantee for this service is the **idempotent-upsert** property already covered in §1/§2 above (`Product.merge`'s no-op-on-identical-input case, and `PostgresProductRepository`'s upsert-by-dedup-key round-trip).

## 6. Coverage expectation

Touches all three layers (domain, application, infrastructure). Domain layer (`product_normalizer`, `product_deduplicator`, `allergen_tag_deriver`, `Product` aggregate, all value objects) carries the widest case count in §1 by design — this is the anticorruption-layer boundary the implementation plan's §6 flags for `architecture-agent`/`security-agent` review, so it needs to be the most thoroughly tested layer, well above the ≥90% domain floor. Application-layer command/query handlers are tested against fake ports (§1-adjacent, omitted above for brevity — one test per handler's success path plus its documented error path) to clear ≥85%. Infrastructure §2's integration matrix (7 adapters/repositories × several cases each) plus §3's contract tests are expected to clear ≥70% infrastructure coverage. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.
