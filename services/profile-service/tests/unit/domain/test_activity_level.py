from __future__ import annotations

import pytest

from domain.value_objects.activity_level import ActivityLevel, InvalidActivityLevelError


@pytest.mark.parametrize("value", ["SEDENTARY", "LIGHT", "MODERATE", "ACTIVE", "VERY_ACTIVE"])
def test_documented_activity_level_values_valid(value):
    assert ActivityLevel.from_value(value).value == value


def test_unknown_activity_level_value_raises():
    with pytest.raises(InvalidActivityLevelError):
        ActivityLevel.from_value("NOT_A_LEVEL")
