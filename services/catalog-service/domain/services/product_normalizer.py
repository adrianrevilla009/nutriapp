"""product_normalizer — per-source raw dict -> RawProductRecord -> domain
value objects.

This is `catalog-service`'s anticorruption layer (implementation plan
§6, `docs/domain-glossary-and-context-map.md` §2's "Any external
third-party API... Anticorruption Layer" row): third-party data is
arbitrary-quality and never validated ahead of time, so every field here
degrades gracefully (coerce, drop, or fall back to `None`) rather than
raising for anything short of a genuinely empty/unidentifiable record.

`RawProductRecord` is defined here (a domain concern — it is the
already-normalized-but-not-yet-deduplicated shape) and re-exported by
`application/dto/raw_product_record.py` for the application layer's own
import surface, so the domain layer never imports upward from
application/infrastructure (ADR-0001).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from domain.services.allergen_tag_deriver import (
    derive_dietary_tags_from_off_labels,
    derive_off_allergen_tags,
    derive_usda_allergen_tags,
)
from domain.value_objects.allergen_tags import AllergenTags
from domain.value_objects.barcode import Barcode, InvalidBarcodeError
from domain.value_objects.dietary_tags import DietaryTags
from domain.value_objects.nutrient_panel import (
    IncompleteNutrientPanelError,
    InvalidNutrientPanelError,
    NutrientPanel,
)
from domain.value_objects.package_size import InvalidPackageSizeError, PackageSize
from domain.value_objects.price import Price
from domain.value_objects.source_reference import SourceName

logger = logging.getLogger(__name__)


class EmptyRawRecordError(ValueError):
    """Raised for a `None`/empty raw record — nothing to normalize."""


class MissingSourceIdentifierError(ValueError):
    """Raised when a raw record has no stable source-scoped identifier at
    all (e.g. no OFF `code`/`_id`, no USDA `fdcId`) — the adapter's batch
    reader must skip-and-log this row rather than crash the whole batch,
    per the external-data-ethics SKILL.md "source fragility" guidance."""


@dataclass(frozen=True, slots=True)
class RawProductRecord:
    source: SourceName
    source_product_id: str
    barcode: Barcode | None
    name: str | None
    brand: str | None
    category: str | None
    nutrient_panel: NutrientPanel | None
    dietary_tags: DietaryTags
    allergen_tags: AllergenTags
    package_size: PackageSize | None
    price: Price | None
    observed_at: datetime


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _g_to_mg(value: float | None) -> float | None:
    return None if value is None else value * 1000.0


def _safe_barcode(raw_value: Any) -> Barcode | None:
    if raw_value is None:
        return None
    raw_str = str(raw_value).strip()
    if not raw_str:
        return None
    try:
        return Barcode(raw_str)
    except InvalidBarcodeError:
        logger.warning("catalog_normalizer_dropped_invalid_barcode", extra={"raw_value": raw_str})
        return None


def _parse_quantity_string(raw_value: Any) -> PackageSize | None:
    if not raw_value or not isinstance(raw_value, str):
        return None
    parts = raw_value.strip().split()
    if len(parts) < 2:
        return None
    try:
        value = float(parts[0])
        return PackageSize.from_raw(value, parts[1])
    except (ValueError, InvalidPackageSizeError):
        return None


def _build_panel(fields: dict[str, float | None]) -> NutrientPanel | None:
    try:
        return NutrientPanel(**fields)
    except (IncompleteNutrientPanelError, InvalidNutrientPanelError):
        return None


# --- Open Food Facts -------------------------------------------------


def normalize_open_food_facts_record(
    raw: dict[str, Any] | None, *, observed_at: datetime
) -> RawProductRecord:
    if not raw:
        raise EmptyRawRecordError("Open Food Facts raw record is empty.")

    source_product_id = raw.get("code") or raw.get("_id")
    if not source_product_id:
        raise MissingSourceIdentifierError(
            "Open Food Facts record has no 'code'/'_id' to identify it by."
        )

    nutriments = raw.get("nutriments") or {}
    panel_fields = {
        "energy_kcal": _coerce_float(nutriments.get("energy-kcal_100g")),
        "protein_g": _coerce_float(nutriments.get("proteins_100g")),
        "carbohydrates_g": _coerce_float(nutriments.get("carbohydrates_100g")),
        "fat_g": _coerce_float(nutriments.get("fat_100g")),
        "sugars_g": _coerce_float(nutriments.get("sugars_100g")),
        "fiber_g": _coerce_float(nutriments.get("fiber_100g")),
        "saturated_fat_g": _coerce_float(nutriments.get("saturated-fat_100g")),
        "sodium_mg": _g_to_mg(_coerce_float(nutriments.get("sodium_100g"))),
        "salt_g": _coerce_float(nutriments.get("salt_100g")),
        "calcium_mg": _g_to_mg(_coerce_float(nutriments.get("calcium_100g"))),
        "iron_mg": _g_to_mg(_coerce_float(nutriments.get("iron_100g"))),
        "vitamin_c_mg": _g_to_mg(_coerce_float(nutriments.get("vitamin-c_100g"))),
    }
    nutrient_panel = _build_panel(panel_fields) if nutriments else None

    categories = raw.get("categories")
    category = (
        categories.split(",")[0].strip() if isinstance(categories, str) and categories else None
    )

    return RawProductRecord(
        source=SourceName.OPEN_FOOD_FACTS,
        source_product_id=str(source_product_id),
        barcode=_safe_barcode(raw.get("code")),
        name=(raw.get("product_name") or None),
        brand=(raw.get("brands") or None),
        category=category,
        nutrient_panel=nutrient_panel,
        dietary_tags=derive_dietary_tags_from_off_labels(raw.get("labels_tags") or []),
        allergen_tags=derive_off_allergen_tags(raw.get("allergens_tags") or []),
        package_size=_parse_quantity_string(raw.get("quantity")),
        price=None,  # Open Prices adapter deferred (implementation plan §9.5)
        observed_at=observed_at,
    )


# --- USDA FoodData Central Branded Foods ------------------------------

_USDA_NUTRIENT_NAME_MAP = {
    "energy_kcal": "Energy",
    "protein_g": "Protein",
    "carbohydrates_g": "Carbohydrate, by difference",
    "fat_g": "Total lipid (fat)",
    "sugars_g": "Sugars, total including NLEA",
    "fiber_g": "Fiber, total dietary",
    "saturated_fat_g": "Fatty acids, total saturated",
    "sodium_mg": "Sodium, Na",
    "calcium_mg": "Calcium, Ca",
    "iron_mg": "Iron, Fe",
    "vitamin_c_mg": "Vitamin C, total ascorbic acid",
}

_USDA_LABEL_NUTRIENT_KEY_MAP = {
    "energy_kcal": "calories",
    "protein_g": "protein",
    "carbohydrates_g": "carbohydrates",
    "fat_g": "fat",
    "sugars_g": "sugars",
    "fiber_g": "fiber",
    "saturated_fat_g": "saturatedFat",
    "sodium_mg": "sodium",
    "calcium_mg": "calcium",
    "iron_mg": "iron",
}


def _panel_from_food_nutrients(food_nutrients: list[dict[str, Any]]) -> NutrientPanel | None:
    by_name = {}
    for entry in food_nutrients:
        name = entry.get("nutrientName")
        if name:
            by_name[name] = _coerce_float(entry.get("value"))
    fields = {field: by_name.get(usda_name) for field, usda_name in _USDA_NUTRIENT_NAME_MAP.items()}
    fields.setdefault("salt_g", None)
    return _build_panel(fields)


def _panel_from_label_nutrients(raw: dict[str, Any]) -> NutrientPanel | None:
    label_nutrients = raw.get("labelNutrients")
    if not label_nutrients:
        return None
    serving_size = _coerce_float(raw.get("servingSize"))
    serving_unit = str(raw.get("servingSizeUnit") or "").strip().lower()
    if not serving_size or serving_size <= 0 or serving_unit not in ("g", "grm", "ml"):
        # Per-serving-only data with no usable serving size to convert
        # from — mark the panel incomplete rather than silently
        # mislabeling per-serving data as per-100g (test-plan §1).
        return None
    factor = 100.0 / serving_size
    fields: dict[str, float | None] = {}
    for field, label_key in _USDA_LABEL_NUTRIENT_KEY_MAP.items():
        entry = label_nutrients.get(label_key)
        value = _coerce_float(entry.get("value")) if isinstance(entry, dict) else None
        fields[field] = value * factor if value is not None else None
    fields.setdefault("vitamin_c_mg", None)
    fields.setdefault("salt_g", None)
    return _build_panel(fields)


def normalize_usda_fdc_record(
    raw: dict[str, Any] | None, *, observed_at: datetime
) -> RawProductRecord:
    if not raw:
        raise EmptyRawRecordError("USDA FDC raw record is empty.")

    fdc_id = raw.get("fdcId")
    if not fdc_id:
        raise MissingSourceIdentifierError("USDA FDC record has no 'fdcId' to identify it by.")

    food_nutrients = raw.get("foodNutrients") or []
    nutrient_panel = (
        _panel_from_food_nutrients(food_nutrients)
        if food_nutrients
        else _panel_from_label_nutrients(raw)
    )

    return RawProductRecord(
        source=SourceName.USDA_FDC,
        source_product_id=str(fdc_id),
        barcode=_safe_barcode(raw.get("gtinUpc")),
        name=(raw.get("description") or None),
        brand=(raw.get("brandOwner") or None),
        category=(raw.get("brandedFoodCategory") or None),
        nutrient_panel=nutrient_panel,
        dietary_tags=DietaryTags.empty(),  # USDA Branded Foods has no structured dietary-label field
        allergen_tags=derive_usda_allergen_tags(raw.get("ingredients")),
        package_size=_parse_quantity_string(raw.get("packageWeight")),
        price=None,
        observed_at=observed_at,
    )


def normalize_raw_record(
    source: SourceName, raw: dict[str, Any] | None, *, observed_at: datetime
) -> RawProductRecord:
    if source is SourceName.OPEN_FOOD_FACTS:
        return normalize_open_food_facts_record(raw, observed_at=observed_at)
    if source is SourceName.USDA_FDC:
        return normalize_usda_fdc_record(raw, observed_at=observed_at)
    raise ValueError(f"Unsupported source: {source!r}")
