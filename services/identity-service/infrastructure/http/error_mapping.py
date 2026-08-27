"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.
"""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import (
    InvalidCallerCredentialError,
    InvalidCredentialsError,
    InvalidTokenError,
    RateLimitedError,
)
from domain.entities.token import TokenExpiredError, TokenRevokedError
from domain.ports.rate_limiter_port import RateLimiterUnavailableError
from domain.services.registration_policy import EmailAlreadyRegisteredError
from domain.value_objects.email import InvalidEmailError
from domain.value_objects.password import WeakPasswordError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (RateLimiterUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE, "RATE_LIMITER_UNAVAILABLE"),
    (RateLimitedError, status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED"),
    (InvalidCredentialsError, status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS"),
    (InvalidCallerCredentialError, status.HTTP_401_UNAUTHORIZED, "INVALID_CALLER_CREDENTIAL"),
    (InvalidTokenError, status.HTTP_400_BAD_REQUEST, "INVALID_TOKEN"),
    (TokenRevokedError, status.HTTP_401_UNAUTHORIZED, "TOKEN_REVOKED"),
    (TokenExpiredError, status.HTTP_401_UNAUTHORIZED, "TOKEN_EXPIRED"),
    (EmailAlreadyRegisteredError, status.HTTP_409_CONFLICT, "EMAIL_ALREADY_REGISTERED"),
    (WeakPasswordError, status.HTTP_400_BAD_REQUEST, "WEAK_PASSWORD"),
    (InvalidEmailError, status.HTTP_400_BAD_REQUEST, "INVALID_EMAIL"),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
