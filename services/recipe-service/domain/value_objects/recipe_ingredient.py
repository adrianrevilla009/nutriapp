"""RecipeIngredient -- a single line of a Recipe's ingredient list: a
`catalog-service` product id plus a quantity in grams. This service never
stores a denormalized copy of the product's name/nutrition here -- only
the reference id and quantity; nutrition data is always resolved fresh via
`CatalogProductPort` at compute time (creation/update/publish), never
cached stale on the ingredient line itself.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


class InvalidQuantityError(ValueError):
    """Raised for a non-positive ingredient quantity."""


@dataclass(frozen=True, slots=True)
class RecipeIngredient:
    catalog_product_id: uuid.UUID
    quantity_grams: float

    def __post_init__(self) -> None:
        if self.quantity_grams <= 0:
            raise InvalidQuantityError(
                f"quantity_grams must be positive, got {self.quantity_grams!r}."
            )
