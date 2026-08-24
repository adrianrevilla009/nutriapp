# API Standards

Full policy behind the day-to-day conventions in
`.claude/skills/api-conventions/SKILL.md` and the gateway split defined in
ADR-0008. This document governs the *lifecycle and organization-wide rules*
for APIs; the skill governs *how to write one endpoint*.

## 1. Public vs. Internal APIs

- **Public API**: exposed through Kong to the frontend and (eventually) any
  third-party integration. Only the BFF's endpoints and any explicitly
  designated public service endpoint are public.
- **Internal API**: service-to-service calls inside the cluster, never routed
  through Kong, reachable only via NetworkPolicy-permitted paths. Internal
  APIs still follow the same conventions (versioning, error shape, OpenAPI)
  because internal contracts break just as expensively as external ones.

## 2. Versioning & Deprecation

- URL-path versioning (`/api/v1/...`), per
  `.claude/skills/api-conventions/SKILL.md`.
- A version is deprecated, never deleted outright:
  1. New version (`v2`) ships alongside `v1`.
  2. `v1` responses include a `Sunset` header (RFC 8594) with the planned
     removal date, and `Deprecation: true`.
  3. Deprecation is announced in `docs/api-catalog.md` and, for
     externally-consumed APIs, in a `CHANGELOG.md` at the repo root.
  4. Minimum deprecation window: 90 days for internal consumers, 180 days for
     any external/public consumer, before `v1` is removed.
- A schema change that is **additive and backward-compatible** (new optional
  field, new endpoint) does not require a version bump — only breaking
  changes (removed/renamed field, changed type, changed status code
  semantics) do.

## 3. Error Format (RFC 7807-inspired)

Standard shape across all services, extending the base shape in the
conventions skill with machine-readable detail for programmatic clients:
```json
{
  "error": "The requested item was not found",
  "code": "ITEM_NOT_FOUND",
  "status": 404,
  "correlation_id": "b3f1...",
  "details": {}
}
```
`code` values are stable identifiers, documented per-service in that
service's `README.md`, and must not change once shipped (treat as part of the
public contract).

## 4. Rate Limiting

Enforced at the Kong gateway (ADR-0008), not hand-rolled per service:
- Default: per-API-key/IP sliding window, tuned per endpoint class.
- Stricter limits on authentication-adjacent endpoints (login, password
  reset, registration) — see `docs/security-and-compliance.md` section 1.
- `food-recognition-service`'s photo-upload endpoint and `nutrition-assistant-service`'s chat
  endpoint get separate, lower limits given their higher per-request cost
  (external API calls billed per use).
- Rate-limit responses use `429` with a `Retry-After` header.

## 5. Idempotency

Per `.claude/skills/api-conventions/SKILL.md`: any endpoint with a side
effect that a client might retry must support an `Idempotency-Key`. The
server stores the key (with a TTL, e.g. 24h) and returns the original
response for a repeated key rather than re-executing the side effect. Backed
by the same deduplication mechanism used for message consumers (CLAUDE.md
2.4) where practical, to avoid two separate idempotency implementations.

## 6. Backward Compatibility Testing

- Contract tests (per `docs/testing-strategy.md` section 2.3) run against
  both the current and previous API version whenever both are live, to catch
  accidental breakage of a deprecated-but-still-supported version.
- Consumer-driven contract tests: any service that consumes another
  service's API maintains a contract test that fails the *provider's* CI if
  the provider's response shape would break it (Pact or equivalent).

## 7. Documentation & Discoverability

- Every public and internal API is listed in `docs/api-catalog.md` with its
  version, owning service, and current deprecation status.
- OpenAPI specs are served at `/api/v{n}/openapi.json` per service and
  aggregated at the Kong layer for a single browsable API portal (Redocly),
  per CLAUDE.md section 10.
