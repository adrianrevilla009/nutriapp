"""SectionStatus value object -- test-plan section 1."""

from __future__ import annotations

import pytest

from domain.value_objects.section_status import SectionStatus


def test_available__carries_data_and_status():
    status = SectionStatus.available({"calories_kcal": 2000})

    assert status.status == "available"
    assert status.data == {"calories_kcal": 2000}
    assert status.reason is None


def test_unavailable__downstream_error__no_data_reason_preserved():
    status = SectionStatus.unavailable(reason="downstream_error")

    assert status.status == "unavailable"
    assert status.data is None
    assert status.reason == "downstream_error"


def test_unavailable__not_yet_computed__no_data_reason_preserved():
    status = SectionStatus.unavailable(reason="not_yet_computed")

    assert status.status == "unavailable"
    assert status.data is None
    assert status.reason == "not_yet_computed"


def test_unavailable__unrecognized_reason__raises_value_error():
    with pytest.raises(ValueError, match="Unrecognized"):
        SectionStatus.unavailable(reason="something_else")
