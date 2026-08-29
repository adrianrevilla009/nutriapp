"""CreateCheckoutSessionHandler -- backs `POST /api/v1/billing/checkout-sessions`
(implementation plan section 1.1). Never collects card data itself: it
only ever asks `PaymentProviderPort` for a Stripe-hosted Checkout Session
URL and returns it (PCI scope minimization, billing-agent.md)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from application.dto.checkout_session_result import CheckoutSessionResult
from application.errors import SubscriptionAlreadyActiveError
from domain.ports.payment_provider_port import PaymentProviderPort
from domain.ports.subscription_repository_port import SubscriptionRepositoryPort
from domain.value_objects.subscription_status import SubscriptionStatus


@dataclass(frozen=True, slots=True)
class CreateCheckoutSessionCommand:
    user_id: uuid.UUID
    customer_email: str | None
    success_url: str
    cancel_url: str
    idempotency_key: str


class CreateCheckoutSessionHandler:
    def __init__(
        self,
        subscriptions: SubscriptionRepositoryPort,
        payment_provider: PaymentProviderPort,
    ) -> None:
        self._subscriptions = subscriptions
        self._payment_provider = payment_provider

    async def handle(self, command: CreateCheckoutSessionCommand) -> CheckoutSessionResult:
        existing = await self._subscriptions.get_by_user_id(command.user_id)
        if existing is not None and existing.status == SubscriptionStatus.active():
            raise SubscriptionAlreadyActiveError(
                f"User {command.user_id} already has an active subscription."
            )

        session = await self._payment_provider.create_checkout_session(
            user_id=command.user_id,
            customer_email=command.customer_email,
            success_url=command.success_url,
            cancel_url=command.cancel_url,
            idempotency_key=command.idempotency_key,
        )
        return CheckoutSessionResult(stripe_session_id=session.stripe_session_id, url=session.url)
