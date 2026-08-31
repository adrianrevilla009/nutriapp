from __future__ import annotations

import uuid

import pytest

from domain.value_objects.recipe_ingredient import InvalidQuantityError, RecipeIngredient


def test_positive_quantity_accepted():
    ingredient = RecipeIngredient(catalog_product_id=uuid.uuid4(), quantity_grams=100.0)
    assert ingredient.quantity_grams == 100.0


def test_zero_quantity_raises():
    with pytest.raises(InvalidQuantityError):
        RecipeIngredient(catalog_product_id=uuid.uuid4(), quantity_grams=0)


def test_negative_quantity_raises():
    with pytest.raises(InvalidQuantityError):
        RecipeIngredient(catalog_product_id=uuid.uuid4(), quantity_grams=-10)
