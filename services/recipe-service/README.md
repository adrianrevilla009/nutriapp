# recipe-service

User recipe authoring (ingredients drawn from `catalog-service` products,
with quantities), computed per-recipe/per-serving macro/micro nutrient
totals, Pro-gated publishing to cross-user search, and Pro-gated
cross-user recipe search (CLAUDE.md section 2.2, `.claude/agents/recipe-agent.md`).

## Bounded context

See `.claude/agents/recipe-agent.md` and
`/plans/recipe-service/implementation-plan.md`.

## Architecture

Hexagonal (`domain/` -> `application/` -> `infrastructure/`, ADR-0001).
Event-driven CRUD (ADR-0002) -- `Recipe` is stored conventionally (one row
per recipe, soft-unpublished on removal from search, never a hard row
delete), not event-sourced. Domain events are published as a side effect
via the Outbox pattern.

Nutrient computation (`domain/services/recipe_nutrient_calculator.py`) is
this service's OWN copy of `nutrition-calculation-service`'s per-100g x
quantity formula (never a cross-service import, CLAUDE.md section 2.5),
tested against the shared, hand-computed reference fixture
`packages/shared-contracts/fixtures/nutrient_calculation_reference_cases.json`.
Computed totals are ALWAYS derived server-side from ingredient data --
never accepted as user input, not even optionally (recipe-agent.md).

## Published events (v1)

`RecipeCreated`, `RecipeUpdated`, `RecipePublished`, `RecipeUnpublished`
(new, added by this plan) -- see `docs/events-catalog.md` for payload
schemas. Consumers (`analytics-service`/`nutrition-assistant-service`) are
documented as future, not-yet-implemented (neither service exists yet) --
same deferral pattern used elsewhere in this codebase.

## Consumed events (v1)

`EntitlementGranted`/`EntitlementRevoked` (`billing-service`) -- the
FIRST real consumer of these two events in this codebase, implementing
this service's side of the `ProUpgradeEntitlementPropagation` saga's
fan-out (`docs/sagas-and-distributed-transactions.md`). Idempotent by
`event_id` (`processed_entitlement_events` table); upserts the local
`entitlement_cache` read table.

## Public API

JWT-authenticated (ADR-0022, `packages/shared-contracts`' centralized
auth dependency) throughout.

- `POST /api/v1/recipes` -- author a recipe. Not Pro-gated.
- `PATCH /api/v1/recipes/{recipe_id}` -- edit your own recipe, recomputes
  totals. Not Pro-gated.
- `GET /api/v1/recipes/{recipe_id}` -- read your own recipe (including
  drafts). Not Pro-gated.
- `GET /api/v1/recipes?mine=true` -- list your own recipes, including
  drafts. Not Pro-gated.
- `POST /api/v1/recipes/{recipe_id}/publish` -- **Pro-gated.** Blocks if
  any ingredient no longer resolves against `catalog-service` at publish
  time (re-verified fresh, never trusted from creation time).
- `POST /api/v1/recipes/{recipe_id}/unpublish` / `DELETE /api/v1/recipes/{recipe_id}`
  -- soft-unpublish only, never a hard row delete. Idempotent.
- `GET /api/v1/recipes/search?q=...` -- **Pro-gated.** Full-text search
  over published recipes only, never a draft/unpublished recipe.

**Entitlement-rejection status code**: `402 Payment Required`, code
`NOT_ENTITLED` -- documented decision in
`infrastructure/http/error_mapping.py` (no existing Pro-gated precedent
existed in this codebase to follow; this is the first Pro-gated feature
built).

## Entitlement gating (implementation plan section 1.7)

Cache-first: `entitlement_cache` table (populated by consuming
`EntitlementGranted`/`EntitlementRevoked`), checked first on every
publish/search request. On a genuine cache MISS (no row yet for that
user), falls back to `billing-service`'s synchronous
`GET /internal/v1/billing/entitlements/{user_id}` (own circuit breaker,
`billing_entitlement_check`) -- **the fallback result is never written
back into the cache** (`application/entitlement_check.py`'s
`is_user_entitled` has no reference to the cache's write method at all --
a structural guarantee, not just a discipline). A fallback-check failure
fails SAFE (not entitled), never fail open.

## Resilience

Two independently-named circuit breakers, never sharing state:

| Integration                                    | Circuit name              | fail_max | reset_timeout |
|--------------------------------------------------|------------------------------|------------|------------------|
| `catalog-service` product lookup (per ingredient) | `catalog_product_lookup`     | 5          | 30s              |
| `billing-service` entitlement check (cache-miss fallback only) | `billing_entitlement_check` | 5 | 30s |

## Testing

`docs/testing-strategy.md`. `CatalogProductClient`/`BillingEntitlementClient`
are tested entirely against `httpx.MockTransport` fixtures -- **zero live
calls to catalog-service or billing-service anywhere in this test suite.**
Run:

```
uv run pytest tests/unit -q
uv run pytest tests/integration tests/contract -q
uv run pytest --cov=domain --cov=application --cov=infrastructure --cov-report=term-missing
```

Coverage floors: domain >= 90%, application >= 85%, infrastructure >= 70%.

## Dependency note

Built against `billing-service`'s PR #23 (Stripe subscriptions,
entitlements) event/endpoint contracts -- `billing-service`'s PR must be
merged before or alongside this service's own PR.
