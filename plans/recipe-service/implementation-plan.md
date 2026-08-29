# Implementation Plan — `recipe-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — event-driven CRUD), ADR-0004 (messaging backbone), ADR-0015 (billing/entitlements), ADR-0019 (saga pattern), `.claude/agents/recipe-agent.md`, `.claude/skills/resilience-patterns/SKILL.md`, `.claude/skills/saga-conventions/SKILL.md`, `.claude/skills/domain-calculation-conventions/SKILL.md`, `docs/sagas-and-distributed-transactions.md` (`ProUpgradeEntitlementPropagation`), `docs/events-catalog.md`, `docs/api-catalog.md`, `/plans/billing-service/implementation-plan.md`

## 1. Scope

Build `recipe-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing shared platform scaffolding.

**Bounded context** (CLAUDE.md §2.2, `.claude/agents/recipe-agent.md`): user recipe authoring (ingredients from `catalog-service`, quantities, instructions, servings), computed macro/micro breakdown, publishing (Pro-gated), and cross-user recipe search (Pro-gated).

**Dependency note (explicit, this session):** this plan is built against `billing-service`'s documented event/endpoint contracts from PR #23 (implemented and CI-green this session, not yet merged at the time this plan was written) — `EntitlementGranted`/`EntitlementRevoked` events and `GET /internal/v1/billing/entitlements/{user_id}`. Matches the precedent already set by `food-recognition-service` being built against `catalog-service`'s then-unmerged internal lookup endpoint (PR #11). **PR #23 must be merged before or alongside `recipe-service`'s own PR** — flagged explicitly so this isn't merged first by mistake.

**Architecture review (this session, `architecture-agent`, before this plan was written):**
- Confirmed event-driven CRUD (ADR-0002).
- Confirmed nutrient computation: `recipe-service` calls `catalog-service`'s existing public `GET /api/v1/catalog/products/{id}` per ingredient (confirmed to return `nutrition_per_100g`) and implements its **own local copy** of `nutrition-calculation-service`'s per-100g × quantity formula (`nutrient_amount = (per_100g_value / 100) × quantity_grams`, summed, micronutrient availability tracked as available/partial/unavailable) — never a cross-service code import (CLAUDE.md §2.5), matching the "own copy of common patterns" convention already used repo-wide. To guard against formula drift between the two independent implementations, this plan adds a shared JSON reference-fixture (`packages/shared-contracts/fixtures/nutrient_calculation_reference_cases.json` — data, not code) that `recipe-service`'s own unit tests consume; retrofitting `nutrition-calculation-service`'s already-merged tests to also consume it is a documented future nicety, not required now (would mean reopening that merged service for a non-functional test improvement).
- Confirmed the entitlement-gating design: `recipe-service` consumes both `EntitlementGranted`/`EntitlementRevoked` into a local `entitlement_cache` table (checked first on every publish/search request), falling back to `billing-service`'s synchronous, circuit-breaker-guarded internal endpoint only when no cached row exists yet for that user (a lagging/not-yet-processed consumer) — per ADR-0015's explicit "never a synchronous check on every request" rule and the `ProUpgradeEntitlementPropagation` saga's fail-safe design (a lagging consumer treats the user as not-yet-entitled, never fail-open).

**Acceptance criteria:**

1. **`POST /api/v1/recipes`** — author a recipe: ingredients (`catalog_product_id` + `quantity_grams`, list), instructions (free text), servings (positive int), title. **Not Pro-gated** — personal authoring is free. Publishes `RecipeCreated` (v1) via Outbox. Computed macro/micro totals (per-recipe and per-serving) are derived server-side from ingredient data at creation time — **never accepted as user input, never manually overridable** (`recipe-agent.md`'s explicit rule).
2. **`PATCH /api/v1/recipes/{recipe_id}`** — edit own recipe (ingredients/instructions/servings/title). Recomputes totals from the updated ingredient list. Publishes `RecipeUpdated` (v1).
3. **`GET /api/v1/recipes/{recipe_id}`** / **`GET /api/v1/recipes?mine=true`** — read own recipe(s), including unpublished ones. Not Pro-gated.
4. **`POST /api/v1/recipes/{recipe_id}/publish`** — **Pro-gated**: entitlement check (cache-first, fallback to `billing-service`) before proceeding. Blocks publishing if any ingredient's `catalog_product_id` no longer resolves to a real `catalog-service` product at publish time (re-verified synchronously, circuit-breaker-guarded, at publish — not trusted from creation time, since a product could have been removed since) — **never publishes incomplete/unresolvable data** (`recipe-agent.md`'s explicit rule). Publishes `RecipePublished` (v1) and makes the recipe visible in cross-user search.
5. **`POST /api/v1/recipes/{recipe_id}/unpublish`** and **`DELETE /api/v1/recipes/{recipe_id}`** — removes the recipe from cross-user search without deleting the author's own record/event history (soft-delete/unpublish flag, not a hard row delete). Publishes **`RecipeUnpublished`** (v1) — a new event, not yet in `docs/events-catalog.md`, added by this plan (§5) so `analytics-service`/`nutrition-assistant-service` can react to a recipe leaving search, mirroring `diary-service`'s "every removal publishes an event" precedent rather than repeating `activity-service`'s self-flagged gap from earlier this session.
6. **`GET /api/v1/recipes/search?q=...`** — **Pro-gated**: entitlement check (same cache-first pattern) before executing. Full-text/faceted search over published recipes only (Postgres full-text/`pg_trgm`, mirroring `catalog-service`'s search approach per ADR-0012's precedent — not a new search technology decision).
7. **Entitlement cache**: `entitlement_cache` table (`user_id`, `entitled: bool`, `updated_at`), populated by consuming `EntitlementGranted`/`EntitlementRevoked` (idempotent, dedup by `event_id`). `GetEntitlementHandler`-equivalent checks this cache first; on a cache miss (no row yet for that user), falls back to `GET /internal/v1/billing/entitlements/{user_id}` (own named circuit breaker, `billing_entitlement_check`) and does **not** cache the fallback result (avoids caching a possibly-stale answer under a name that implies event-driven freshness — next request re-checks the cache, which will have caught up if the event has since arrived).
8. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).

**Explicitly out of scope for this plan:**
- Any consumer-side wiring in `analytics-service`/`nutrition-assistant-service` for `RecipeCreated`/`RecipeUpdated`/`RecipePublished`/`RecipeUnpublished` — neither service exists yet, same deferral pattern as `activity-service`'s `ExerciseLogged`.
- Recipe images/media upload — `docs/product-requirements.md` doesn't require this for the MVP recipe feature; text-only (title/instructions/ingredients) for now.
- Recipe ratings/reviews/comments — a `social-service`-adjacent feature, not part of `recipe-service`'s bounded context per `recipe-agent.md`.
- Retrofitting `nutrition-calculation-service`'s tests to consume the new shared reference-fixture (architecture-agent's noted future nicety, not required now).

## 2. Architectural classification

**Event-driven CRUD** (ADR-0002, confirmed by architecture-agent) — not event-sourced. `Recipe` is stored conventionally (one row per recipe, soft-unpublished on removal from search), events published via Outbox as a side effect, mirroring `catalog-service`'s/`activity-service`'s pattern. `entitlement_cache` is a simple event-projected read table, same shape as `notification-service`'s `reminder_schedule`/`billing-service`'s revocation-schedule precedent — not its own CQRS/ES concern.

## 3. Files to create or modify

```
services/recipe-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_recipe_tables.py
      # recipes (recipe_id, user_id, title, instructions, servings,
      #   ingredients JSONB [{catalog_product_id, quantity_grams}],
      #   computed_totals JSONB {per_recipe, per_serving}, is_published
      #   bool, unpublished_at nullable, created_at, updated_at)
      # entitlement_cache (user_id, entitled bool, updated_at)
      # processed_entitlement_events (event_id, processed_at) -- idempotency
      # outbox
  domain/
    entities/            # Recipe
    value_objects/         # RecipeIngredient, Servings, NutrientTotals
                          # (mirrors nutrition-calculation-service's
                          # MacroAmounts/micronutrient-status shape --
                          # own copy, per CLAUDE.md 2.5)
    events/                # base.py (own copy), recipe_created.py,
                          # recipe_updated.py, recipe_published.py,
                          # recipe_unpublished.py (new, see plan section 5)
    services/               # recipe_nutrient_calculator.py -- pure function,
                          # mirrors nutrition_total_calculator.py's formula
                          # (per-100g x quantity, summed, divided by
                          # servings for the per-serving figure), tested
                          # against the new shared reference fixture
    ports/                  # recipe_repository_port.py,
                          # entitlement_cache_repository_port.py,
                          # processed_entitlement_events_repository_port.py,
                          # catalog_product_port.py (the per-ingredient
                          # lookup), entitlement_check_port.py (the
                          # billing-service fallback call),
                          # outbox_repository_port.py
  application/
    commands/               # create_recipe.py, update_recipe.py,
                          # publish_recipe.py, unpublish_recipe.py,
                          # delete_recipe.py, handle_entitlement_granted.py,
                          # handle_entitlement_revoked.py
    queries/                 # get_recipe.py, list_own_recipes.py,
                          # search_published_recipes.py
    dto/
    errors.py
  infrastructure/
    http/
      routes/                # recipe_routes.py, search_routes.py, health.py
      schemas/
      dependencies.py         # reuses packages/shared-contracts' centralized
                          # JWT auth dependency
      error_mapping.py
    external/
      catalog_product_client.py    # implements CatalogProductPort; own
                          # circuit breaker + tenacity retry + timeout,
                          # calls catalog-service's existing public
                          # GET /api/v1/catalog/products/{id}
      billing_entitlement_client.py  # implements EntitlementCheckPort;
                          # own circuit breaker (billing_entitlement_check)
                          # + retry + timeout, calls billing-service's
                          # GET /internal/v1/billing/entitlements/{user_id}
                          # with the X-Internal-Service-Credential pattern
    persistence/
      models.py, postgres_recipe_repository.py,
      postgres_entitlement_cache_repository.py,
      postgres_processed_entitlement_events_repository.py,
      postgres_outbox_repository.py
    messaging/
      billing_events_consumer.py   # EntitlementGranted, EntitlementRevoked
      rabbitmq_event_publisher.py, outbox_relay_worker.py
    composition_root.py, main.py
  tests/
    unit/domain/            # RecipeIngredient/Servings/NutrientTotals value
                          # objects, recipe_nutrient_calculator.py against
                          # the shared reference fixture (hand-computed
                          # cases, per recipe-agent.md's testing requirement)
    unit/application/        # all handlers, mocked ports -- including the
                          # unresolvable-ingredient-blocks-publish case,
                          # the cache-hit/cache-miss-fallback entitlement
                          # cases, and the unentitled-user-rejected cases
    integration/infrastructure/  # testcontainers Postgres/RabbitMQ,
                          # CatalogProductClient and
                          # BillingEntitlementClient against fixture HTTP
                          # servers (full circuit-breaker matrices),
                          # repository round-trips, outbox relay, migration,
                          # billing_events_consumer idempotency
    contract/http/         # all 7 routes, all 4 event payload contracts

