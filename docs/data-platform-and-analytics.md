# Data Platform & Analytics

This document separates **three distinct analytics concerns** that this
repo already touches individually but never distinguished explicitly —
conflating them (as ADR-0013 already warns against for the first two)
leads to the wrong team/service owning the wrong data with the wrong
sensitivity handling.

## 1. Domain Analytics (owned by `analytics-service`)

Trends, anomalies, and reports computed **from the product's own domain
events** for the *end user's* benefit (e.g. "your usage trend this
month"). Already fully specified: CLAUDE.md section 5,
`.claude/agents/analytics-agent.md`, `docs/events-catalog.md`. Not
duplicated here.

## 2. Product Analytics (owned by a `bff-service` forwarding adapter)

User behavior instrumentation (funnel drop-off, feature adoption,
retention) for the *product team's* benefit, not the end user's. Already
specified in ADR-0013 (self-hosted PostHog). Not duplicated here.

## 3. Data Warehouse / BI (new — this is the actual gap)

For questions neither of the above answers well: cross-service historical
analysis, executive reporting, ad-hoc SQL exploration across the whole
product's data, or feeding a future ML training pipeline. Distinct from
both above because it needs data **joined across every service's
database**, which none of the per-service read models are designed to
do (CLAUDE.md section 2.5: one database per service, by design).

### 3.1 Activation Condition
**Not built until a concrete question needs it** — same measured-need
discipline as ADR-0012. Typical triggers: a recurring executive/investor
reporting need that requires joining 3+ services' data, or the first ML
feature that needs historical training data assembled across services.

### 3.2 Architecture (once activated)
- **ELT, not ETL**: extract each service's relevant data (via its
  existing read-model/event stream, never a direct write-database
  connection — that would violate the one-database-per-service
  boundary) into a dedicated analytical store, then transform there.
- **Storage**: start with a single Postgres-compatible analytical
  extension (e.g. a read-optimized schema, or DuckDB for local/ad-hoc
  analysis) before reaching for a dedicated warehouse (ClickHouse,
  Snowflake, BigQuery) — same "don't add infrastructure ahead of
  measured need" pattern as ADR-0012.
- **Ingestion**: consume the same domain events already flowing through
  RabbitMQ (CLAUDE.md section 2.4) via a dedicated, low-priority
  consumer — never query a service's operational database directly for
  warehouse loading, which would create an undocumented coupling and a
  performance risk to the operational path.
- **PII handling**: any warehouse ingestion pipeline touching data
  covered by `docs/data-protection-and-privacy.md` must apply the same
  minimization principle — pseudonymize or exclude fields not needed for
  the specific analytical question, and honor the right-to-erasure flow
  (section 4 of that doc) by propagating deletions into the warehouse,
  not treating it as a permanent, un-erasable copy.

### 3.3 Testing & Ownership
- Data pipeline correctness (row counts, referential consistency across
  ingested services) is tested the same way an event-consumer's
  idempotency is tested elsewhere in this repo — a known input event
  stream produces a known warehouse state.
- Owned by `analytics-agent` if the warehouse is primarily used for
  domain reporting, or a new dedicated agent if the scope grows large
  enough to warrant one — do not silently expand `analytics-service`'s
  bounded context to include warehouse ETL without an ADR, since that
  conflates "domain analytics for users" with "cross-service BI for the
  business," the exact conflation ADR-0013 already warns against for
  product analytics.

## 4. Data Contracts

Whichever of the three above consumes another service's data, it does so
against that service's **documented, versioned** event schema
(`docs/events-catalog.md`) — never an undocumented internal table shape.
A breaking change to an event schema (CLAUDE.md section 2.3: new version +
upcaster, never in-place mutation) is the formal data contract this
entire section relies on; treat a schema change without following that
process as breaking every downstream analytics consumer silently, not
just the operational consumers it was designed to protect.
