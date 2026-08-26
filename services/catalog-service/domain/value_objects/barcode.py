"""Barcode value object — GTIN/EAN/UPC check-digit validation.

Barcode is the sole dedup key for `Product` (implementation plan Addendum
1, §9.3(a)) — no fuzzy name+brand matching. A `Barcode` is either a valid,
check-digit-verified GTIN-8/12/13/14, or absent (`None` at the entity
level) — never an unvalidated raw string masquerading as a barcode.
"""

from __future__ import annotations

from dataclasses import dataclass

_VALID_LENGTHS = (8, 12, 13, 14)  # EAN-8, UPC-A, EAN-13, GTIN-14


class InvalidBarcodeError(ValueError):
    """Raised when a raw string is not a validly check-digited barcode."""


def _gtin_check_digit(digits: str) -> int:
    """GS1 standard check-digit algorithm, uniform across GTIN-8/12/13/14:
    starting from the rightmost digit *excluding* the check digit itself,
    alternate weights 3, 1, 3, 1, ...; the check digit is
    (10 - (sum % 10)) % 10.
    """
    payload = digits[:-1]
    total = 0
    weight_cycle = (3, 1)
    for index, char in enumerate(reversed(payload)):
        weight = weight_cycle[index % 2]
        total += int(char) * weight
    return (10 - (total % 10)) % 10


@dataclass(frozen=True, slots=True)
class Barcode:
    value: str

    def __post_init__(self) -> None:
        if not self.value.isdigit() or len(self.value) not in _VALID_LENGTHS:
            raise InvalidBarcodeError(
                f"Barcode must be all-digit and one of lengths {_VALID_LENGTHS}: {self.value!r}"
            )
        expected = _gtin_check_digit(self.value)
        actual = int(self.value[-1])
        if expected != actual:
            raise InvalidBarcodeError(
                f"Barcode {self.value!r} failed check-digit validation "
                f"(expected {expected}, got {actual})."
            )

    def __str__(self) -> str:
        return self.value
