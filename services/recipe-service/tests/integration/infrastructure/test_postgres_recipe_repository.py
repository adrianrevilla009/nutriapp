"""PostgresRecipeRepository -- round-trip persistence via testcontainers
Postgres (test-plan section 2), including ingredients/computed_totals
JSONB serialization round-trip."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.services.recipe_nutrient_calculator import (
    calculate_ingredient_nutrient_total,
    calculate_recipe_nutrient_totals,
)
from domain.value_objects.nutrient_panel import NutrientPanel
from domain.value_objects.recipe_ingredient import RecipeIngredient
from infrastructure.persistence.postgres_recipe_repository import PostgresRecipeRepository
from tests.fixtures.factories import NOW, make_recipe


async def test_save_and_get_round_trips_ingredients_and_totals(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    product_id = uuid.uuid4()
    panel = NutrientPanel(
        energy_kcal=200.0, protein_g=10.0, carbohydrates_g=20.0, fat_g=5.0, sugars_g=3.0
    )
    line = calculate_ingredient_nutrient_total(quantity_grams=150, nutrition_per_100g=panel)
    totals = calculate_recipe_nutrient_totals([line], servings=3)
    recipe = make_recipe(
        ingredients=(RecipeIngredient(catalog_product_id=product_id, quantity_grams=150),),
        computed_totals=totals,
    )

    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        await repo.save(recipe)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        fetched = await repo.get_by_id(recipe.recipe_id)

    assert fetched is not None
    assert fetched.ingredients[0].catalog_product_id == product_id
    assert fetched.ingredients[0].quantity_grams == 150
    assert fetched.computed_totals.per_recipe.macros.calories_kcal == 300.0
    assert fetched.computed_totals.per_recipe.micronutrients_status == "available"
    assert fetched.computed_totals.per_recipe.macros_status == "available"


async def test_list_by_user_id_excludes_other_users(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    mine = make_recipe(user_id=owner_id)
    other = make_recipe(user_id=other_id)

    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        await repo.save(mine)
        await repo.save(other)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        results = await repo.list_by_user_id(owner_id)

    assert [r.recipe_id for r in results] == [mine.recipe_id]


async def test_search_published_only_returns_published_matching_recipes(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    published = make_recipe(title="Pasta Bake").publish(NOW)
    draft = make_recipe(title="Pasta Secret Draft")

    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        await repo.save(published)
        await repo.save(draft)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        results = await repo.search_published("pasta")

    assert [r.recipe_id for r in results] == [published.recipe_id]


async def test_get_by_id_missing_returns_none(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = PostgresRecipeRepository(session)
        result = await repo.get_by_id(uuid.uuid4())
    assert result is None
