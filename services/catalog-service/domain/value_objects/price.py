"""Price value object — amount + ISO 4217 currency code. Optional at the
entity level (implementation plan §9.6: a single nullable "best-known"
price, not per-retailer)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ISO_4217_RE = re.compile(r"^[A-Z]{3}$")


class InvalidPriceError(ValueError):
    """Raised for a negative amount or a malformed currency code."""


@dataclass(frozen=True, slots=True)
class Price:
    amount: float
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise InvalidPriceError(f"Price.amount cannot be negative: {self.amount!r}.")
        if not _ISO_4217_RE.match(self.currency):
            raise InvalidPriceError(f"Price.currency must be an ISO 4217 code: {self.currency!r}.")
