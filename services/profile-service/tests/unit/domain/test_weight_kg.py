from __future__ import annotations

import pytest

from domain.value_objects.weight_kg import InvalidWeightError, WeightKg


def test_valid_positive_weight_accepted():
    weight = WeightKg(70.5)
    assert float(weight) == 70.5


@pytest.mark.parametrize("value", [0, -1, -70.5])
def test_zero_or_negative_weight_raises(value):
    with pytest.raises(InvalidWeightError):
        WeightKg(value)
