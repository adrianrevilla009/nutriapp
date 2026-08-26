from __future__ import annotations

import pytest

from domain.value_objects.quantity import InvalidQuantityError, Quantity


def test_positive_amount_and_supported_unit_accepted():
    q = Quantity(amount=100.0, unit="g")
    assert q.amount == 100.0
    assert q.unit == "g"


@pytest.mark.parametrize("amount", [0, -5])
def test_zero_or_negative_amount_raises(amount):
    with pytest.raises(InvalidQuantityError):
        Quantity(amount=amount, unit="g")


def test_unsupported_unit_raises():
    with pytest.raises(InvalidQuantityError):
        Quantity(amount=1.0, unit="lb")
