from __future__ import annotations

import uuid
from datetime import datetime, timezone

from domain.entities.recipe import Recipe
from domain.value_objects.nutrient_totals import ZERO_MACROS, NutrientTotals, RecipeNutrientTotals
from domain.value_objects.servings import Servings

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 6, 2, tzinfo=timezone.utc)

ZERO_TOTALS = NutrientTotals(
    macros=ZERO_MACROS,
    macros_status="unavailable",
    micronutrients=None,
    micronutrients_status="unavailable",
)
ZERO_RECIPE_TOTALS = RecipeNutrientTotals(per_recipe=ZERO_TOTALS, per_serving=ZERO_TOTALS)


def _make_recipe(**overrides) -> Recipe:
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


def test_create_starts_unpublished():
    recipe = _make_recipe()
    assert recipe.is_published is False
    assert recipe.unpublished_at is None
    assert recipe.was_ever_published is False


def test_publish_sets_flag_and_clears_unpublished_at():
    recipe = _make_recipe().publish(NOW)
    assert recipe.is_published is True
    assert recipe.unpublished_at is None
    assert recipe.was_ever_published is True


def test_unpublish_a_published_recipe_sets_timestamp():
    published = _make_recipe().publish(NOW)
    unpublished = published.unpublish(LATER)
    assert unpublished.is_published is False
    assert unpublished.unpublished_at == LATER
    assert unpublished.was_ever_published is True


def test_unpublish_is_idempotent_for_an_already_unpublished_recipe():
    published = _make_recipe().publish(NOW)
    unpublished_once = published.unpublish(LATER)
    unpublished_twice = unpublished_once.unpublish(LATER)
    assert unpublished_twice is unpublished_once


def test_unpublish_a_never_published_recipe_is_a_no_op():
    draft = _make_recipe()
    result = draft.unpublish(LATER)
    assert result is draft
    assert result.was_ever_published is False


def test_update_never_changes_publish_state():
    published = _make_recipe().publish(NOW)
    updated = published.update(
        title="New Title",
        instructions="New instructions.",
        servings=Servings(4),
        ingredients=(),
        computed_totals=ZERO_RECIPE_TOTALS,
        now=LATER,
    )
    assert updated.is_published is True
    assert updated.title == "New Title"
    assert updated.servings == Servings(4)
