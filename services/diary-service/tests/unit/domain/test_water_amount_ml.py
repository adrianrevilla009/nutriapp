from __future__ import annotations

import pytest

from domain.value_objects.water_amount_ml import InvalidWaterAmountError, WaterAmountMl


def test_positive_value_accepted():
    assert float(WaterAmountMl(250.0)) == 250.0


@pytest.mark.parametrize("amount", [0, -1])
def test_zero_or_negative_raises(amount):
    with pytest.raises(InvalidWaterAmountError):
        WaterAmountMl(amount)
