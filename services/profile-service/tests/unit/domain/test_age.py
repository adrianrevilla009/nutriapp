from __future__ import annotations

import pytest

from domain.value_objects.age import Age, InvalidAgeError


@pytest.mark.parametrize("value", [1, 30, 120])
def test_valid_age_accepted(value):
    assert int(Age(value)) == value


@pytest.mark.parametrize("value", [0, -1, 121, 200])
def test_out_of_range_age_raises(value):
    with pytest.raises(InvalidAgeError):
        Age(value)
