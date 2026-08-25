"""Sex value object -- enum, only the documented values are valid."""

from __future__ import annotations

from enum import Enum


class InvalidSexError(Exception):
    """Raised when a sex value is not one of the documented enum values."""


class Sex(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"

    @classmethod
    def from_value(cls, value: str) -> Sex:
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidSexError(f"Unsupported sex value: {value!r}") from exc
