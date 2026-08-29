"""map_exception -- the defensive house-style fallback for a genuinely
unexpected error (application/errors.py's docstring: GetDashboardHandler
itself never raises)."""

from __future__ import annotations

from infrastructure.http.error_mapping import map_exception


def test_map_exception_returns_500_internal_error_shape():
    response = map_exception(RuntimeError("boom"))

    assert response.status_code == 500
    assert response.body is not None
