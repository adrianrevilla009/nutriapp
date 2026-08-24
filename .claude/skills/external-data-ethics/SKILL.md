---
description: Ethical and technical rules for ingesting third-party supermarket product data into NutriApp. Use whenever touching catalog-service or adding a new supermarket API/source.
---

# Ethical External Data Acquisition — Conventions

## Before Ingesting Any New Source
1. Check `robots.txt` for the domain (if scraping).
2. Check whether an official public API exists before resorting to HTML
   scraping.
3. Check the source's terms of service — if automated collection is
   explicitly prohibited, do not proceed with this source; document the
   source as unavailable rather than working around the restriction.

## Technical Best Practices
- Rate limiting: respect any published rate limit or `Retry-After` header;
  default to a conservative minimum delay between requests to the same
  source if none is published.
- Identifiable `User-Agent` — do not spoof a browser identity unless
  strictly necessary and justified in the implementation plan.
- Cache aggressively (Redis, TTL per
  `.claude/skills/caching-strategy/SKILL.md`) — never repeat a request whose
  result is still valid.
- Wrap every ingestion call in the resilience patterns defined in
  `.claude/skills/resilience-patterns/SKILL.md` (circuit breaker, retry with
  backoff, explicit timeout) — a failing source must degrade gracefully,
  never cause a tight retry loop.

## Data Scope
- **Collect**: product name, brand, barcode/GTIN, nutrition-facts panel
  (macro/micronutrients per 100g), category, dietary/allergen tags, price,
  and package size — the fields `catalog-service` search, `diary-service`
  logging, and `nutrition-calculation-service` computation actually need.
- **Never collect**: anything identifying a person (names, profile photos,
  reviews attributed to individuals, etc.), even if technically present in
  the source's markup, unless the purpose explicitly requires it and the
  data is anonymized first — and only if that is an actual, deliberate
  requirement for this project, documented in an ADR.

## Bulk Ingestion Runs
Any ingestion run beyond a small, ad-hoc test fetch (i.e. a scheduled or
production-scale catalog refresh) requires explicit human confirmation before
execution — enforced by `.claude/hooks/pre-bash-guard.sh`, but state this
explicitly in the implementation plan regardless.

## Source Fragility
If a source changes its structure or API shape and breaks the parser,
report this clearly (which source, what changed, what broke) rather than
forcing a brittle workaround that may silently produce wrong data.

## Testing
- Ingestion adapters are tested against recorded fixture responses
  (VCR-style cassettes), never against the live source in CI —
  deterministic, fast, and does not add load to the real source.
- Normalization and deduplication logic (domain layer) is unit tested with a
  wide range of malformed/partial input fixtures.
