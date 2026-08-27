"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): dict(error=..., code=...)."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import (
    InvalidCallerCredentialError,
    ProfileNotFoundError,
    RevealRateLimitedError,
)
from domain.entities.profile import (
    ConsentRequiredError,
    GoalAlreadyExistsError,
    NoExistingGoalError,
    UnsupportedMetricTypeError,
)
from domain.ports.rate_limiter_port import RateLimiterUnavailableError
from domain.services.goal_policy import MissingGoalTargetDateError
from domain.value_objects.activity_level import InvalidActivityLevelError
from domain.value_objects.age import InvalidAgeError
from domain.value_objects.goal_target import InvalidGoalTargetError
from domain.value_objects.goal_type import InvalidGoalTypeError
from domain.value_objects.height_cm import InvalidHeightError
from domain.value_objects.sex import InvalidSexError
from domain.value_objects.weight_kg import InvalidWeightError
from infrastructure.security.kms_envelope_data_encryption import (
    KmsCallFailedError,
    KmsCircuitOpenError,
)

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message, "code": code})


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (ProfileNotFoundError, status.HTTP_404_NOT_FOUND, "PROFILE_NOT_FOUND"),
    (ConsentRequiredError, status.HTTP_403_FORBIDDEN, "CONSENT_REQUIRED"),
    (UnsupportedMetricTypeError, status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_METRIC_TYPE"),
    (GoalAlreadyExistsError, status.HTTP_409_CONFLICT, "GOAL_ALREADY_EXISTS"),
    (NoExistingGoalError, status.HTTP_409_CONFLICT, "NO_EXISTING_GOAL"),
    (MissingGoalTargetDateError, status.HTTP_400_BAD_REQUEST, "MISSING_GOAL_TARGET_DATE"),
    (InvalidGoalTargetError, status.HTTP_400_BAD_REQUEST, "INVALID_GOAL_TARGET"),
    (InvalidGoalTypeError, status.HTTP_400_BAD_REQUEST, "INVALID_GOAL_TYPE"),
    (InvalidWeightError, status.HTTP_400_BAD_REQUEST, "INVALID_WEIGHT"),
    (InvalidHeightError, status.HTTP_400_BAD_REQUEST, "INVALID_HEIGHT"),
    (InvalidAgeError, status.HTTP_400_BAD_REQUEST, "INVALID_AGE"),
    (InvalidSexError, status.HTTP_400_BAD_REQUEST, "INVALID_SEX"),
    (InvalidActivityLevelError, status.HTTP_400_BAD_REQUEST, "INVALID_ACTIVITY_LEVEL"),
    (KmsCircuitOpenError, status.HTTP_503_SERVICE_UNAVAILABLE, "ENCRYPTION_UNAVAILABLE"),
    (KmsCallFailedError, status.HTTP_503_SERVICE_UNAVAILABLE, "ENCRYPTION_UNAVAILABLE"),
    # Internal reveal-metrics endpoint only (implementation plan Addendum 2)
    # -- never a differentiated message beyond these generic ones (no
    # detail that would help an attacker distinguish failure modes, and
    # never any biometric field value, per requirement 7).
    (InvalidCallerCredentialError, status.HTTP_401_UNAUTHORIZED, "INVALID_CALLER_CREDENTIAL"),
    (RevealRateLimitedError, status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED"),
    (RateLimiterUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE, "RATE_LIMITER_UNAVAILABLE"),
]


def map_exception(exc: Exception) -> JSONResponse:
    for exc_type, status_code, code in _MAPPING:
        if isinstance(exc, exc_type):
            return error_response(status_code, str(exc) or code, code)
    logger.exception("unmapped_exception", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_ERROR"
    )
