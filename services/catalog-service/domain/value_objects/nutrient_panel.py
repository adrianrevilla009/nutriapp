"""NutrientPanel value object — macro/micro nutrient facts, always
normalized to "per 100g" before construction (normalization/conversion
itself happens in domain/services/product_normalizer.py; this VO only
validates the already-normalized shape).
"""

from __future__ import annotations

from dataclasses import dataclass

_MACRO_FIELDS = ("energy_kcal", "protein_g", "carbohydrates_g", "fat_g")
_MICRO_FIELDS = (
    "sugars_g",
    "fiber_g",
    "saturated_fat_g",
    "sodium_mg",
    "salt_g",
    "calcium_mg",
    "iron_mg",
    "vitamin_c_mg",
)


class InvalidNutrientPanelError(ValueError):
    """Raised when any provided nutrient value is negative."""


class IncompleteNutrientPanelError(ValueError):
    """Raised when the macro core (energy/protein/carbs/fat) is missing."""


@dataclass(frozen=True, slots=True)
class NutrientPanel:
    energy_kcal: float | None
    protein_g: float | None
    carbohydrates_g: float | None
    fat_g: float | None
    sugars_g: float | None = None
    fiber_g: float | None = None
    saturated_fat_g: float | None = None
    sodium_mg: float | None = None
    salt_g: float | None = None
    calcium_mg: float | None = None
    iron_mg: float | None = None
    vitamin_c_mg: float | None = None

    def __post_init__(self) -> None:
        for name in _MACRO_FIELDS:
            value = getattr(self, name)
            if value is None:
                raise IncompleteNutrientPanelError(
                    f"NutrientPanel is missing required macro field {name!r}."
                )
        for name in (*_MACRO_FIELDS, *_MICRO_FIELDS):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise InvalidNutrientPanelError(f"NutrientPanel field {name!r} cannot be negative.")

    def as_dict(self) -> dict[str, float | None]:
        return {name: getattr(self, name) for name in (*_MACRO_FIELDS, *_MICRO_FIELDS)}