packages/shared-contracts/
  fixtures/nutrient_calculation_reference_cases.json   # new -- hand-
    computed reference recipes with known expected totals (data only,
    architecture-agent's anti-drift recommendation)

infra/terraform/environments/dev/recipe-service.tf   # mirrors
    activity-service.tf's structure (own RDS schema/user, ECR repo);
    new secret: billing-service internal-reveal-style credential
    (X-Internal-Service-Credential), same mechanism as every prior
    internal-endpoint consumer
infra/k8s/charts/recipe-service/     # own chart, correct env-list format +
    envFrom wiring from the start
.github/workflows/recipe-service-ci.yml   # mirrors the other services'
    pipelines, pinned uv/action SHAs per existing convention

docs/events-catalog.md     # RecipeCreated/RecipeUpdated/RecipePublished
    flipped to Active, producer=recipe-service, consumers documented-not-
    yet-consuming; RecipeUnpublished added as a new v1 event (§5)
docs/api-catalog.md        # add the 7 new routes (5 public user-facing +
    2 Pro-gated), note which two require entitlement
docs/domain-glossary-and-context-map.md   # add recipe-service's
    relationships: Customer-Supplier via published events (deferred
    consumers), Open Host Service consumer of catalog-service's public
    product endpoint, Open Host Service consumer of billing-service's
    entitlement events + internal endpoint (Conformist, narrow synchronous
    exception, same classification precedent as the other internal-
    endpoint consumers)
