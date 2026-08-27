import pytest

from domain.value_objects.portion_range_grams import InvalidPortionRangeError, PortionRangeGrams


def test_genuine_range_accepted():
    r = PortionRangeGrams(min_g=50, max_g=150)
    assert r.min_g == 50
    assert r.max_g == 150


def test_min_greater_than_max_rejected():
    with pytest.raises(InvalidPortionRangeError):
        PortionRangeGrams(min_g=150, max_g=50)


def test_zero_or_negative_min_rejected():
    with pytest.raises(InvalidPortionRangeError):
        PortionRangeGrams(min_g=0, max_g=100)


def test_zero_width_range_rejected():
    with pytest.raises(InvalidPortionRangeError):
        PortionRangeGrams(min_g=100, max_g=100)


def test_negative_max_rejected():
    with pytest.raises(InvalidPortionRangeError):
        PortionRangeGrams(min_g=10, max_g=-5)
