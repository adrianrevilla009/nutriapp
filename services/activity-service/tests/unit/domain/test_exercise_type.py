"""ExerciseType value object tests (test-plan section 1)."""

from __future__ import annotations

import pytest

from domain.value_objects.exercise_type import ExerciseType, InvalidExerciseTypeError


@pytest.mark.parametrize(
    "raw_value",
    ["running", "walking", "cycling", "strength_training", "swimming", "other"],
)
def test_each_enumerated_value_is_accepted(raw_value: str) -> None:
    assert ExerciseType(raw_value).value == raw_value


def test_unrecognized_string_raises() -> None:
    with pytest.raises(InvalidExerciseTypeError):
        ExerciseType("rock_climbing")