docs/sagas-and-distributed-transactions.md  # ProUpgradeEntitlementPropagation:
    note recipe-service is now the FIRST real consumer implementing its
    side of the saga's fan-out (was documented-but-unbuilt until now)
ARCHITECTURE.md            # verify any existing recipe-service
    placeholder is still accurate
docker-compose.yml         # add a recipe-service block, own database
```

## 4. Ports/adapters affected

**New ports:** `RecipeRepositoryPort`, `EntitlementCacheRepositoryPort`, `ProcessedEntitlementEventsRepositoryPort`, `CatalogProductPort` (→ `catalog-service`'s existing public endpoint), `EntitlementCheckPort` (→ `billing-service`'s existing internal endpoint), `OutboxRepositoryPort`. No existing port from another service is reused (each service keeps its own port/adapter copy, per CLAUDE.md §2.5); `packages/shared-contracts`' centralized JWT auth dependency is reused for the public routes, per established precedent. `packages/shared-contracts` also gains a new **data-only** fixture file (§3), not a logic import.

## 5. Domain events

**Published:** `RecipeCreated`, `RecipeUpdated`, `RecipePublished` (all v1, already documented in `docs/events-catalog.md` from prior ADR acceptance, flipped to `Active` here) plus **`RecipeUnpublished` (v1, new)**:
```
### RecipeUnpublished (v1)
- Producer: recipe-service
- Consumers: analytics-service, nutrition-assistant-service (documented, not yet existing)
- Emitted when: a user unpublishes or deletes a previously-published recipe -- removed
  from cross-user search, author's own record/event history retained.
