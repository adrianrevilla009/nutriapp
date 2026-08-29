"""POST /api/v1/billing/checkout-sessions -- creates a Stripe-hosted
Checkout Session for the authenticated user (implementation plan section
1.1). JWT-authenticated via packages/shared-contracts' centralized
dependency (implementation plan section 7).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.create_checkout_session import (
    CreateCheckoutSessionCommand,
    CreateCheckoutSessionHandler,
)
from infrastructure.composition_root import Container, build_repositories
from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_session,
)
from infrastructure.http.error_mapping import map_exception
from infrastructure.http.schemas.billing_schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.post(
    "/checkout-sessions",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a Pro subscription via Stripe-hosted Checkout",
    description="Never collects card data itself -- returns a Stripe Checkout "
    "Session URL the frontend redirects the browser to (PCI scope minimization).",
)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    user_id: Annotated[uuid.UUID, Depends(get_authenticated_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[Container, Depends(get_container)],
) -> CheckoutSessionResponse | JSONResponse:
    subscriptions, _processed, _revocation, _outbox = build_repositories(session)
    handler = CreateCheckoutSessionHandler(subscriptions, container.payment_provider)
    try:
        result = await handler.handle(
            CreateCheckoutSessionCommand(
                user_id=user_id,
                customer_email=body.customer_email,
                success_url=body.success_url,
                cancel_url=body.cancel_url,
                # Generated once per HTTP request, reused across every
                # retry attempt inside the adapter (Stripe's documented
                # idempotency-key best practice, implementation plan
                # section 7) -- never regenerated per attempt.
                idempotency_key=str(uuid.uuid4()),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return map_exception(exc)
    return CheckoutSessionResponse(
        stripe_session_id=result.stripe_session_id, checkout_url=result.url
    )
