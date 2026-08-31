from __future__ import annotations

import pytest

from domain.value_objects.servings import InvalidServingsError, Servings


def test_positive_servings_accepted():
    assert int(Servings(1)) == 1
    assert int(Servings(4)) == 4


def test_zero_servings_raises():
    with pytest.raises(InvalidServingsError):
        Servings(0)


def test_negative_servings_raises():
    with pytest.raises(InvalidServingsError):
        Servings(-2)
