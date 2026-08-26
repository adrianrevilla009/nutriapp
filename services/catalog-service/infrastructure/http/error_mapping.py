"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import ProductNotFoundError, UnsupportedSearchFilterError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (UnsupportedSearchFilterError, status.HTTP_422_UNPROCESSABLE_ENTITY, "UNSUPPORTED_FILTER"),
    (ProductNotFoundError, status.HTTP_404_NOT_FOUND, "PRODUCT_NOT_FOUND"),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
