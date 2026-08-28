"""CatalogProduct -- this service's own anticorruption-layer shape for a
product returned by `catalog-service`'s internal barcode-lookup endpoint.

Mirrors the response shape of `catalog-service`'s public
`GET /api/v1/catalog/products/{id}` (reused as-is by its new internal
lookup endpoint, per `/plans/catalog-service/implementation-plan.md`
Addendum 2) -- but this is `food-recognition-service`'s OWN independent
type (CLAUDE.md section 2.5: no cross-service imports), built by
`CatalogLookupClient` from the raw HTTP JSON response, never
`catalog-service`'s own `Product` entity or `ProductResponse` schema
directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


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


@dataclass(frozen=True, slots=True)
class PackageSize:
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class Price:
    amount: float
    currency: str


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    product_id: uuid.UUID
    barcode: str | None
    name: str | None
    brand: str | None
    category: str | None
    nutrition_per_100g: NutrientPanel | None
    dietary_tags: list[str]
    allergen_tags: list[str]
    package_size: PackageSize | None
    price: Price | None
