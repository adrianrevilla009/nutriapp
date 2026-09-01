"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.

**Entitlement-rejection status code**: `402 Payment Required`, code
`NOT_ENTITLED` -- reuses `recipe-service`'s exact convention verbatim, now
a repo-wide standard (implementation plan section 3), not a per-service
decision to re-litigate."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import NotEntitledError
from domain.entities.follow import SelfFollowError
from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from domain.value_objects.feed_entry import InvalidFeedEntryError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_content(message, code))


def _content(message: str, code: str) -> dict[str, str]:
    body: dict[str, str] = {}
    body["error"] = message
    body["code"] = code
    return body


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (SelfFollowError, status.HTTP_422_UNPROCESSABLE_ENTITY, "SELF_FOLLOW"),
    (InvalidFeedEntryError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_FEED_ENTRY"),
    (NotEntitledError, status.HTTP_402_PAYMENT_REQUIRED, "NOT_ENTITLED"),
    (
        EntitlementCheckUnavailableError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "ENTITLEMENT_CHECK_UNAVAILABLE",
    ),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
