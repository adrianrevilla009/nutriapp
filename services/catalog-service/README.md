# catalog-service

NutriApp's supermarket product inventory: aggregation, normalization,
deduplication, and full-text/faceted search over a catalog sourced from
third-party reference-data APIs. First service in the repo to mirror
`identity-service`'s conventional-persistence + event-driven-CRUD pattern
rather than `profile-service`'s event-sourced pattern (CLAUDE.md section
14, implementation plan section 2), and the first service whose write
model is populated by ingestion from external third-party sources rather
than direct user action.

## Bounded context

Ingestion, normalization, deduplication, dietary/allergen tag derivation,
and full-text/faceted search of a supermarket-style product inventory.
This service owns no authentication, no diary/logging state, and no
nutrient-calculation logic — it is the system of record for *product
reference data* only (see `.claude/agents/catalog-agent.md`).

## Sources

**Evaluated and integrated:**
- **Open Food Facts** (primary) — ingested via its bulk export (a
  downloaded JSONL file), never the live API, per
  `.claude/skills/external-data-ethics/SKILL.md`'s "cache aggressively /
  never repeat a request whose result is still valid" guidance and the
  fact Open Food Facts explicitly publishes and recommends the bulk
  export for large-scale consumption over its rate-limited live search
  API. `infrastructure/external/open_food_facts/`.
- **USDA FoodData Central, Branded Foods dataset** (secondary) — a live,
  registered-key, rate-limited (1000 req/hour/IP) HTTP API with an
  official public API and a permissive terms of use for non-commercial
  and commercial reference-data reuse. `infrastructure/external/usda_fdc/`.

