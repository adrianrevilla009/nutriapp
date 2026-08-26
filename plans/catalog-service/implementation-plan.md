# Implementation Plan — `catalog-service`

**Status:** Approved
**Date approved:** 2026-08-26
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — `catalog-service` is explicitly *not* in scope), ADR-0004 (messaging backbone), ADR-0012 (catalog search strategy, Accepted), `.claude/agents/catalog-agent.md`, `.claude/skills/external-data-ethics/SKILL.md`, `/plans/identity-service/implementation-plan.md` (reference pattern for conventional persistence + platform scaffolding), `/plans/profile-service/implementation-plan.md` (cross-reference only, for outbox/composition-root shape — not for its ES specifics), `/plans/platform-infra/implementation-plan.md` (shared infra reused as-is)

## 1. Scope

Build `catalog-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding (`infra/k8s/charts/_lib/`, shared RDS instance, root `docker-compose.yml`/`Makefile`) established by `identity-service`. No new platform-level infra needed (Postgres and RabbitMQ already exist; Redis already exists as `identity-redis` — this plan adds `catalog-redis` as a per-service cache instance, same pattern).

**Bounded context** (per `.claude/agents/catalog-agent.md` / CLAUDE.md §2.2): aggregation, normalization, deduplication, and full-text/faceted search of a supermarket-style product inventory sourced from third-party reference-data APIs, with dietary/allergen tag derivation. This service owns no authentication, no diary/logging state, and no nutrient-calculation logic (`nutrition-calculation-service`'s job) — it is the system of record for *product reference data* only.

**Source decision (already approved, not reopened here):** Open Food Facts (primary, via bulk export, not the live scan API), USDA FoodData Central Branded Foods (secondary, live rate-limited API), Open Prices (optional tertiary, pricing only). No adapter for Mercadona/Carrefour/Dia/Alcampo/Eroski — documented as unavailable per their legal notices, no official API. Architecture keeps adding a future retailer adapter cheap if/when one is officially cleared.

**Acceptance criteria** (restated from the task, refined into concrete, numbered scope items for this plan):
1. `CatalogSourcePort` (domain/application boundary) with a concrete `OpenFoodFactsBulkExportAdapter` that ingests a downloaded OFF export file (JSONL, per §7) into `catalog-service`'s own `products` table, each row passed through the shared domain normalization/dedup service. Execution of the actual bulk run is out of scope for this plan (design only, per CLAUDE.md §7 — see §9.1).
2. A second concrete adapter, `UsdaFdcApiAdapter`, ingests the Branded Foods dataset via the live USDA FDC HTTP API, reconciled against the same dedup key (barcode/GTIN) as Open Food Facts.
3. `GET /api/v1/catalog/products/search` — full-text + typo-tolerant search over the product catalog using Postgres `tsvector`/GIN + `pg_trgm`, per ADR-0012 (no OpenSearch).
4. Dietary/allergen filters (`vegan`, `vegetarian`, `gluten_free`, `lactose_free`, etc.) as query parameters on the same search endpoint, derived from ingested label/allergen data.
5. `ProductCatalogued` (new product) / `ProductUpdated` (existing product's data changed) domain events published via the Outbox pattern after every ingestion write, matching `.claude/agents/catalog-agent.md`'s naming intent (`ProductAdded`/`ProductUpdated`) — this plan renames `ProductAdded` to `ProductCatalogued` for past-tense precision consistent with the PascalCase-past-tense convention (`UserRegistered`, `WeightRecorded`) since "Added" reads awkwardly with a dedup-merge outcome (see §5 for the exact reasoning and the required doc reconciliation).
6. Ingestion adapters (both OFF and USDA) are integration-tested exclusively against recorded fixtures (VCR-style cassettes via `vcrpy` or `pytest-recording`) — never live requests in CI, per `external-data-ethics` SKILL.md and `catalog-agent.md`.
7. Normalization/dedup domain logic unit-tested with a wide range of malformed/partial input fixtures (missing barcode, missing nutrient panel, conflicting units, non-numeric nutrient values, duplicate barcode across sources with divergent data).
8. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).

**Explicitly out of scope for this plan** (flagged, not silently dropped):
- Open Prices adapter (optional tertiary source, acceptance criteria don't require it at launch — noted as a follow-up in §9).
- Executing any bulk/production-scale ingestion run — this plan designs the adapters and a schedulable job; running it against real data requires the separate CLAUDE.md §7 human-confirmation gate at execution time, independent of this plan's approval.
- A future retailer adapter (Mercadona et al.) — no adapter code, only an architecture that doesn't block adding one later.

## 2. Architectural classification

Per ADR-0002 and `.claude/agents/catalog-agent.md`: **conventional persistence + event-driven CRUD**, not event sourcing — `catalog-service` is not in ADR-0002's ES-mandatory list (only `diary-service` and `profile-service` are). State (the `products` table) is the source of truth, stored and updated directly; `ProductCatalogued`/`ProductUpdated` are published as a side effect of that write, via the Outbox pattern, exactly like `identity-service`'s `UserRegistered`/`NewDeviceLoginDetected` — not like `profile-service`'s event-sourced aggregate/projector pair. This is the **first service in the repo to mirror `identity-service`'s conventional-persistence pattern** rather than `profile-service`'s ES pattern, and the first service whose write model is populated by *ingestion from external third-party sources* rather than direct user action — both are precedents worth an explicit `architecture-agent` look (see §6).

All three hexagonal layers are touched. New pattern introduced at the domain/application boundary: a **multi-source pluggable ingestion port** (`CatalogSourcePort`) with independent adapters per source feeding one shared domain-level normalization/dedup service — this specific shape (N adapters → 1 shared domain reconciliation step) does not yet exist anywhere else in the codebase and is worth calling out for reuse if a future service (e.g. `activity-service`'s multi-wearable-provider ingestion) needs the same shape.

## 3. Files to create or modify

```
services/catalog-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_catalog_tables.py
      # products (read/write model, tsvector + GIN + pg_trgm indexes),
      # product_sources (per-source raw-value tracking, see §7),
      # outbox, ingestion_runs (audit: source, started_at, finished_at,
      # items_seen/added/updated/skipped, status)

  domain/
    entities/product.py                        # aggregate root: identity = product_id (uuid);
                                                 # dedup/merge key = barcode when present
    value_objects/barcode.py                    # GTIN/EAN validation (check digit)
    value_objects/nutrient_panel.py             # per-100g macro/micro fields, immutable
    value_objects/dietary_tags.py                # frozenset of DietaryTag enum
    value_objects/allergen_tags.py               # frozenset of AllergenTag enum
    value_objects/package_size.py                # value + unit
    value_objects/price.py                       # amount + currency, optional (may be absent)
    value_objects/source_reference.py            # source name + source's own product id/URL
    events/product_catalogued.py
    events/product_updated.py
    ports/product_repository_port.py
    ports/catalog_source_port.py                 # CatalogSourcePort: fetch_batch() -> RawProductRecord
    ports/event_publisher_port.py
    ports/outbox_repository_port.py
    ports/search_read_port.py                    # search-facing read port (query object -> Product page)
    ports/search_cache_port.py                    # cache-aside wrapper around search reads
    services/product_normalizer.py               # per-source raw dict -> RawProductRecord -> domain VOs
    services/product_deduplicator.py             # merge/reconcile strategy, see §7's conflict rule
    services/allergen_tag_deriver.py             # derives DietaryTag/AllergenTag set from raw labels

  application/
    dto/raw_product_record.py                    # shared intermediate shape all source adapters produce
    commands/ingest_product_batch.py              (+ handler: normalize -> dedup -> upsert -> outbox)
    queries/search_products.py                    (+ handler: cache-aside -> ProductSearchReadPort)
    queries/get_product_by_id.py                  (+ handler)
    jobs/run_open_food_facts_ingestion.py          # orchestrates a bounded ingestion run over one
                                                    # export file/delta, calls ingest_product_batch
                                                    # in pages; scheduling trigger is external (§7)
    jobs/run_usda_fdc_ingestion.py                 # same shape, paginated live-API run,
                                                    # rate-limit-aware (§7)

  infrastructure/
    http/routes/search_routes.py
    http/routes/product_routes.py                 # GET /products/{id}
    http/schemas/
    http/health.py
    messaging/rabbitmq_event_publisher.py
    messaging/outbox_relay_worker.py
    persistence/models.py
    persistence/postgres_product_repository.py     # ProductRepositoryPort adapter
    persistence/postgres_search_read_model.py       # SearchReadPort adapter (tsvector/pg_trgm query)
    persistence/postgres_outbox_repository.py
    persistence/postgres_ingestion_run_repository.py  # audit trail for each ingestion run
    caching/redis_search_cache.py                   # SearchCachePort adapter
    external/open_food_facts/bulk_export_reader.py   # streams/parses the downloaded JSONL export
    external/open_food_facts/open_food_facts_source_adapter.py  # implements CatalogSourcePort
    external/usda_fdc/usda_fdc_client.py             # httpx client, own connection pool (bulkhead)
    external/usda_fdc/usda_fdc_source_adapter.py     # implements CatalogSourcePort
    external/usda_fdc/circuit_breaker.py             # purgatory instance, USDA-specific config
    external/open_prices/                            # placeholder dir only, not implemented (§9)
    composition_root.py
    main.py

  tests/
    unit/domain/...        # product_normalizer, product_deduplicator, allergen_tag_deriver —
                            # wide malformed/partial-input fixture matrix (criterion 7)
    unit/application/...   # ingest_product_batch / search_products handlers, fake ports
    integration/infrastructure/
        test_postgres_product_repository.py
        test_postgres_search_read_model.py          # tsvector/pg_trgm query correctness + p95 smoke
        test_open_food_facts_source_adapter.py       # against a recorded fixture export file, not live
        test_usda_fdc_source_adapter.py              # VCR cassettes, never live (criterion 6)
        test_usda_fdc_circuit_breaker.py             # trip/half-open/recover, per resilience-patterns
        test_redis_search_cache.py                    # hit/miss/invalidation-on-ProductUpdated
        test_outbox_relay_worker.py
        test_migration_0001.py
    contract/http/test_search_routes.py, test_product_routes.py
    contract/events/test_event_schemas.py            # ProductCatalogued/ProductUpdated
    fixtures/factories.py
    fixtures/cassettes/usda_fdc/                      # VCR cassettes
    fixtures/open_food_facts_export_samples/          # small representative JSONL sample files,
                                                       # including malformed rows

