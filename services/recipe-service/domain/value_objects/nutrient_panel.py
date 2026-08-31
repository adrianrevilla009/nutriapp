"""NutrientPanel -- this service's own anticorruption-layer shape for the
`nutrition_per_100g` panel returned by `catalog-service`'s public
`GET /api/v1/catalog/products/{id}` endpoint (CatalogProductPort's
resolved-product payload).

Mirrors `catalog-service`'s `NutrientPanelResponse` / `food-recognition-
service`'s own `NutrientPanel` field-for-field -- but this is
`recipe-service`'s OWN independent type (CLAUDE.md section 2.5: no
cross-service imports), built by `CatalogProductClient` from the raw HTTP
JSON response, never `catalog-service`'s own `Product`/`NutrientPanelResponse`
types directly.

Every field is independently optional: a real catalog product's panel can
be partially populated (e.g. `energy_kcal` known, `vitamin_c_mg` not) --
`recipe_nutrient_calculator.py` must handle a `None` field value, never
invent one.
"""

from __future__ import annotations

from dataclasses import dataclass

MICRONUTRIENT_FIELDS: tuple[str, ...] = (
    "sugars_g",
    "fiber_g",
    "saturated_fat_g",
    "sodium_mg",
    "salt_g",
    "calcium_mg",
    "iron_mg",
    "vitamin_c_mg",
)


@dataclass(frozen=True, slots=True)
class NutrientPanel:
    energy_kcal: float | None = None
    protein_g: float | None = None
    carbohydrates_g: float | None = None
    fat_g: float | None = None
    sugars_g: float | None = None
    fiber_g: float | None = None
    saturated_fat_g: float | None = None
    sodium_mg: float | None = None
    salt_g: float | None = None
    calcium_mg: float | None = None
    iron_mg: float | None = None
    vitamin_c_mg: float | None = None

    def micronutrient_values(self) -> dict[str, float | None]:
        return {field: getattr(self, field) for field in MICRONUTRIENT_FIELDS}
