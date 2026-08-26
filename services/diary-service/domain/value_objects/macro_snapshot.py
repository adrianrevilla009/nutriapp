"""MacroSnapshot -- denormalized per-unit macro fields, part of FoodSource's
client-supplied snapshot (implementation plan section 5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InvalidMacroSnapshotError(Exception):
    """Raised when a macro value is negative."""


@dataclass(frozen=True, slots=True)
class MacroSnapshot:
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float

    def __post_init__(self) -> None:
        for field_name in ("calories_kcal", "protein_g", "carbs_g", "fat_g"):
            value = getattr(self, field_name)
            if value < 0:
                raise InvalidMacroSnapshotError(
                    f"Macro field {field_name!r} must be non-negative, got {value!r}."
                )

    def to_dict(self) -> dict[str, float]:
        return {
            "calories_kcal": self.calories_kcal,
            "protein_g": self.protein_g,
            "carbs_g": self.carbs_g,
            "fat_g": self.fat_g,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MacroSnapshot:
        return cls(
            calories_kcal=float(data["calories_kcal"]),
            protein_g=float(data["protein_g"]),
            carbs_g=float(data["carbs_g"]),
            fat_g=float(data["fat_g"]),
        )
