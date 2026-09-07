"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.

Entitlement-rejection status code: 402 Payment Required, code
NOT_ENTITLED -- reuses recipe-service's/analytics-service's repo-wide
convention verbatim."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import AssistantUnavailableError, NotEntitledError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (NotEntitledError, status.HTTP_402_PAYMENT_REQUIRED, "NOT_ENTITLED"),
    (AssistantUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE, "ASSISTANT_UNAVAILABLE"),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
