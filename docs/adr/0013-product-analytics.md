# ADR-0013: Product Analytics

## Status
Accepted

## Date
2026-08-23

## Context
`analytics-service` (CLAUDE.md section 5) computes **domain**
analytics for users — trends, anomalies — from domain events. That is a
distinct concern from **product analytics**: understanding user behavior
(funnel drop-off during onboarding, feature adoption, retention cohorts) to
inform product decisions. Nothing in the current stack covers this, and
conflating the two inside `analytics-service` would pollute a
domain-focused service with an unrelated, cross-cutting concern.

## Decision
- Adopt **self-hosted PostHog** (open-source, Postgres/ClickHouse-backed)
  for product analytics, following the same free/self-hosted-by-default
  pattern already used throughout `docs/mcp-servers.md` (Prometheus/Grafana
  over Datadog, GlitchTip over Sentry).
- Product analytics is emitted from the **frontend** (page views, feature
  interactions) and, for server-side events that matter for product
  decisions (e.g. "core action performed" as a retention signal, not its
  domain-specific content), via a thin event-forwarding adapter in
  `bff-service` —
  never by having every domain service take on a PostHog dependency
  directly.
- **Status**: Disabled (specified), same convention as `docs/mcp-servers.md`
  entries — activated once `frontend/` exists and there's a concrete
  product question (onboarding funnel, feature adoption) to answer, not
  speculatively from day one.

## Considered Alternatives
- **Amplitude / Mixpanel (paid, managed)** — more polished analysis UX and
  no self-hosting burden, but a recurring paid cost and a third-party data
  processor to add to `docs/data-protection-and-privacy.md`'s already
  careful handling of any sensitive personal data. Rejected by default for the
  same reason the project prefers GlitchTip/Prometheus over their paid
  equivalents; revisit via a new ADR if self-hosted PostHog's operational
  burden outweighs its cost savings at scale.
- **No product analytics, decisions from qualitative feedback only** —
  what exists today. Rejected: the product roadmap will need quantitative
  signal (onboarding drop-off, feature adoption) that qualitative feedback
  alone under-represents.
- **Building event tracking into `analytics-service`** — rejected per the
  Context above: conflates a domain-specific concern with a
  product-behavior concern that has different consumers (product/growth
  vs. `nutrition-assistant-service`/`core-domain-agent`) and different
  data-sensitivity handling.

## Consequences
### Positive
- Product decisions get quantitative grounding without adding a paid
  vendor or polluting `analytics-service`'s domain focus.
- Self-hosted keeps user behavior data inside the project's own
  infrastructure boundary, simplifying the data-protection story.

### Negative / Trade-offs
- One more self-hosted stateful service to operate and back up.
- Self-hosted PostHog's analysis UX lags the managed paid competitors
  somewhat; acceptable trade-off given the cost and data-locality benefit.

### Follow-up actions
- Add PostHog as an entry in `docs/mcp-servers.md`'s catalog pattern once
  `frontend/` exists (an MCP for querying PostHog data during development,
  same free/paid framing as entry 6/7 there).
- Define the specific events tracked (and explicitly which are *not*
  tracked, e.g. nothing from sensitive domain content — behavior events
  only) in a follow-up doc once activated.

## References
- `docs/data-protection-and-privacy.md`
- `docs/mcp-servers.md`
- CLAUDE.md section 5
