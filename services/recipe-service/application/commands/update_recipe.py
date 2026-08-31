"""UpdateRecipeHandler -- backs `PATCH /api/v1/recipes/{recipe_id}`. Not
Pro-gated (editing your own recipe is authoring, not publishing).
Recomputes totals from the updated ingredient list -- never accepts a
totals override (same structural guard as `CreateRecipeCommand`)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import RecipeNotFoundError
from application.ingredient_resolution import resolve_all_ingredients
from domain.entities.recipe import Recipe
from domain.events.recipe_updated import build_recipe_updated_event
from domain.ports.catalog_product_port import CatalogProductPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.recipe_repository_port import RecipeRepositoryPort
from domain.services.recipe_nutrient_calculator import (
    calculate_ingredient_nutrient_total,
    calculate_recipe_nutrient_totals,
)
from domain.value_objects.recipe_ingredient import RecipeIngredient
from domain.value_objects.servings import Servings


@dataclass(frozen=True, slots=True)
class UpdateRecipeIngredientInput:
    catalog_product_id: uuid.UUID
    quantity_grams: float


@dataclass(frozen=True, slots=True)
class UpdateRecipeCommand:
    recipe_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    instructions: str
    servings: int
    ingredients: list[UpdateRecipeIngredientInput]
    correlation_id: str


class UpdateRecipeHandler:
    def __init__(
        self,
        recipes: RecipeRepositoryPort,
        catalog_products: CatalogProductPort,
        outbox: OutboxRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._recipes = recipes
        self._catalog_products = catalog_products
        self._outbox = outbox
        self._now_fn = now_fn

    async def handle(self, command: UpdateRecipeCommand) -> Recipe:
        recipe = await self._recipes.get_by_id(command.recipe_id)
        if recipe is None or recipe.user_id != command.user_id:
            raise RecipeNotFoundError(f"Recipe {command.recipe_id} not found.")

        servings = Servings(command.servings)
        ingredients = tuple(
            RecipeIngredient(
                catalog_product_id=item.catalog_product_id, quantity_grams=item.quantity_grams
            )
            for item in command.ingredients
        )

        resolved_products = await resolve_all_ingredients(ingredients, self._catalog_products)
        ingredient_lines = [
            calculate_ingredient_nutrient_total(
                quantity_grams=ingredient.quantity_grams,
                nutrition_per_100g=product.nutrition_per_100g,
            )
            for ingredient, product in zip(ingredients, resolved_products, strict=True)
        ]
        computed_totals = calculate_recipe_nutrient_totals(ingredient_lines, servings=int(servings))

        updated = recipe.update(
            title=command.title,
            instructions=command.instructions,
            servings=servings,
            ingredients=ingredients,
            computed_totals=computed_totals,
            now=self._now_fn(),
        )
        await self._recipes.save(updated)
        await self._outbox.enqueue(
            build_recipe_updated_event(
                recipe_id=updated.recipe_id,
                user_id=updated.user_id,
                correlation_id=command.correlation_id,
            )
        )
        return updated
