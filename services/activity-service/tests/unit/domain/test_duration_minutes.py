"""DurationMinutes value object tests (test-plan section 1)."""

from __future__ import annotations

import pytest

from domain.value_objects.duration_minutes import DurationMinutes, InvalidDurationError


def test_zero_raises() -> None:
    with pytest.raises(InvalidDurationError):
        DurationMinutes(0)


def test_one_is_accepted() -> None:
    assert int(DurationMinutes(1)) == 1


def test_negative_raises() -> None:
    with pytest.raises(InvalidDurationError):
        DurationMinutes(-5)
