"""Shared test fixtures/factories -- Recipe builders and in-memory fake
port implementations (hexagonal-architecture SKILL.md: "Application: unit
tests using fake/in-memory implementations of ports, not the real
adapters")."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.entities.recipe import Recipe
from domain.events.base import DomainEvent
from domain.ports.catalog_product_port import (
    CatalogProductUnavailableError,
    ResolvedIngredientProduct,
)
from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.nutrient_totals import ZERO_MACROS, NutrientTotals, RecipeNutrientTotals
from domain.value_objects.servings import Servings

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

ZERO_TOTALS = NutrientTotals(
    macros=ZERO_MACROS,
    macros_status="unavailable",
    micronutrients=None,
    micronutrients_status="unavailable",
)
ZERO_RECIPE_TOTALS = RecipeNutrientTotals(per_recipe=ZERO_TOTALS, per_serving=ZERO_TOTALS)

DEFAULT_PANEL = NutrientPanel(
    energy_kcal=100.0, protein_g=5.0, carbohydrates_g=10.0, fat_g=2.0, sugars_g=1.0
)


def make_recipe(**overrides) -> Recipe:
    defaults = dict(
        recipe_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Test Recipe",
        instructions="Mix and serve.",
        servings=Servings(2),
        ingredients=(),
        computed_totals=ZERO_RECIPE_TOTALS,
        now=NOW,
    )
    defaults.update(overrides)
    return Recipe.create(**defaults)


class FakeRecipeRepository:
    def __init__(self, seed: list[Recipe] | None = None) -> None:
        self.by_id: dict[uuid.UUID, Recipe] = {r.recipe_id: r for r in (seed or [])}
        self.save_calls = 0
        self.delete_calls = 0

    async def get_by_id(self, recipe_id: uuid.UUID) -> Recipe | None:
        return self.by_id.get(recipe_id)

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[Recipe]:
        return [r for r in self.by_id.values() if r.user_id == user_id]

    async def search_published(self, query: str) -> list[Recipe]:
        return [
            r for r in self.by_id.values() if r.is_published and query.lower() in r.title.lower()
        ]

    async def save(self, recipe: Recipe) -> None:
        self.save_calls += 1
        self.by_id[recipe.recipe_id] = recipe

    async def delete(self, recipe_id: uuid.UUID) -> None:
        # Present only so a test can assert it is NEVER called -- never
        # invoked by any real handler (recipe-agent.md: no hard row delete).
        self.delete_calls += 1
        self.by_id.pop(recipe_id, None)


class FakeCatalogProductPort:
    def __init__(
        self,
        resolvable: dict[uuid.UUID, ResolvedIngredientProduct] | None = None,
        raise_unavailable: bool = False,
    ) -> None:
        self.resolvable = resolvable or {}
        self.raise_unavailable = raise_unavailable
        self.calls: list[uuid.UUID] = []

    async def get_product(self, product_id: uuid.UUID) -> ResolvedIngredientProduct | None:
        self.calls.append(product_id)
        if self.raise_unavailable:
            raise CatalogProductUnavailableError("catalog-service unavailable (fake).")
        return self.resolvable.get(product_id)


def make_resolved_product(
    product_id: uuid.UUID, nutrition_per_100g: NutrientPanel | None = DEFAULT_PANEL
) -> ResolvedIngredientProduct:
    return ResolvedIngredientProduct(product_id=product_id, nutrition_per_100g=nutrition_per_100g)


class FakeEntitlementCacheRepository:
    def __init__(self, seed: dict[uuid.UUID, bool] | None = None) -> None:
        self.by_user: dict[uuid.UUID, bool] = dict(seed or {})
        self.upsert_calls = 0

    async def get(self, user_id: uuid.UUID) -> bool | None:
        return self.by_user.get(user_id)

    async def upsert(self, user_id: uuid.UUID, entitled: bool, updated_at: datetime) -> None:
        self.upsert_calls += 1
        self.by_user[user_id] = entitled


class FakeEntitlementCheckPort:
    def __init__(self, result: bool = False, raise_unavailable: bool = False) -> None:
        self.result = result
        self.raise_unavailable = raise_unavailable
        self.calls: list[uuid.UUID] = []

    async def check_entitlement(self, user_id: uuid.UUID) -> bool:
        self.calls.append(user_id)
        if self.raise_unavailable:
            raise EntitlementCheckUnavailableError("billing-service unavailable (fake).")
        return self.result


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return [e for e in self.enqueued if e.event_id not in self.published_ids][:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class FakeProcessedEntitlementEventsRepository:
    def __init__(self) -> None:
        self.processed: set[uuid.UUID] = set()

    async def is_processed(self, event_id: uuid.UUID) -> bool:
        return event_id in self.processed

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        self.processed.add(event_id)
