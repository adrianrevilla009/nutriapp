"""Pydantic response schemas for the product/search HTTP surface
(api-conventions SKILL.md)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from domain.entities.product import Product


class NutrientPanelResponse(BaseModel):
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


class PackageSizeResponse(BaseModel):
    value: float
    unit: str


class PriceResponse(BaseModel):
    amount: float
    currency: str


class ProductResponse(BaseModel):
    product_id: uuid.UUID
    barcode: str | None
    name: str | None
    brand: str | None
    category: str | None
    nutrition_per_100g: NutrientPanelResponse | None
    dietary_tags: list[str]
    allergen_tags: list[str]
    package_size: PackageSizeResponse | None
    price: PriceResponse | None
    sources: list[str]


def product_to_response(product: Product) -> ProductResponse:
    return ProductResponse(
        product_id=product.product_id,
        barcode=str(product.barcode) if product.barcode else None,
        name=product.name,
        brand=product.brand,
        category=product.category,
        nutrition_per_100g=(
            NutrientPanelResponse(**product.nutrient_panel.as_dict())
            if product.nutrient_panel
            else None
        ),
        dietary_tags=[t.value for t in product.dietary_tags],
        allergen_tags=[t.value for t in product.allergen_tags],
        package_size=(
            PackageSizeResponse(
                value=product.package_size.value, unit=product.package_size.unit.value
            )
            if product.package_size
            else None
        ),
        price=(
            PriceResponse(amount=product.price.amount, currency=product.price.currency)
            if product.price
            else None
        ),
        sources=sorted(s.value for s in product.sources),
    )