**Evaluated and explicitly rejected — no adapter exists or will be added
without a new ADR reopening this decision** (per
`.claude/skills/external-data-ethics/SKILL.md`'s "document the source as
unavailable rather than working around the restriction"):
- **Mercadona** — no official public product API; its site's terms of
  service prohibit automated scraping of product/pricing data. Rejected.
- **Carrefour (ES)** — no official public product API for third-party
  reference-data reuse; scraping its storefront is against its published
  terms of service. Rejected.
- **Dia** — no official public product API. Rejected.
- **Alcampo** — no official public product API. Rejected.
- **Eroski** — no official public product API. Rejected.

The `CatalogSourcePort` abstraction (`domain/ports/catalog_source_port.py`)
makes adding a future retailer adapter cheap *if and only if* one of these
retailers (or a new one) ever publishes an official API with terms that
permit this use — that would be a new implementation plan, not a
reinterpretation of this rejection.

**Deferred, not rejected:** Open Prices (pricing-only tertiary source) —
`infrastructure/external/open_prices/` is a placeholder directory only;
no adapter code exists yet (implementation plan sections 1/9.5).

## Architecture

- Hexagonal (ADR-0001): `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only.
- Conventional persistence + Outbox (ADR-0002, not event-sourced) —
  `products`/`product_sources` are the write model; `ProductCatalogued`/
  `ProductUpdated` are published as a side effect of an ingestion write,
  via the Outbox pattern.
- `CatalogSourcePort`: one shared interface, two independent adapters
  (`OpenFoodFactsSourceAdapter` — file-based, no live calls;
  `UsdaFdcSourceAdapter` — live HTTP, circuit-breaker + retry + rate
  limit) feeding one shared domain-level normalization/dedup pipeline
  (`domain/services/product_normalizer.py`, `product_deduplicator.py`,
  `allergen_tag_deriver.py`) — the anticorruption layer boundary for this
  service (`docs/domain-glossary-and-context-map.md`).
- Full-text/faceted search: Postgres `tsvector` + GIN + `pg_trgm`
  (ADR-0012) — no OpenSearch/Elasticsearch.

## Deduplication and conflict resolution (implementation plan Addendum 1)

- Barcode is the **sole** cross-source dedup key — no fuzzy name+brand
  matching.
- On a genuine numeric disagreement in `nutrition_per_100g` between
  sources for the same barcode, the most-recently-updated source's value
  wins on the live `products` row; **both** sources' raw values are
  retained in `product_sources` — nothing is silently discarded.
- A product present in only one source is trusted as-is.
- Allergen (and dietary) tags are always a **union** across every known
  source for a product, never an intersection — a conservative default
  that never silently drops a safety-relevant allergen one source
  reported.

## Running locally

```
docker compose up catalog-service catalog-db catalog-redis rabbitmq
```

See root `docker-compose.yml` and `.env.example` for required environment
variables. No real ingestion run happens automatically — `run_open_food_facts_ingestion`/
`run_usda_fdc_ingestion` (`application/jobs/`) are manually triggerable
only, not wired to any scheduler (implementation plan section 9.2), and
any bulk/production-scale run requires explicit human confirmation before
execution (CLAUDE.md section 7).

## Testing

```
cd services/catalog-service
uv sync --extra dev
uv run pytest tests/unit                 # domain + application, no I/O
uv run pytest tests/integration          # testcontainers: Postgres, Redis, RabbitMQ
                                          # + hand-authored fixtures/cassettes for
                                          # the two source adapters (never live)
uv run pytest tests/contract             # HTTP + event schema contracts
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage targets (CLAUDE.md section 3): domain >= 90%, application >= 85%,
infrastructure >= 70%.

**Ingestion adapter tests never make a live HTTP call.** `OpenFoodFactsSourceAdapter`
is tested against a hand-authored sample export file
(`tests/fixtures/open_food_facts_export_samples/`, including a
deliberately malformed row). `UsdaFdcSourceAdapter` is tested against
hand-authored JSON response bodies shaped like the documented USDA FDC
Branded Foods API schema (`tests/fixtures/cassettes/usda_fdc/`, including
a 429 rate-limit response body), served via `httpx.MockTransport` — no
`vcrpy`/`pytest-recording` cassette-replay library was needed to achieve
this determinism.

## Resilience configuration

- `UsdaFdcSourceAdapter` (the only adapter making live outbound calls):
  `purgatory`-based circuit breaker (`infrastructure/external/usda_fdc/circuit_breaker.py`),
  `fail_max=5` consecutive failures, `reset_timeout=60s`. `tenacity` retry:
  exponential backoff with jitter, max 3 attempts, only for transient
  transport errors. Explicit timeout: 10s connect / 30s read. Own
  `httpx.AsyncClient` connection pool (bulkhead), isolated from any other
  outbound client.
- A proactive token-bucket rate limiter (Redis-backed,
  `catalog:usda-rate-limit:{hour_bucket}`, 1h TTL) respects USDA's
  published 1000 requests/hour/IP limit rather than relying on
  retry-after-429 alone.
- `OpenFoodFactsSourceAdapter` makes no live HTTP calls — no circuit
  breaker needed for the adapter itself.
- If the USDA circuit is open mid-run, that run's USDA phase is skipped
  for the cycle (status `circuit_open`, logged) and the OFF phase
  proceeds independently — one source's failure never blocks the other.

## Caching (`.claude/skills/caching-strategy/SKILL.md`)

- `catalog:product:{product_id}` — 24h TTL.
- `catalog:search-results:{query_hash}` — 15 min TTL.
- `ProductUpdated` -> invalidates `catalog:product:{product_id}`.
  Best-effort invalidation of cached search-result pages containing that
  product is a deliberate simplification, not attempted — acceptable
  staleness within the 15 min TTL.

## Owned events (see docs/events-catalog.md)

- `ProductCatalogued` (v1, new — renamed from the agent-doc's `ProductAdded`
  for PascalCase-past-tense precision, implementation plan section 5).
- `ProductUpdated` (v1, new).

No events consumed — `catalog-service` is a pure upstream/reference-data
source in the context map.

## Dependencies

- PostgreSQL (own logical database within the shared RDS instance;
  `pg_trgm` extension).
- Redis (search cache + USDA rate-limit counter).
- RabbitMQ (outbox relay -> `catalog.events` topic exchange).
- USDA FoodData Central API (live, rate-limited, registered key).
