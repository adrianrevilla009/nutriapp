"""Maps application/domain exceptions to the standard NutriApp error shape
(api-conventions SKILL.md): {"error": "...", "code": "..."}.

**Entitlement-rejection status code decision** (test-plan section 3: "402
vs 403 -- confirm against an existing Pro-gated precedent if one exists,
otherwise document the choice"): no other service in this codebase has
built a Pro-gated HTTP route yet (recipe-service is the first), so there
is no existing precedent to follow. This service uses **402 Payment
Required** -- the most semantically accurate status for "you can
authenticate fine, but this specific feature requires an active paid
subscription you don't have" (RFC 9110 reserves 402 for exactly this;
403 would conflate "not entitled" with "forbidden regardless of payment
status," which is a different, broader condition). `NOT_ENTITLED` is the
error `code`, so a frontend can branch on the machine-readable code
without depending on the HTTP status number alone.
"""

from __future__ import annotations

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

from application.errors import NotEntitledError, RecipeNotFoundError, UnresolvableIngredientError
from domain.ports.catalog_product_port import CatalogProductUnavailableError
from domain.ports.entitlement_check_port import EntitlementCheckUnavailableError
from domain.value_objects.recipe_ingredient import InvalidQuantityError
from domain.value_objects.servings import InvalidServingsError

logger = structlog.get_logger()


def error_response(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=_content(message, code))


def _content(message: str, code: str) -> dict[str, str]:
    body: dict[str, str] = {}
    body["error"] = message
    body["code"] = code
    return body


_MAPPING: list[tuple[type[Exception], int, str]] = [
    (RecipeNotFoundError, status.HTTP_404_NOT_FOUND, "RECIPE_NOT_FOUND"),
    (UnresolvableIngredientError, status.HTTP_422_UNPROCESSABLE_ENTITY, "UNRESOLVABLE_INGREDIENT"),
    (InvalidQuantityError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_QUANTITY"),
    (InvalidServingsError, status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_SERVINGS"),
    (NotEntitledError, status.HTTP_402_PAYMENT_REQUIRED, "NOT_ENTITLED"),
    (
        CatalogProductUnavailableError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "CATALOG_SERVICE_UNAVAILABLE",
    ),
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
