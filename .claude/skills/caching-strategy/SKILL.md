---
description: Redis caching conventions for NutriApp — cache-aside pattern, key namespacing, TTLs, and event-driven invalidation. Use whenever adding a cache to any read path.
---

# Caching Strategy — NutriApp Conventions

Full rationale in CLAUDE.md section 2.7.

## Pattern
Cache-aside by default: on read, check Redis first; on a miss, read from the
source of truth, populate the cache, then return. Write-through (updating the
cache synchronously on write) is reserved for cases where any staleness is
unacceptable — document that choice explicitly where used.

## Key Namespacing
`{service}:{entity}:{identifier}[:{sub-resource}]`, e.g.:
- `diary:daily-summary:{user_id}:{date}`
- `catalog:product:{product_id}`
- `nutrition:current-target:{user_id}`

## TTLs (defaults — override per key namespace with justification)
| Namespace                          | TTL        | Rationale                                  |
|--------------------------------------|------------|-----------------------------------------------|
| `diary:daily-summary:*`              | 5 minutes  | Frequently updated intra-day, short staleness ok |
| `catalog:product:*`                | 24 hours   | Reference data changes infrequently             |
| `nutrition:current-target:*`         | 1 hour     | Changes only on profile/goal updates            |
| `catalog:search-results:*`           | 15 minutes | Balance freshness vs. scrape load               |

### Non-Redis exception: in-process JWKS cache

The JWT-verification helper (`shared_contracts.auth.jwt_verifier.JwtVerifier`,
ADR-0022) caches a producing service's fetched JWKS document **in-process**,
not in Redis — it is hot-path cryptographic key material needed
synchronously on every authenticated request, and a Redis round trip on
every request would reintroduce exactly the per-request network dependency
JWKS local verification exists to avoid. The same explicit-TTL discipline
still applies: 10 minutes by default (`DEFAULT_JWKS_CACHE_TTL_SECONDS`),
long enough to avoid hammering the JWKS endpoint, short enough that a key
rotation is picked up within a bounded window rather than requiring a
process restart (ADR-0022's "consumers must not cache the JWKS response
indefinitely"). `profile-service` is the first consumer
(`services/profile-service/infrastructure/http/dependencies.py`).

## Event-Driven Invalidation
Prefer invalidating a cache key in response to the domain event that makes it
stale, rather than relying solely on TTL expiry:
- `FoodEntryLogged` -> invalidate `diary:daily-summary:{user_id}:{date}`.
- `ProductUpdated` -> invalidate `catalog:product:{product_id}`.
- `NutritionTargetUpdated` -> invalidate `nutrition:current-target:{user_id}`.

TTL remains as a safety net in case an invalidation is ever missed, but should
not be the primary invalidation mechanism for data with a clear triggering
event.

## Rules
- Never cache personal data with a TTL longer than necessary for its use case;
  cached data is still subject to the deletion requirements in
  `docs/security-and-compliance.md` — a user data deletion request must also
  purge relevant cache entries, not just the source-of-truth database.
- Never use the cache as the source of truth for anything — it must always be
  safe to flush the entire cache and rebuild it from source without data loss.

## Testing Requirements
- Unit/integration tests cover: cache hit path, cache miss path (falls
  through to source and populates cache), and invalidation on the relevant
  domain event.
