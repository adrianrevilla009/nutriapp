"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.

**Entitlement-rejection status code**: `402 Payment Required`, code
`NOT_ENTITLED` -- reuses `recipe-service`'s repo-wide convention verbatim."""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import InvalidReportRequestError, NotEntitledError
from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from domain.value_objects.deficiency_signal import InvalidDeficiencySignalError
from domain.value_objects.macro_running_total import InvalidMacroRunningTotalError
from domain.value_objects.report_period import InvalidReportPeriodError
from domain.value_objects.streak_summary import InvalidStreakSummaryError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_content(message, code))


def _content(message: str, code: str) -> dict[str, str]:
    body: dict[str, str] = {}
    body["error"] = message
    body["code"] = code
    return body


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (NotEntitledError, status.HTTP_402_PAYMENT_REQUIRED, "NOT_ENTITLED"),
    (InvalidReportRequestError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_REPORT_REQUEST"),
    (InvalidStreakSummaryError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_TREND_REQUEST"),
    (InvalidMacroRunningTotalError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_TREND_REQUEST"),
    (InvalidReportPeriodError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_REPORT_REQUEST"),
    (InvalidDeficiencySignalError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_SIGNAL"),
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
