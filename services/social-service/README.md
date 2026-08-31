# social-service

One-way follow connections between users and a Pro-gated activity feed
composed from followed users' published recipes (CLAUDE.md section 2.2,
`.claude/agents/social-agent.md`).

## Bounded context

See `.claude/agents/social-agent.md` and
`/plans/social-service/implementation-plan.md`.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001).
Event-driven CRUD (ADR-0002) -- `Follow` is a conventional row per
follower/followee pair, `feed_entries` is a simple event-projected read
table, not event-sourced. Domain events are published as a side effect via
the Outbox pattern.

**Follow semantics**: one-way, no approval required. Self-follow is
rejected structurally (`domain/entities/follow.py`'s `__post_init__`).
Unfollow is a genuine HARD delete of the `Follow` row -- unlike
`recipe-service`'s soft-unpublish-only convention, a follow relationship
has no history value once ended (a deliberate, confirmed deviation, see
`/plans/social-service/implementation-plan.md` section 1).

**Feed composition**: fan-out-on-read, NOT bff-service aggregation. This
service consumes `recipe-service`'s `RecipePublished`/`RecipeUnpublished`
into its own local `feed_entries` projection (`recipe_id`, `author_id`,
`title`, `published_at` -- never the full recipe). `GET /feed` joins this
table against the caller's own `follows` table. No circuit breaker or
synchronous call to `recipe-service` anywhere -- feed composition is
entirely async via consumed events.

**Known, flagged gap**: `RecipePublished` (v1), as actually published by
`recipe-service` today, does NOT carry a `title` field (`packages/shared-
contracts/schemas/recipe_published.v1.json` is `{recipe_id, user_id,
published_at}` only). `feed_entries.title` is therefore `None` for every
entry today -- see `domain/value_objects/feed_entry.py`'s docstring for
the full reasoning and the recommended follow-up (a `RecipePublished` v2
adding `title`, out of scope for this plan since it requires reopening
the already-merged `recipe-service`).

## Published events (v1)

`UserFollowed`, `UserUnfollowed` -- see `docs/events-catalog.md` for
payload schemas. `UserFollowed` has a real, live consumer
(`notification-service`'s `social_events_consumer.py`, PR A of this
initiative) -- `UserUnfollowed` is documented as consumed only by
`analytics-service` (not yet implemented).

## Consumed events (v1)

- `EntitlementGranted`/`EntitlementRevoked` (`billing-service`) -- the
  SECOND real consumer of these two events (after `recipe-service`),
  implementing this service's side of the `ProUpgradeEntitlementPropagation`
  saga's fan-out. Idempotent by `event_id` (`processed_entitlement_events`
  table); upserts the local `entitlement_cache` read table.
- `RecipePublished`/`RecipeUnpublished` (`recipe-service`) -- the FIRST
  real consumer of either event in this codebase. Idempotent by `event_id`
  (`processed_recipe_events` table, an INDEPENDENT ledger from
  `processed_entitlement_events`); upserts/removes `feed_entries` rows.
  `RecipeUnpublished` removal happens synchronously with consumption, not
  a scheduled recompute.

## Public API

JWT-authenticated (ADR-0022, `packages/shared-contracts`' centralized
auth dependency) throughout.

- `POST /api/v1/social/follows` -- follow another user. **Pro-gated.**
  Rejects self-follow (422/`SELF_FOLLOW`). Idempotent (already-following
  returns the existing row, 201, no duplicate event).
- `DELETE /api/v1/social/follows/{followee_id}` -- unfollow. **Pro-gated.**
  Hard delete. Idempotent (not-following is a no-op, 204, no event).
- `GET /api/v1/social/follows/following` / `.../followers` -- list who you
  follow / who follows you. Not Pro-gated.
- `GET /api/v1/social/feed` -- **Pro-gated.** Activity feed of followed
  users' published recipes, newest first.

**Entitlement-rejection status code**: `402 Payment Required`, code
`NOT_ENTITLED` -- reuses `recipe-service`'s exact convention verbatim, now
a repo-wide standard (`infrastructure/http/error_mapping.py`).

## Entitlement gating (implementation plan section 1.2)

Cache-first: `entitlement_cache` table (populated by consuming
`EntitlementGranted`/`EntitlementRevoked`), checked first on every
follow/unfollow/feed request. On a genuine cache MISS, falls back to
`billing-service`'s synchronous
`GET /internal/v1/billing/entitlements/{user_id}` (own circuit breaker,
`billing_entitlement_check`) -- **the fallback result is never written
back into the cache** (`application/entitlement_check.py`'s
`is_user_entitled` has no reference to the cache's write method at all).
A fallback-check failure fails SAFE (not entitled), never fail open.

Gates the *acting* user (the follower, or the feed viewer) -- the
followee's own entitlement is irrelevant. Revocation
(`HandleEntitlementRevokedHandler`) only flips the cached flag -- it never
deletes or hides existing `follows`/`feed_entries` rows (non-destructive,
structurally guarded -- that handler has no reference to
`FollowRepositoryPort` at all).

## Resilience

One circuit breaker, mirroring `recipe-service`'s pattern:

| Integration                                                    | Circuit name              | fail_max | reset_timeout |
|------------------------------------------------------------------|------------------------------|------------|------------------|
| `billing-service` entitlement check (cache-miss fallback only) | `billing_entitlement_check` | 5          | 30s              |

No `recipe-service` circuit breaker -- there is no synchronous call to
`recipe-service` anywhere (feed composition is entirely async via consumed
events).

## Testing

`docs/testing-strategy.md`. `BillingEntitlementClient` is tested entirely
against `httpx.MockTransport` fixtures -- **zero live calls to
billing-service or recipe-service anywhere in this test suite.** Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.

## Dependency note

Depends on `notification-service`'s coordinated PR A (adding
`social_events_consumer.py`, per `/plans/social-service/implementation-plan.md`
section 6) landing first or alongside this service's own PR, so
`UserFollowed` is never live with zero consumers even transiently.
