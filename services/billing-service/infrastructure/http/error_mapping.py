"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import (
    InvalidCallerCredentialError,
    SubscriptionAlreadyActiveError,
    SubscriptionNotFoundError,
)
from domain.ports.payment_provider_port import WebhookSignatureVerificationError
from domain.value_objects.stripe_ids import InvalidStripeIdError
from domain.value_objects.subscription_status import InvalidSubscriptionStatusError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_content(message, code))


def _content(message: str, code: str) -> dict[str, str]:
    body: dict[str, str] = {}
    body["error"] = message
    body["code"] = code
    return body


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (SubscriptionAlreadyActiveError, status.HTTP_409_CONFLICT, "SUBSCRIPTION_ALREADY_ACTIVE"),
    (SubscriptionNotFoundError, status.HTTP_404_NOT_FOUND, "SUBSCRIPTION_NOT_FOUND"),
    (InvalidCallerCredentialError, status.HTTP_401_UNAUTHORIZED, "INVALID_CALLER_CREDENTIAL"),
    (
        WebhookSignatureVerificationError,
        status.HTTP_401_UNAUTHORIZED,
        "INVALID_WEBHOOK_SIGNATURE",
    ),
    (InvalidStripeIdError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_STRIPE_ID"),
    (
        InvalidSubscriptionStatusError,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_SUBSCRIPTION_STATUS",
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
