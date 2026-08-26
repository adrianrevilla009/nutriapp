"""FoodSource -- opaque source_type discriminator + source_reference_id +
a denormalized snapshot, shared by Food Entry and Meal Plan Entry
(implementation plan section 1's settled scoping constraint / section 5).

`source_type` reserves `recipe` and `ai_detected` for later services --
this plan only ever exercises `catalog_product` (test-plan section 0).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.value_objects.macro_snapshot import MacroSnapshot
from domain.value_objects.quantity import Quantity

SUPPORTED_SOURCE_TYPES = frozenset({"catalog_product", "recipe", "ai_detected"})


class InvalidFoodSourceError(Exception):
    """Raised when source_type is unsupported or source_reference_id is missing."""


@dataclass(frozen=True, slots=True)
class FoodSourceSnapshot:
    name: str
    brand: str | None
    quantity: float
    unit: str
    macros_per_unit: MacroSnapshot

    def __post_init__(self) -> None:
        # Delegates to Quantity so amount/unit invariants (test-plan section 0/1's
        # g|ml|serving vocabulary) are enforced on this actual write path, not just
        # proven in isolation on the standalone Quantity value object.
        Quantity(amount=self.quantity, unit=self.unit)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "brand": self.brand,
            "quantity": self.quantity,
            "unit": self.unit,
            "macros_per_unit": self.macros_per_unit.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FoodSourceSnapshot:
        return cls(
            name=data["name"],
            brand=data.get("brand"),
            quantity=float(data["quantity"]),
            unit=data["unit"],
            macros_per_unit=MacroSnapshot.from_dict(data["macros_per_unit"]),
        )


@dataclass(frozen=True, slots=True)
class FoodSource:
    source_type: str
    source_reference_id: str
    snapshot: FoodSourceSnapshot

    def __post_init__(self) -> None:
        if self.source_type not in SUPPORTED_SOURCE_TYPES:
            raise InvalidFoodSourceError(f"Unsupported source_type: {self.source_type!r}.")
        if not self.source_reference_id:
            raise InvalidFoodSourceError("source_reference_id must not be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_reference_id": self.source_reference_id,
            "snapshot": self.snapshot.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FoodSource:
        return cls(
            source_type=data["source_type"],
            source_reference_id=data["source_reference_id"],
            snapshot=FoodSourceSnapshot.from_dict(data["snapshot"]),
        )