infra/k8s/charts/catalog-service/
  Chart.yaml, values.yaml, values-dev.yaml, values-staging.yaml, values-prod.yaml
  values.schema.json                 # included from day one, per profile-service's addendum lesson
  ci/synthetic-values.yaml
  templates/ (built on infra/k8s/charts/_lib/, same as identity-service/profile-service)

infra/terraform/environments/dev/catalog-service.tf
    # mirrors identity-service.tf: module.ecr_catalog_service, Helm release referencing
    # module.rds/module.secrets/module.eks outputs, _db-provision-job wiring;
    # Redis: reuses the single shared infra/terraform/modules/elasticache cluster the
    # platform-infra plan already provisions (main.tf's `module "elasticache"`) via a
    # `catalog:*` key namespace — no new ElastiCache cluster (see Addendum 1)

.github/workflows/catalog-service-ci.yml
    # includes helm-lint-and-template job from the start; a dedicated fixture-freshness
    # check step is NOT added here (VCR cassettes are reviewed like code, not auto-refreshed
    # in CI, to avoid a CI job silently making live third-party calls)

docker-compose.yml, Makefile          # add catalog-db, catalog-redis, catalog-service blocks /
                                       # SERVICE=catalog-service target

packages/shared-contracts/schemas/product_catalogued.v1.json      # new
packages/shared-contracts/schemas/product_updated.v1.json         # new
packages/shared-contracts/python/shared_contracts/events/         # add the two above

