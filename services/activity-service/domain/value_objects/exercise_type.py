"""ExerciseType -- a small closed enum, not free text (implementation plan
section 9, open question 1). `OTHER` covers anything not enumerated; the
optional free-text label carried alongside it (see
`domain/entities/exercise_entry.py`) is for display only and never
aggregable -- it is never itself a member of this enum.
"""

from __future__ import annotations

from enum import Enum
from typing import NoReturn


class InvalidExerciseTypeError(ValueError):
    """Raised when a raw string does not match any recognized exercise type."""


class ExerciseType(str, Enum):
    RUNNING = "running"
    WALKING = "walking"
    CYCLING = "cycling"
    STRENGTH_TRAINING = "strength_training"
    SWIMMING = "swimming"
    OTHER = "other"

    @classmethod
    def _missing_(cls, value: object) -> NoReturn:
        raise InvalidExerciseTypeError(f"{value!r} is not a recognized exercise type.")
