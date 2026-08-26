# catalog-service — agent-scoped notes

This file is scoped guidance for any agent working inside
`services/catalog-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/catalog-agent.md`
(bounded context, domain responsibilities, rules) — read both first, and
read `.claude/skills/external-data-ethics/SKILL.md` before touching any
source integration — it is mandatory, non-negotiable reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001).
- Conventional persistence + Outbox (ADR-0002, CLAUDE.md section 2.4) —
  not event-sourced. This is the second service (after `identity-service`)
  to validate that shape, and the first under a multi-source ingestion
  write path rather than direct user action.
- `CatalogSourcePort` (`domain/ports/catalog_source_port.py`) is the
  multi-source pluggable ingestion abstraction: N adapters -> 1 shared
  domain-level normalization/dedup service. If a future service needs
  the same N-adapters-to-1-domain-service shape (e.g. `activity-service`'s
  planned multi-wearable-provider ingestion), copy this shape, not a
  bespoke one.
- Barcode is the sole cross-source dedup key (Addendum 1 to the
  implementation plan) — never add fuzzy name+brand matching without a
  new, explicit human-approved decision; the false-merge risk for data
  feeding nutrition calculations downstream is real.
- **Zero live HTTP calls in tests, ever.** `OpenFoodFactsSourceAdapter`
  reads a file; `UsdaFdcSourceAdapter` tests use `httpx.MockTransport`
  fed from hand-authored fixture bodies in `tests/fixtures/cassettes/usda_fdc/`.
  Never add a test that calls the real Open Food Facts or USDA FDC host.
- Any bulk/production-scale ingestion run requires explicit human
  confirmation immediately before that specific execution (CLAUDE.md
  section 7, restated in `.claude/agents/catalog-agent.md`) — this is a
  standing constraint on every future run, not a one-time approval.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s).
- Adapters: `infrastructure/persistence/`, `infrastructure/caching/`,
  `infrastructure/messaging/`, `infrastructure/external/`.
- Composition root: `infrastructure/composition_root.py` — the only place
  concrete adapters are wired to ports.
- Anticorruption layer: `domain/services/product_normalizer.py`,
  `product_deduplicator.py`, `allergen_tag_deriver.py` — arbitrary
  third-party data quality is contained here, never leaks past it as a
  domain `Product`/`NutrientPanel`/etc. that hasn't already degraded
  gracefully (coerce, drop, or `None`, never raise for anything short of
  a genuinely empty/unidentifiable record).
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`.

## If a source's structure changes and breaks a parser

Report it clearly (which source, what changed, what broke) rather than
forcing a brittle workaround that might silently produce wrong nutrition
data — per `.claude/skills/external-data-ethics/SKILL.md`'s "Source
Fragility" section and `.claude/agents/catalog-agent.md`'s rules.
