# Test Plan — `recipe-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/recipe-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases

**Value objects:**
- `RecipeIngredient(catalog_product_id, quantity_grams)` — `quantity_grams <= 0` raises.
- `Servings(0)` raises (must be positive); `Servings(1)` accepted.
- `NutrientTotals` — mirrors `nutrition-calculation-service`'s `MacroAmounts`/micronutrient-status shape; a `partial` status arises when some ingredients resolve micronutrients and others don't.

**`recipe_nutrient_calculator.py`** (pure function, against `packages/shared-contracts/fixtures/nutrient_calculation_reference_cases.json`):
- For each hand-computed reference case in the shared fixture: per-recipe totals match the documented expected values exactly (macros); per-serving totals equal per-recipe totals divided by `servings`.
- An ingredient with no micronutrient data available → recipe-level micronutrient status is `partial` (not silently `available` or `unavailable`) when at least one other ingredient does have data, `unavailable` when none do.
- Zero ingredients (a recipe mid-creation before any are added, if the domain allows it) → zero totals, never a division error.

**`CreateRecipeHandler`** (fake `CatalogProductPort`, fake repository, fake outbox):
- All ingredients resolve → recipe persisted with computed totals, `RecipeCreated` published with the computed totals in its payload (never user-supplied totals — confirms the handler's signature doesn't even accept a totals parameter from the caller, a structural guard).
- An ingredient's `catalog_product_id` doesn't resolve (fake port raises not-found) → recipe creation rejected with a typed error, no partial recipe persisted, no event published.

