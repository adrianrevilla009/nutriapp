"""GET /internal/v1/billing/entitlements/{user_id} -- internal-only, never
routed through Kong (implementation plan section 1.4). The synchronous
fallback compensation path for the `ProUpgradeEntitlementPropagation` saga
(docs/sagas-and-distributed-transactions.md) -- callers wrap this in a
circuit breaker on their OWN side (resilience-patterns SKILL.md), per
every prior internal-endpoint precedent (identity-service's
`internal_token_routes.py`, catalog-service's `internal_catalog_routes.py`).

`X-Internal-Service-Credential` header, constant-time-compared -- mirrors
identity-service/catalog-service's single-shared-credential pattern (not
profile-service's fully-segregated-port pattern: that extra hardening was
specifically justified by Article 9 special-category health data, which
does not apply here).
"""

from __future__ import annotations

import hmac
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.errors import InvalidCallerCredentialError
from application.queries.get_entitlement_for_user import (
    GetEntitlementForUserHandler,
    GetEntitlementForUserQuery,
)
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import get_container, get_session
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.billing_schemas import EntitlementResponse

router = APIRouter(prefix="/internal/v1/billing", tags=["internal"])


@router.get(
    "/entitlements/{user_id}",
    response_model=EntitlementResponse,
    summary="Synchronous entitlement fallback check (internal only)",
    description="Service-to-service only. Never routed through Kong. Callers wrap "
    "this in their own circuit breaker. Never errors for a user with no subscription "
    "record -- returns entitled: false (fail safe, saga-conventions SKILL.md).",
)
async def get_entitlement(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
    x_internal_service_credential: Annotated[str, Header()] = "",
) -> EntitlementResponse | JSONResponse:
    try:
        if not hmac.compare_digest(
            x_internal_service_credential, container.settings.internal_entitlement_credential
        ):
            raise InvalidCallerCredentialError("Invalid internal service credential.")

        subscriptions, _processed, _revocation, _outbox = build_repositories(session)
        handler = GetEntitlementForUserHandler(subscriptions)
        result = await handler.handle(GetEntitlementForUserQuery(user_id=user_id))
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return EntitlementResponse(user_id=str(user_id), entitled=result.entitled)
