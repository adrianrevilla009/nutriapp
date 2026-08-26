"""PackageSize value object — value + unit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PackageUnit(str, Enum):
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITER = "ml"
    LITER = "l"
    UNIT = "unit"


class InvalidPackageSizeError(ValueError):
    """Raised for a non-positive value or an unsupported unit string."""


@dataclass(frozen=True, slots=True)
class PackageSize:
    value: float
    unit: PackageUnit

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidPackageSizeError(
                f"PackageSize.value must be positive, got {self.value!r}."
            )

    @classmethod
    def from_raw(cls, value: float, unit: str) -> PackageSize:
        try:
            package_unit = PackageUnit(unit.strip().lower())
        except ValueError as exc:
            raise InvalidPackageSizeError(f"Unsupported package unit: {unit!r}.") from exc
        return cls(value=value, unit=package_unit)