- Payload: { "recipe_id": "uuid", "user_id": "uuid", "unpublished_at": "timestamp" }
```
Consumers for all four events remain documented-not-yet-consuming (`analytics-service`/`nutrition-assistant-service` don't exist yet).

**Consumed:** `EntitlementGranted`, `EntitlementRevoked` (v1, `billing-service`) — the first real consumer of these events, implementing `recipe-service`'s side of the `ProUpgradeEntitlementPropagation` saga's fan-out.

## 6. Cross-service impact

**Flagged for `architecture-agent` review, already addressed this session:**
- Two new synchronous call relationships (`recipe-service` → `catalog-service`'s public product endpoint, `recipe-service` → `billing-service`'s internal entitlement endpoint) — both against already-existing, already-documented endpoints; no producer-side change needed anywhere.
- First real consumer of `EntitlementGranted`/`EntitlementRevoked` — implements (not just documents) the `ProUpgradeEntitlementPropagation` saga's consumer-side fan-out for the first time; `docs/sagas-and-distributed-transactions.md` updated to reflect this (§3).
- **Dependency on `billing-service` PR #23 merging** (§1) — explicitly flagged, not a silent assumption.

No other service's code changes as a result of this plan.

## 7. Resilience/caching/migration needs

- **Circuit breakers** (two independent synchronous dependencies): `catalog_product_lookup` (per-ingredient, called potentially many times per create/update/publish — each call independently circuit-broken, a single unresolvable/slow ingredient degrades that one ingredient's resolution, never the whole request silently) and `billing_entitlement_check` (the cache-miss fallback only). Both named, `tenacity` retry, explicit timeout, dedicated `httpx.AsyncClient` per `resilience-patterns/SKILL.md`.
- **Caching**: the `entitlement_cache` table itself *is* the cache (Postgres, not Redis) — consistent with `notification-service`'s/`billing-service`'s precedent of not introducing Redis for a low-volume, already-indexed-lookup use case. Recipe search (§1.6) may warrant a Redis result cache later if search volume justifies it — not built in this MVP (mirrors `catalog-service`'s own search-caching precedent being added incrementally, not day one).
- **Migration**: one initial Alembic migration creating four new tables, purely additive (new service).

## 8. Test plan reference

`/test-plan` will define concrete test cases next: value object validation, `recipe_nutrient_calculator.py` against the shared reference fixture, all seven command/query handlers (including unresolvable-ingredient-blocks-publish, cache-hit/cache-miss-fallback entitlement cases, unentitled-user-rejected-not-degraded), the two external clients' circuit-breaker matrices, repository round-trips, outbox atomicity, `billing_events_consumer`'s idempotency, and contract tests for all seven routes and all four event payloads. Not enumerated further here.

## 9. Risks and open questions

1. **`recipe-agent.md`'s "call the shared calculation logic" wording is imprecise** (architecture-agent's finding) — this plan interprets it correctly as "mirror the same formula, don't import code," consistent with CLAUDE.md §2.5. Recommend a small follow-up doc fix to `recipe-agent.md` itself for clarity; not blocking this plan.
2. **Ingredient re-resolution at publish time** (§1.4) adds up to N synchronous `catalog-service` calls (N = ingredient count) on the publish path — acceptable for a recipe-sized ingredient list (typically single-digit to low-double-digit items), each independently circuit-broken; if a future recipe format allows very large ingredient lists, batch-lookup would need revisiting (not needed for this MVP).
3. No other open questions — the three architecturally significant questions (nutrient computation approach, entitlement-gating pattern, classification) were resolved by `architecture-agent` before this plan was written (§1).