docs/events-catalog.md      # replace the current ProductAdded/ProductUpdated combined
                             # placeholder entry (lines 78-85) with ProductCatalogued (renamed)
                             # + ProductUpdated as separately-versioned, Status: Active entries
docs/api-catalog.md         # /api/v1/catalog/*: planned -> active
docs/domain-glossary-and-context-map.md   # add "Ingestion Run", "Dedup Key" terms if this
                             # session's normalization vocabulary isn't already covered by
                             # the existing "Product" entry
.claude/agents/catalog-agent.md   # update "ProductAdded" reference to "ProductCatalogued"
                             # once the rename is confirmed at /implementation-review (§5)
```

## 4. Ports/adapters affected

| Port (domain/application) | Adapter (infrastructure) |
|---|---|
| `ProductRepositoryPort` | `PostgresProductRepository` (upsert by dedup key, load by id/barcode) |
| `SearchReadPort` | `PostgresSearchReadModel` (`tsvector`/`tsquery` + GIN + `pg_trgm` query, ADR-0012) |
| `SearchCachePort` | `RedisSearchCache` (cache-aside, `catalog:search-results:*`, 15 min TTL) |
| `EventPublisherPort` | `RabbitMqEventPublisher` (faststream) — same pattern as `identity-service`, new instance |
| `OutboxRepositoryPort` | `PostgresOutboxRepository` + `OutboxRelayWorker` — same pattern, new instance |
| `CatalogSourcePort` | `OpenFoodFactsSourceAdapter` (reads a downloaded bulk export file via `BulkExportReader`, no live HTTP calls at all) |
| `CatalogSourcePort` | `UsdaFdcSourceAdapter` (live HTTP via `UsdaFdcClient`, own `httpx.AsyncClient` pool — bulkhead — wrapped in `purgatory` circuit breaker + `tenacity` retry) |
| *(not implemented this plan)* | `OpenPricesSourceAdapter` — same `CatalogSourcePort` interface, deferred (§9) |
| *(not implemented this plan, explicitly future-proofed)* | A hypothetical `MercadonaSourceAdapter`/etc. would implement the same `CatalogSourcePort` with zero changes to `product_normalizer`/`product_deduplicator` — this is the concrete test of the port abstraction's value |

All new. `EventPublisherPort`/`OutboxRepositoryPort` reuse `identity-service`'s established *pattern*, not its code — `catalog-service` gets its own outbox table (CLAUDE.md §2.5, no shared schemas). `CatalogSourcePort` is the new multi-source abstraction this plan introduces (§2, §6) — its single method contract is `async def fetch_batch(cursor: str | None) -> SourceBatch` where `SourceBatch` yields `RawProductRecord` DTOs (application-layer, not domain) plus a next-cursor for pagination/resumability, so both a file-based (OFF) and an HTTP-paginated (USDA) source satisfy the same shape.

## 5. Domain events

- **`ProductCatalogued` (v1, new — renamed from the agent-doc's `ProductAdded`)** — `{ "product_id": "uuid", "barcode": "string | null", "name": "string", "brand": "string | null", "category": "string | null", "nutrition_per_100g": { "...": "macro/micro fields" }, "dietary_tags": ["string"], "allergen_tags": ["string"], "package_size": { "value": "number", "unit": "string" } | null, "sources": ["open_food_facts" | "usda_fdc"], "catalogued_at": "timestamp" }`. Emitted the first time a product (by dedup key) is written to `products`, regardless of which source triggered it.
- **`ProductUpdated` (v1, new)** — same payload shape as `ProductCatalogued` plus `"changed_fields": ["string"]`, emitted when an already-catalogued product's data changes on a subsequent ingestion pass (either the same source re-syncing, or a second source's data reconciling into the row per §7's conflict rule).
- No events consumed — `catalog-service` has no inbound event dependency on any other service (it is a pure upstream/reference-data source in the context map).

**Naming rename flagged explicitly**: `.claude/agents/catalog-agent.md` §"Architectural Constraints" currently says `ProductAdded`/`ProductUpdated`, and `docs/events-catalog.md`'s existing placeholder entry (lines 78–85) also says `ProductAdded`. This plan proposes `ProductCatalogued` instead, for two reasons: (a) strict PascalCase-past-tense consistency with `UserRegistered`/`WeightRecorded`/`GoalSet` — "Added" is grammatically past tense but reads as a raw CRUD verb rather than a domain fact, whereas "Catalogued" names the actual business event (this product entered the catalog); (b) with the dedup/merge design, the first-write case is not always a clean "add" (it can be a second source completing a record the first source started, still a fresh catalog entry from the read side's perspective) — "Catalogued" fits that ambiguity better than "Added" does. This is a naming call, not a payload/semantics change — approved in Addendum 1 below.

Requires `docs/events-catalog.md` update (replace the single placeholder entry with two concrete, separately-versioned `Status: Active` entries) and `packages/shared-contracts` schema additions. Documented consumers per `docs/domain-glossary-and-context-map.md` / `docs/events-catalog.md`: `diary-service`, `food-recognition-service` (barcode matching), `recipe-service` — none exist as live consumers yet, so no live integration breaks from the rename; the payload shape decided here becomes their future contract.

## 6. Cross-service impact — flagged for `architecture-agent`

- **First service to mirror `identity-service`'s conventional-persistence + event-driven-CRUD pattern** rather than `profile-service`'s event-sourced pattern — worth confirming the outbox/composition-root shape generalizes cleanly a second time under conventional persistence specifically (not just under ES, which `profile-service` already validated).
- **First service whose write model is populated by ingestion from external third-party data sources**, not directly by user action or another internal service's event. This is a materially different trust/validation boundary (arbitrary third-party data quality, not a validated internal command) — `architecture-agent` and `security-agent` should both look at `product_normalizer`/`product_deduplicator` as the anticorruption layer boundary (per `docs/domain-glossary-and-context-map.md` §2's "Any external third-party API... Anticorruption Layer" row, which already anticipates this).
- **New pattern: multi-source pluggable ingestion via one shared `CatalogSourcePort`** feeding a single domain-level dedup/reconciliation service. Nothing else in the repo has this N-adapters-to-1-domain-service shape yet (closest precedent, `identity-service`'s single `TokenIssuerPort`, is 1:1). Worth an explicit sign-off that this generalizes, since `activity-service`'s planned multi-wearable-provider ingestion (Apple Health/Google Fit/Fitbit/Garmin, CLAUDE.md §2.2) will likely want to copy this exact shape later.
- `diary-service`, `food-recognition-service`, `recipe-service` are documented consumers of `ProductCatalogued`/`ProductUpdated` (`docs/domain-glossary-and-context-map.md`) but don't exist yet — no live integration to break, but the event rename in §5 and the payload shape decided here become their contract; `diary-service` is being built in parallel right now (separate plan/worktree) and will treat `catalog-service`'s product ids as opaque references, so no coupling risk during this build.
- `nutrition-calculation-service` is not a direct consumer of these events per the current docs (it consumes `FoodEntryLogged` from `diary-service`, not catalog events directly) — confirm this reading matches `docs/domain-glossary-and-context-map.md`'s actual intent, since `nutrition-calculation-service`'s formula ultimately depends on catalog nutrient data via `diary-service`'s `product_id` reference, and a stale local copy vs. a live catalog lookup at calculation time is a design question that belongs to `nutrition-calculation-service`'s own plan, not this one — noted here only so it isn't silently assumed.

## 7. Resilience/caching/migration needs

**Circuit breaker + retry + timeout per source adapter** (`.claude/skills/resilience-patterns/SKILL.md`):
- `UsdaFdcSourceAdapter` (only adapter making live outbound calls): `purgatory`-based circuit breaker, `fail_max=5` consecutive failures, `reset_timeout=60s` (half-open trial after 1 minute) — documented in `catalog-service/README.md`. `tenacity` retry: exponential backoff with jitter, max 3 attempts, max total wait 30s; retries are safe here because USDA's Branded Foods lookup-by-page is idempotent (no side effect on the USDA side). Explicit timeout: 10s connect / 30s read per request (FDC responses can be large JSON pages). Own `httpx.AsyncClient` with a bounded connection pool (bulkhead) — isolated from any other outbound client in the service (there is currently only this one, but the pattern is set up correctly for when Open Prices is added later).
- USDA's published rate limit (1000 requests/hour/IP with a registered key) is respected via a token-bucket rate limiter inside `UsdaFdcClient` (Redis-backed counter, `catalog:usda-rate-limit:{hour_bucket}`, same Redis instance as the search cache) rather than relying on retry-after-429 alone — a proactive throttle, not just a reactive backoff, per `external-data-ethics` SKILL.md's "respect any published rate limit."
- `OpenFoodFactsSourceAdapter` makes **no live HTTP calls** (reads a downloaded export file) — no circuit breaker needed for the adapter itself; the *download* of the export file (outside this adapter's scope, likely a separate ops/cron concern) would need its own resilience wrapper if automated later, noted but not designed here since acceptance criterion 1 only requires ingesting a design that consumes an already-downloaded file.
- Fallback behavior: if `UsdaFdcSourceAdapter`'s circuit is open during a scheduled run, that run's USDA phase is skipped for this cycle (logged, surfaced via the `ingestion_runs` audit table's `status`) and the OFF phase proceeds independently — the two sources' ingestion runs are decoupled, one source's failure never blocks the other.

**Caching** (`.claude/skills/caching-strategy/SKILL.md`):
- `catalog:product:{product_id}` — 24h TTL (reference data, changes infrequently) — matches the skill's documented default exactly.
- `catalog:search-results:{query_hash}` — 15 min TTL — matches the skill's documented default exactly.
- Event-driven invalidation: `ProductUpdated` → invalidate `catalog:product:{product_id}` (per the skill's example) and best-effort invalidate any cached search-result page containing that product (acceptable staleness within the 15 min TTL if a targeted invalidation is impractical — document this as a deliberate simplification, not silently skipped).
- `catalog:usda-rate-limit:{hour_bucket}` — 1h TTL (rolling window counter, not a "cache" in the read sense but reuses the same Redis instance/skill's namespacing convention).

**Migration** (`.claude/skills/database-migrations/SKILL.md`):
- First Alembic migration, `CREATE TABLE`-only: `products` (with `tsvector` generated column + GIN index, `pg_trgm` extension + trigram index on `name`/`brand`), `product_sources` (one row per source-per-product, storing that source's raw last-seen values — needed for the conflict-resolution rule below and for re-deriving `ProductUpdated`'s `changed_fields`), `outbox`, `ingestion_runs` (audit). Purely additive — does not trigger the destructive-change approval gate.
- `pg_trgm` extension creation (`CREATE EXTENSION IF NOT EXISTS pg_trgm`) is itself additive and safe, but is a superuser/extension-privilege operation on some managed Postgres setups — confirm the RDS parameter group used by the platform-infra plan already allows it (identity-service/profile-service didn't need this extension, so it hasn't been exercised yet); flagged as a migration-time risk, not a blocking one.
- **Terraform**: same shape as `identity-service.tf` — no new shared infra strictly required, just this service's chart wiring + its own ECR repo via `infra/terraform/modules/ecr`. Redis: resolved in Addendum 1 below.

## 8. Test plan reference

See `/plans/catalog-service/test-plan.md`.

## 9. Risks and open questions

**9.1 — Bulk/production-scale ingestion runs are execution-time gated, not plan-time gated (restating CLAUDE.md §7 explicitly, not a footnote).** This plan designs `OpenFoodFactsSourceAdapter`/`UsdaFdcSourceAdapter` and the `run_*_ingestion` jobs, and its tests exercise them against small fixture/cassette data only. Actually running either job against the real Open Food Facts export or the live USDA API — for anything beyond a tiny, ad-hoc smoke fetch — is a bulk/production-scale ingestion run and requires explicit human confirmation immediately before that specific execution, enforced by `.claude/hooks/pre-bash-guard.sh` and restated in `.claude/agents/catalog-agent.md`. This is a standing constraint on every future ingestion run this service performs, not a one-time approval consumed by approving this plan. **No real ingestion run will be executed as part of implementing this plan** — implementation and test execution use fixtures/cassettes exclusively.

**9.2 — Open Food Facts delta-sync cadence needs a human-confirmed schedule.** Deferred: the job exists and is manually triggerable but is **not** wired to any scheduler (k8s `CronJob` or otherwise) as part of this plan.

**9.3 — Cross-source conflict resolution when Open Food Facts and USDA disagree on the same barcode — resolved in Addendum 1.**

**9.4 — USDA's 1000 req/hour rate limit bounds initial backfill time.** Not blocking implementation (no real backfill runs this plan); `run_usda_fdc_ingestion` is designed resumable (cursor-based) specifically so a future multi-day backfill can pause/resume across the §9.1 gate. Actual backfill scope (all of Branded Foods vs. a curated subset) is a decision for whoever executes the first real run, not this plan.

**9.5 — Open Prices adapter deferred, not blocking.** Confirmed out of scope for this iteration (§1); `CatalogSourcePort` already accommodates adding it later with no domain/application changes.

**9.6 — `products` table schema treats price as optional and single-value, not per-retailer.** Accepted as designed for this MVP pass — a single nullable "best-known" price via the `Price` value object, not a per-retailer price list. If per-retailer pricing granularity becomes an actual product requirement, that's a follow-up plan adding a `product_prices` table, not a rework of this one.

**9.7 — Redis topology — resolved in Addendum 1.**

---

## Addendum 1 — 2026-08-26, open questions resolved at approval

**§9.3 resolved.** Conflict-resolution policy for `product_deduplicator`, confirmed as proposed:
(a) barcode is the sole dedup key — no fuzzy name+brand matching (too high a false-merge risk for data feeding nutrition calculations downstream);
(b) on a genuine numeric disagreement in `nutrition_per_100g` between sources for the same barcode, the most-recently-updated source's `product_sources` row wins for the live `products` row, but **both** sources' raw values are retained in `product_sources` — no data is silently discarded, and a future curation step could override;
(c) a product present in only one source is trusted as-is.
This is pinned down as a concrete rule for `/test-plan` to write cases against, not left as a design-time placeholder.

**§9.7 resolved.** `infra/terraform/environments/dev/main.tf` already provisions exactly one shared `module "elasticache"` cluster for the whole platform (confirmed by inspection — no per-service ElastiCache module exists for `identity-service` either). `catalog-service` reuses that same shared cluster in Terraform/prod, isolated purely by its `catalog:*` Redis key namespace — **no new ElastiCache cluster is provisioned**. For local `docker-compose` parity, add a dedicated `catalog-redis` container (mirroring `identity-redis`'s existing per-service-container convention for local dev, which is a dev-environment convenience and not indicative of the shared-cluster production topology).

**Human authorization for straight-through execution.** The product owner approved this plan and the accompanying test plan together and authorized proceeding directly through `/implementation-execution` and `/test-execution` without an additional per-stage pause, to be reviewed as a completed body of work afterward. This does **not** waive CLAUDE.md §7: no `git push`, no PR, no merge, and no real bulk ingestion run happen as part of this authorization — the branch is left committed locally, unpushed, for human review.
