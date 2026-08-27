"""Nutrient vocabulary translator -- the anticorruption layer resolving
implementation plan section 6(g)'s naming mismatch between diary-service's
and catalog-service's nutrient vocabularies. This service defines its own
canonical vocabulary (matching diary's macro naming, since macros are
always sourced from diary's snapshot) and translates both raw upstream
shapes into it, rather than forking a vocabulary per source.

Canonical macro fields: calories_kcal, protein_g, carbs_g, fat_g.
Canonical micronutrient fields: sugars_g, fiber_g, saturated_fat_g,
sodium_mg, salt_g, calcium_mg, iron_mg, vitamin_c_mg (catalog-service is
the only source of micronutrient data, so its micro field names are
already canonical -- no translation needed for those).
"""

from __future__ import annotations

from collections.abc import Mapping

# catalog-service's raw `nutrition_per_100g` macro field name -> canonical name
_CATALOG_MACRO_FIELD_MAP: dict[str, str] = {
    "energy_kcal": "calories_kcal",
    "protein_g": "protein_g",
    "carbohydrates_g": "carbs_g",
    "fat_g": "fat_g",
}

# diary-service's raw `macros_per_unit` field name -> canonical name (already
# canonical -- diary's vocabulary IS this service's canonical macro vocabulary).
_DIARY_MACRO_FIELD_MAP: dict[str, str] = {
    "calories_kcal": "calories_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbs_g",
    "fat_g": "fat_g",
}

_CATALOG_MICRO_FIELDS: tuple[str, ...] = (
    "sugars_g",
    "fiber_g",
    "saturated_fat_g",
    "sodium_mg",
    "salt_g",
    "calcium_mg",
    "iron_mg",
    "vitamin_c_mg",
)


def translate_catalog_nutrition(raw: Mapping[str, float | None]) -> dict[str, float | None]:
    """Translates a raw catalog-service `nutrition_per_100g` shape into the
    canonical vocabulary -- macros renamed, micronutrients passed through
    unchanged (already canonical)."""
    canonical: dict[str, float | None] = {}
    for raw_field, canonical_field in _CATALOG_MACRO_FIELD_MAP.items():
        if raw_field in raw:
            canonical[canonical_field] = raw[raw_field]
    for field in _CATALOG_MICRO_FIELDS:
        if field in raw:
            canonical[field] = raw[field]
    return canonical


def translate_diary_macros(raw: Mapping[str, float]) -> dict[str, float]:
    """Translates a raw diary-service `macros_per_unit` shape into the
    canonical vocabulary (a no-op rename table today, kept explicit so a
    future diary-service field rename is caught here, not silently)."""
    return {
        canonical_field: raw[raw_field]
        for raw_field, canonical_field in _DIARY_MACRO_FIELD_MAP.items()
        if raw_field in raw
    }
