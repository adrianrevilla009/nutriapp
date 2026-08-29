"""Pydantic v2 request/response schemas -- infrastructure layer only
(api-conventions SKILL.md). The domain/application layers never import
Pydantic (ADR-0001)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CheckoutSessionRequest(BaseModel):
    success_url: str = Field(..., description="Frontend URL Stripe redirects to on success.")
    cancel_url: str = Field(..., description="Frontend URL Stripe redirects to on cancel.")
    customer_email: str | None = Field(
        default=None, description="Pre-fills Stripe Checkout's email field."
    )


class CheckoutSessionResponse(BaseModel):
    stripe_session_id: str
    checkout_url: str


class EntitlementResponse(BaseModel):
    user_id: str
    entitled: bool