**`UpdateRecipeHandler`:**
- Valid ingredient-list change → totals recomputed, persisted change reflected, `RecipeUpdated` published exactly once.
- Editing a recipe not owned by the caller → typed not-found error (never leak existence of another user's recipe), no write attempted.

**`PublishRecipeHandler`** (fake `CatalogProductPort`, fake `EntitlementCacheRepositoryPort`, fake `EntitlementCheckPort`):
- Entitled user (cache hit, `entitled=True`), all ingredients still resolve → `is_published=True`, `RecipePublished` published.
- Entitled user, but one ingredient no longer resolves (product removed from catalog since creation) → publish rejected with a typed error, recipe remains unpublished, no event published (never publishes incomplete data — `recipe-agent.md`'s explicit rule).
- Unentitled user (cache hit, `entitled=False`) → publish rejected with a typed "not entitled" error before any ingredient-resolution call is attempted (assert the fake `CatalogProductPort` is never called — entitlement is checked first, cheapest check wins).
- No cache entry yet for this user → falls back to `EntitlementCheckPort` (the billing-service call); a `True` result proceeds, a `False` result rejects — either way, the fallback result is **not** written into `entitlement_cache` (confirms the handler never calls the cache-repository's write method in this path — a structural assertion per implementation-plan.md §1.7).

**`UnpublishRecipeHandler`/`DeleteRecipeHandler`:**
- Published recipe → unpublished (flag set, never a hard row delete — assert the fake repository's delete method is never called), `RecipeUnpublished` published.
- Already-unpublished recipe → idempotent no-op (no duplicate `RecipeUnpublished`).
- Never-published recipe (draft) → delete/unpublish succeeds without publishing `RecipeUnpublished` (nothing to announce — it was never in search).

**`SearchPublishedRecipesHandler`:**
- Entitled user (cache hit) → search executes, returns matching published recipes only (never an unpublished/draft recipe, even the searching user's own draft).
- Unentitled user → search rejected before any repository query is attempted (same cheapest-check-first pattern as publish).

**`HandleEntitlementGrantedHandler`/`HandleEntitlementRevokedHandler`** (fake `ProcessedEntitlementEventsRepositoryPort`, fake `EntitlementCacheRepositoryPort`):
- Valid event → cache row upserted (`entitled=True`/`False` respectively), event marked processed.
- Same `event_id` processed twice → second call is a no-op (idempotency check short-circuits before any cache write) — verified by asserting the fake cache-repository's write method is called exactly once total across both invocations.

## 2. Integration test cases

- `CatalogProductClient` — against a fixture HTTP server standing in for `catalog-service`'s public product endpoint: valid `product_id` → product with `nutrition_per_100g` returned; unknown `product_id` → explicit not-found (mapped, not raised as unhandled); simulated repeated failures trip the `catalog_product_lookup` circuit breaker (call-count assertions, recovery verified after `reset_timeout`, per `resilience-patterns/SKILL.md` §Testing Requirements).
- `BillingEntitlementClient` — against a fixture HTTP server standing in for `billing-service`'s internal endpoint: valid credential + entitled user → `True`; valid credential + unentitled user → `False`; invalid/missing credential handling; simulated repeated failures trip the independently-named `billing_entitlement_check` breaker (never sharing state with `catalog_product_lookup`, verified by a call-count assertion with one breaker open and the other still reaching its own fixture server).
- Postgres repositories (`recipes`, `entitlement_cache`, `processed_entitlement_events`, `outbox`) — round-trip persistence via testcontainers Postgres, same convention as every other service.
- `billing_events_consumer` — against a real (testcontainers) RabbitMQ: publishing the same `EntitlementGranted`/`EntitlementRevoked` event twice results in exactly one cache upsert (idempotency test, per `messaging-conventions/SKILL.md` §Testing Requirements); a handler that raises is nacked/requeued up to the configured limit, then dead-lettered.
- Outbox relay worker — appending an event and the outbox row happens atomically; a simulated failure after the DB write but before the publish must not lose the event (still relayed on retry).
- Alembic migration `0001` applies cleanly to an empty database.

## 3. Contract test cases

- `POST /api/v1/recipes` — `201` with computed totals for a valid payload with resolvable ingredients; `422` for an unresolvable ingredient or invalid servings/quantity; `401` unauthenticated.
- `PATCH /api/v1/recipes/{recipe_id}` — `200` on valid update with recomputed totals; `404` for a non-existent or another user's recipe.
- `GET /api/v1/recipes/{recipe_id}` / `GET /api/v1/recipes?mine=true` — `200` with own recipe(s) including drafts; `404`/empty-list appropriately for another user's recipes.
- `POST /api/v1/recipes/{recipe_id}/publish` — `200` for an entitled user with all ingredients resolvable; `402`/`403` (whichever this codebase's convention is for "not entitled" — confirm against an existing Pro-gated precedent if one exists, otherwise document the choice) for an unentitled user; `422` for an unresolvable ingredient.
- `POST /api/v1/recipes/{recipe_id}/unpublish`, `DELETE /api/v1/recipes/{recipe_id}` — `200`/`204` on success; idempotent on a second call.
- `GET /api/v1/recipes/search?q=...` — `200` with matching published recipes for an entitled user; `402`/`403` for an unentitled user; never returns an unpublished recipe regardless of query match.
- `RecipeCreated`/`RecipeUpdated`/`RecipePublished`/`RecipeUnpublished` (v1) — each published payload matches `docs/events-catalog.md`'s documented schema.

## 4. E2E test cases

**Journey 3 is now partially buildable**: CLAUDE.md §3's journey 3 ("Upgrade to Pro → publish a recipe → another user finds it in recipe search") has both halves it needs — `billing-service` (upgrade/entitlement) and `recipe-service` (publish/search) — for the first time this session. **Still not built here**: a true E2E test spans two services' real infrastructure end-to-end, which is a bigger integration-test-environment investment than this plan's scope; recommend a dedicated follow-up once both services are merged and a cross-service E2E harness exists (none does yet in this repo — every prior service's plan deferred E2E for the same reason). Flagged as newly-possible, not silently dropped.

## 5. Event-sourcing-specific cases

**Not applicable.** `recipe-service` uses conventional persistence + event-driven CRUD (implementation plan §2), not event sourcing. The idempotency cases in §1/§2 cover the "new consumer introduced" requirement (this is the first real `EntitlementGranted`/`EntitlementRevoked` consumer in the codebase).

## 6. Coverage expectation

Domain layer (`RecipeIngredient`, `Servings`, `NutrientTotals`, `recipe_nutrient_calculator.py` against the shared reference fixture) has clear, enumerable edge cases — expect close to 100%, comfortably clearing the ≥90% floor. Application layer's nine handlers each have 2-5 cases above, deliberately covering entitlement-gating (cache-hit/miss/fallback, unentitled-rejected-not-degraded), unresolvable-ingredient blocking, and idempotency — not just happy paths — clears the ≥85% floor. Infrastructure layer's two external clients (full circuit-breaker matrices each), four repositories, outbox relay, consumer idempotency, migration, and the seven-route/four-event contract-test groups in §3 are expected to clear the ≥70% infrastructure floor. This plan is assessed as sufficient to meet CLAUDE.md §3's thresholds.

## 7. Fixtures (built, not sourced)

- `packages/shared-contracts/fixtures/nutrient_calculation_reference_cases.json` — hand-computed reference recipes (ingredients with known per-100g values, expected per-recipe and per-serving totals), shared with (but not required to be adopted by) `nutrition-calculation-service`'s own test suite per architecture-agent's anti-drift recommendation.
- `tests/fixtures/catalog_responses/*.json` — fixture `catalog-service` product responses, including a `nutrition_per_100g: null`/missing-micronutrient variant for the partial-status test case.
- `tests/fixtures/billing_responses/*.json` — fixture `billing-service` entitlement-check responses (entitled/unentitled).
- No real call to `catalog-service` or `billing-service` anywhere in this suite.
