"""Pydantic response schemas for the recognition HTTP surface
(api-conventions SKILL.md). Every quantitative estimate is a range, never
a single number (media-recognition-conventions SKILL.md)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from application.commands.analyze_food_photo import AnalyzeFoodPhotoResult
from application.commands.decode_barcode import DecodeBarcodeResult
from domain.value_objects.analysis_status import AnalysisStatus
from domain.value_objects.barcode_lookup_status import BarcodeLookupStatus
from domain.value_objects.catalog_product import CatalogProduct


class FoodCandidateResponse(BaseModel):
    name: str
    portion_range_min_g: float
    portion_range_max_g: float
    confidence: float


class AnalyzePhotoResponse(BaseModel):
    analysis_id: uuid.UUID
    status: AnalysisStatus
    candidates: list[FoodCandidateResponse]
    model_version: str


def analyze_result_to_response(result: AnalyzeFoodPhotoResult) -> AnalyzePhotoResponse:
    return AnalyzePhotoResponse(
        analysis_id=result.analysis_id,
        status=result.status,
        candidates=[
            FoodCandidateResponse(
                name=c.name,
                portion_range_min_g=c.portion_range.min_g,
                portion_range_max_g=c.portion_range.max_g,
                confidence=c.confidence.value,
            )
            for c in result.candidates
        ],
        model_version=result.model_version,
    )


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


class CatalogProductResponse(BaseModel):
    product_id: uuid.UUID
    barcode: str | None
    name: str | None
    brand: str | None
    category: str | None
    nutrition_per_100g: NutrientPanelResponse | None
    dietary_tags: list[str]
    allergen_tags: list[str]
    package_size: PackageSizeResponse | None
    sources: list[str]


def catalog_product_to_response(product: CatalogProduct) -> CatalogProductResponse:
    return CatalogProductResponse(
        product_id=product.product_id,
        barcode=product.barcode,
        name=product.name,
        brand=product.brand,
        category=product.category,
        nutrition_per_100g=(
            NutrientPanelResponse(
                energy_kcal=product.nutrition_per_100g.energy_kcal,
                protein_g=product.nutrition_per_100g.protein_g,
                carbohydrates_g=product.nutrition_per_100g.carbohydrates_g,
                fat_g=product.nutrition_per_100g.fat_g,
                sugars_g=product.nutrition_per_100g.sugars_g,
                fiber_g=product.nutrition_per_100g.fiber_g,
                saturated_fat_g=product.nutrition_per_100g.saturated_fat_g,
                sodium_mg=product.nutrition_per_100g.sodium_mg,
                salt_g=product.nutrition_per_100g.salt_g,
                calcium_mg=product.nutrition_per_100g.calcium_mg,
                iron_mg=product.nutrition_per_100g.iron_mg,
                vitamin_c_mg=product.nutrition_per_100g.vitamin_c_mg,
            )
            if product.nutrition_per_100g
            else None
        ),
        dietary_tags=product.dietary_tags,
        allergen_tags=product.allergen_tags,
        package_size=(
            PackageSizeResponse(value=product.package_size.value, unit=product.package_size.unit)
            if product.package_size
            else None
        ),
        sources=product.sources,
    )


class DecodeBarcodeResponse(BaseModel):
    lookup_id: uuid.UUID
    status: BarcodeLookupStatus
    product: CatalogProductResponse | None


def decode_result_to_response(result: DecodeBarcodeResult) -> DecodeBarcodeResponse:
    return DecodeBarcodeResponse(
        lookup_id=result.lookup_id,
        status=result.status,
        product=(catalog_product_to_response(result.product) if result.product else None),
    )
