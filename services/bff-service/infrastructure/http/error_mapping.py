"""Maps unexpected exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.

`GetDashboardHandler` never raises for a downstream-call failure --
those are captured and degraded per-section (application/errors.py's
docstring). This mapping exists only as the defensive, house-style
fallback for a genuinely unexpected error (e.g. a programming error),
same convention as every other service's error_mapping.py.
"""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


def map_exception(exc: Exception) -> JSONResponse:
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
