"""GET /internal/v1/catalog/lookup — internal-only, never routed through
Kong (implementation plan Addendum 2). Called by food-recognition-service
to resolve a scanned barcode to a catalog product synchronously.

Single port/single app, added to the same FastAPI app catalog-service
already serves — mirrors identity-service's
`infrastructure/http/routes/internal_token_routes.py` precedent (single
port, `X-Internal-Service-Credential` header checked against a configured
value), not profile-service's fully-segregated-port pattern: that extra
hardening was specifically justified by Article 9 special-category health
data (CLAUDE.md section 8), and product nutrition-facts data is
reference/catalog data, not personal data, so the lighter identity-service
precedent is the correct-weight control here.

Reuses the exact same response shape `GET /api/v1/catalog/products/{id}`
already returns (`product_to_response`/`ProductResponse`) — no second
schema for the same shape.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.errors import InvalidCallerCredentialError
from application.queries.get_product_by_barcode import (
    GetProductByBarcodeHandler,
    GetProductByBarcodeQuery,
)
from domain.value_objects.barcode import Barcode
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.product_schemas import ProductResponse, product_to_response

router = APIRouter(prefix="/internal/v1/catalog", tags=["internal"])


@router.get(
    "/lookup",
    response_model=ProductResponse,
    summary="Resolve a barcode to a catalogued product (internal only)",
    description="Service-to-service only. Never routed through Kong. Called by "
    "food-recognition-service to resolve a scanned barcode synchronously. Returns "
    "the same shape as GET /api/v1/catalog/products/{id}.",
)
async def lookup_product_by_barcode(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    barcode: Annotated[str, Query(description="Barcode/GTIN to resolve")],
    x_internal_service_credential: Annotated[str, Header()] = "",
) -> ProductResponse | JSONResponse:
    try:
        if not hmac.compare_digest(
            x_internal_service_credential, container.settings.internal_lookup_credential
        ):
            raise InvalidCallerCredentialError("Invalid internal service credential.")

        products_repo, _outbox_repo, _search_read = build_repositories(session)
        handler = GetProductByBarcodeHandler(products_repo)
        product = await handler.handle(GetProductByBarcodeQuery(barcode=Barcode(barcode)))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return product_to_response(product)
