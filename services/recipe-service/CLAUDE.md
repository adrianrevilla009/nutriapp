# recipe-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/recipe-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/recipe-agent.md`
(bounded context, domain responsibilities, rules) -- read both first,
plus `.claude/skills/saga-conventions/SKILL.md`,
`.claude/skills/resilience-patterns/SKILL.md`, and
`.claude/skills/domain-calculation-conventions/SKILL.md` before touching
anything in `domain/services/recipe_nutrient_calculator.py`,
`application/commands/publish_recipe.py`, or
`infrastructure/messaging/billing_events_consumer.py` -- mandatory,
non-negotiable reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, or pydantic.
- Event-driven CRUD (ADR-0002), not event-sourced -- `Recipe` is a
  conventional row per recipe, mutated via immutable-entity transition
  methods (`create`/`update`/`publish`/`unpublish`) that each return a
  NEW `Recipe` instance; the application layer persists the returned
  instance.
- `computed_totals` is ALWAYS derived server-side from `ingredients` via
  `recipe_nutrient_calculator.py` -- `CreateRecipeCommand`/
  `UpdateRecipeCommand` structurally have no totals field at all (see
  `tests/unit/application/test_create_recipe.py::test_command_signature_never_accepts_a_totals_parameter`).
- `recipe_nutrient_calculator.py` sources BOTH macro and micro figures
  from the SAME `catalog-service` `nutrition_per_100g` panel per
  ingredient (unlike `nutrition-calculation-service`, which splits macros
  from diary-service's snapshot vs. micros from a local mirror) -- see
  that module's own docstring for the resolved ambiguity around a
  missing-panel ingredient's macro contribution (documented as zero, not
  invented, flagged for reviewer-agent).

## Never do this

- Never add a totals/macros/micronutrients parameter to
  `CreateRecipeCommand`/`UpdateRecipeCommand` or either handler's
  `.handle()` signature -- computed totals are always derived, never
  caller-supplied (recipe-agent.md's single most important rule).
- Never publish `RecipePublished` without first (a) confirming
  entitlement via `application/entitlement_check.py`'s cache-first/
  fallback pattern and (b) re-verifying every ingredient resolves via
  `CatalogProductPort`, fresh at publish time -- never trusted from
  creation/update time.
- Never write a fallback `EntitlementCheckPort` result back into
  `entitlement_cache` -- `application/entitlement_check.py`'s
  `is_user_entitled` has no reference to the cache repository's write
  method at all; keep it that way.
- Never add a hard-delete path to `RecipeRepositoryPort` or any concrete
  repository. Removal (`UnpublishRecipeHandler`/`DeleteRecipeHandler`) is
  always a soft-unpublish (`is_published=False`, `unpublished_at` set),
  even for the `DELETE` HTTP verb.
- Never publish `RecipeUnpublished` for a recipe that was never published
  (a draft) or is already unpublished -- `Recipe.unpublish()`'s no-op
  return (`self is result`) is what both handlers check before enqueueing
  the event.
- Never share circuit-breaker state between `catalog_product_lookup` and
  `billing_entitlement_check` -- two independent `purgatory` breaker
  instances, two independent `httpx.AsyncClient` connection pools.
- Never make a live call to a real `catalog-service` or `billing-service`
  instance in this service's own test suite -- `httpx.MockTransport`
  fixtures (`tests/fixtures/catalog_responses/`,
  `tests/fixtures/billing_responses/`) only.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `RecipeRepositoryPort`,
  `EntitlementCacheRepositoryPort`, `ProcessedEntitlementEventsRepositoryPort`,
  `CatalogProductPort`, `EntitlementCheckPort`, `OutboxRepositoryPort`,
  `EventPublisherPort`.
- Adapters: `infrastructure/external/catalog_product_client.py`,
  `infrastructure/external/billing_entitlement_client.py`,
  `infrastructure/persistence/` (four Postgres repositories),
  `infrastructure/messaging/` (`BillingEventsConsumer`,
  `RabbitMqEventPublisher`, `OutboxRelayWorker`).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Shared cross-handler helpers (not ports, not commands):
  `application/ingredient_resolution.py` (used by create/update/publish),
  `application/entitlement_check.py` (used by publish/search).
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).
