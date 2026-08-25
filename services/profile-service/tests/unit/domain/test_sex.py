from __future__ import annotations

import pytest

from domain.value_objects.sex import InvalidSexError, Sex


@pytest.mark.parametrize("value", ["MALE", "FEMALE", "OTHER"])
def test_documented_sex_values_valid(value):
    assert Sex.from_value(value).value == value


def test_unknown_sex_value_raises():
    with pytest.raises(InvalidSexError):
        Sex.from_value("NOT_A_SEX")
