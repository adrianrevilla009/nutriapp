"""ActivityLevel value object -- enum, only the documented values are valid."""

from __future__ import annotations

from enum import Enum


class InvalidActivityLevelError(Exception):
    """Raised when an activity level value is not a documented enum value."""


class ActivityLevel(str, Enum):
    SEDENTARY = "SEDENTARY"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    ACTIVE = "ACTIVE"
    VERY_ACTIVE = "VERY_ACTIVE"

    @classmethod
    def from_value(cls, value: str) -> ActivityLevel:
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidActivityLevelError(f"Unsupported activity_level value: {value!r}") from exc
