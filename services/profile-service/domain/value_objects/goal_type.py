"""GoalType value object -- enum, only LOSE/MAINTAIN/GAIN are valid."""

from __future__ import annotations

from enum import Enum


class InvalidGoalTypeError(Exception):
    """Raised when a goal_type value is not one of LOSE/MAINTAIN/GAIN."""


class GoalType(str, Enum):
    LOSE = "LOSE"
    MAINTAIN = "MAINTAIN"
    GAIN = "GAIN"

    @classmethod
    def from_value(cls, value: str) -> GoalType:
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidGoalTypeError(f"Unsupported goal_type value: {value!r}") from exc
