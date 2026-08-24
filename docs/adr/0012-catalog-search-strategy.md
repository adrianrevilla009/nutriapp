# ADR-0012: Catalog Search Strategy (delete this ADR if the product has no reference/catalog data)

## Status
Accepted

## Date
2026-08-23

## Context
`catalog-service` aggregates reference items from third-party sources
(CLAUDE.md section 1). Users need to search this catalog by name and
partial match (typo-tolerant, ideally) while using the product's core
feature — a latency-sensitive, high-frequency read path. Nothing in the current stack
(`CLAUDE.md` section 4: Postgres, Redis, Qdrant) is explicitly designated
for this, and reaching for a dedicated search engine by default, before
knowing the real catalog size or query patterns, would add an operational
dependency ahead of need.

## Decision
- **Start with Postgres full-text search** (`tsvector`/`tsquery` with a
  GIN index, plus `pg_trgm` for typo-tolerant partial matching) directly in
  `catalog-service`'s read model. No new infrastructure — this is the
  read-model database `catalog-service` already has.
- **Activation condition for a dedicated search engine (OpenSearch)**:
  revisit via a new ADR once *any* of the following is measured, not
  assumed:
  - p95 catalog search latency exceeds 300ms under realistic load
    (`docs/performance-testing.md`) with Postgres full-text search already
    tuned (indexes, `EXPLAIN ANALYZE`-verified query plans).
  - The catalog exceeds roughly 500k items and query patterns need
    faceted search (filter by several attributes simultaneously) that
    `tsvector` handles poorly.
  - Multi-language search (per `.claude/skills/i18n-conventions/SKILL.md`)
    needs language-aware stemming/tokenization beyond Postgres's built-in
    text search configurations.
- If activated, **OpenSearch** (Apache 2.0, AWS-managed option available)
  is the default choice over Elasticsearch, consistent with the project's
  preference for open-licensed/self-hostable tooling seen throughout
  `docs/mcp-servers.md`.

## Considered Alternatives
- **OpenSearch from day one** — better search UX (relevance ranking,
  faceting, typo tolerance) out of the box, but a new stateful service to
  operate, back up (`docs/backup-and-disaster-recovery.md`), and secure
  before there's any evidence Postgres full-text search is insufficient.
  Rejected for now per the project's general bias (see ADR-0006, ADR-0008)
  toward not adding infrastructure ahead of a measured need.
- **Meilisearch/Typesense** — lighter-weight, easier to self-host than
  OpenSearch, good typo tolerance out of the box. A reasonable alternative
  if/when the activation condition above is met; note as a considered
  option in the future ADR that activates a dedicated search engine,
  rather than deciding between them now with no real query-pattern data.
- **Algolia (managed, paid)** — best-in-class search UX, but a paid
  external vendor for a capability free/open alternatives can plausibly
  cover; rejected by the same free-alternative-first pattern in
  `docs/mcp-servers.md`.

## Consequences
### Positive
- Zero new infrastructure until real usage data justifies it.
- `catalog-service` keeps a single database to operate/back up/secure.

### Negative / Trade-offs
- Postgres full-text search's relevance ranking and typo tolerance are
  weaker than a purpose-built search engine; acceptable for launch-scale
  catalog size.
- If the activation condition is met, migrating search introduces a data
  sync pipeline (Postgres -> OpenSearch) that doesn't exist today —
  tracked as a known future cost, not a reason to over-build now.

### Follow-up actions
- Add `pg_trgm` and a GIN `tsvector` index to `catalog-service`'s schema
  when it is scaffolded.
- Add catalog search p95 latency as a tracked SLI in
  `docs/observability-slo.md` once the service exists, so the activation
  condition above is actually measured, not guessed at.

## References
- `docs/performance-testing.md`
- `docs/observability-slo.md`
- CLAUDE.md section 4
