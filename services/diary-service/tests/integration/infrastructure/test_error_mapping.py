"""map_exception() mapping table -- no I/O, but lives alongside the other
infrastructure tests per this service's existing directory convention.

Regression test for the /implementation-review finding: OptimisticConcurrencyError
was raised by PostgresEventStore.append() but had no entry in error_mapping's
_MAPPING table, so a losing writer in a concurrent-append race got an opaque
500 instead of a 409 the client could sensibly retry on.
"""

from __future__ import annotations

import json

from domain.entities.fasting_window import OverlappingFastingWindowError
from domain.ports.event_store_port import OptimisticConcurrencyError
from infrastructure.http.error_mapping import map_exception


def test_optimistic_concurrency_error_maps_to_409() -> None:
    response = map_exception(OptimisticConcurrencyError("lost the race"))
    assert response.status_code == 409
    body = json.loads(response.body)
    assert body["code"] == "CONCURRENT_MODIFICATION"


def test_known_domain_error_still_maps_correctly() -> None:
    response = map_exception(OverlappingFastingWindowError("already open"))
    assert response.status_code == 409
    body = json.loads(response.body)
    assert body["code"] == "FASTING_WINDOW_OVERLAP"


def test_unmapped_exception_falls_back_to_500() -> None:
    response = map_exception(RuntimeError("boom"))
    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["code"] == "INTERNAL_ERROR"
