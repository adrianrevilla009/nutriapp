from __future__ import annotations

import pytest

from domain.value_objects.goal_type import GoalType, InvalidGoalTypeError


@pytest.mark.parametrize("value", ["LOSE", "MAINTAIN", "GAIN"])
def test_documented_goal_type_values_valid(value):
    assert GoalType.from_value(value).value == value


def test_unknown_goal_type_value_raises():
    with pytest.raises(InvalidGoalTypeError):
        GoalType.from_value("NOT_A_GOAL")
