"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.

Note what is deliberately NOT here: a provider failure or a catalog-lookup
failure is never an unhandled exception at this layer -- both
`AnalyzeFoodPhotoHandler` and `DecodeBarcodeHandler` catch those
internally and return a normal `200` response with
`status="unavailable"` (implementation plan section 1, acceptance
criterion 5). This module only maps genuine client-request errors."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import InvalidImageError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (InvalidImageError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_IMAGE"),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
