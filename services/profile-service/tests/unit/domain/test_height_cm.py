from __future__ import annotations

import pytest

from domain.value_objects.height_cm import HeightCm, InvalidHeightError


def test_valid_positive_height_accepted():
    height = HeightCm(175.0)
    assert float(height) == 175.0


@pytest.mark.parametrize("value", [0, -1, -175.0])
def test_zero_or_negative_height_raises(value):
    with pytest.raises(InvalidHeightError):
        HeightCm(value)
