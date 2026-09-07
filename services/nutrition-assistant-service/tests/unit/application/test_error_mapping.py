from __future__ import annotations

from application.errors import AssistantUnavailableError, NotEntitledError
from infrastructure.http.error_mapping import map_exception


def test_not_entitled_maps_to_402() -> None:
    response = map_exception(NotEntitledError("nope"))
    assert response.status_code == 402


def test_assistant_unavailable_maps_to_503() -> None:
    response = map_exception(AssistantUnavailableError("down"))
    assert response.status_code == 503


def test_unmapped_exception_maps_to_500() -> None:
    response = map_exception(ValueError("boom"))
    assert response.status_code == 500
