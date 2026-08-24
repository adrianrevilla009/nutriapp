---
description: Internationalization conventions for both backend and frontend. Use whenever adding user-facing text, units, or locale-dependent data.
---

# Internationalization (i18n) Conventions

## Scope
NutriApp is specified to support multiple locales from the start, even if
the first implemented locale is the only one shipped initially — retrofitting
i18n later is expensive, so the seams must exist from the first service.

## Backend
- No user-facing string is hardcoded in application/domain logic. Any
  text that reaches a user (notifications, generated summaries, AI-assistant
  responses) is either data-driven (values, not prose, sent to the
  frontend for localized rendering) or resolved through a translation
  layer keyed by locale — never string-formatted in one language inside a
  domain service.
- If your domain has units of measure (weight, currency, distance, etc.):
  store and compute internally in a single canonical system regardless of
  locale. Conversion to a user's preferred display unit happens only at
  the presentation boundary (frontend, or a dedicated formatting step in
  `bff-service`), never inside domain calculations in
  `nutrition-calculation-service`.
- Reference/catalog data (`catalog-service`, if applicable) is locale-aware:
  the same item can have different names/labels per source locale. The
  domain model must support an item having multiple localized names, not
  a single name field.
- Dates, times, and number formatting follow the user's locale at the
  presentation boundary; internally, all timestamps are stored in UTC
  (ISO 8601), never a localized string.

## Frontend
- All user-facing copy goes through a translation resource layer (e.g.
  key-based lookups), never inline literal strings in components.
- Pluralization, gendered forms, and right-to-left layout support are
  accounted for in component design from the start — a component that
  only works for one grammatical pattern is not acceptable even before
  a second locale is actually implemented.
- Locale-dependent formatting (numbers, dates, units) uses the
  browser/runtime's locale APIs (or an equivalent library) rather than
  hand-rolled formatting logic.

## Domain-Specific Considerations
- Regulatory nutrition-labeling formats differ by region (e.g. daily value
  percentages, serving-size conventions, EU vs. US units). Any
  region-specific rule must be documented per region before it is
  implemented, not inferred ad hoc.
- Locale can affect which third-party/catalog sources are relevant
  (`catalog-service`); this is a data-source concern, documented per
  source in `.claude/skills/external-data-ethics/SKILL.md`, not an i18n
  concern per se — but the two must stay consistent (a product's locale
  and its available localized names must match its source region).

## Testing
- Any UI component or backend formatting function must have at least one
  test case using a non-default locale (e.g. a locale with a different
  decimal separator, unit system, or pluralization rule) to catch
  hardcoded assumptions early.
