"""HandleInvoicePaidHandler -- `invoice.paid` webhook (implementation plan
section 1.2): a renewal invoice was paid for an existing subscription.
Extends `current_period_end` and publishes `SubscriptionRenewed`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from application.errors import SubscriptionNotFoundError
from domain.events.subscription_renewed import build_subscription_renewed_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.processed_webhook_events_repository_port import (
    ProcessedWebhookEventsRepositoryPort,
)
from domain.ports.subscription_repository_port import SubscriptionRepositoryPort
from domain.value_objects.stripe_ids import StripeSubscriptionId


@dataclass(frozen=True, slots=True)
class HandleInvoicePaidCommand:
    stripe_event_id: str
    stripe_subscription_id: StripeSubscriptionId
    new_current_period_end: datetime
    correlation_id: str
    now: datetime


class HandleInvoicePaidHandler:
    def __init__(
        self,
        subscriptions: SubscriptionRepositoryPort,
        processed_events: ProcessedWebhookEventsRepositoryPort,
        outbox: OutboxRepositoryPort,
    ) -> None:
        self._subscriptions = subscriptions
        self._processed_events = processed_events
        self._outbox = outbox

    async def handle(self, command: HandleInvoicePaidCommand) -> None:
        if await self._processed_events.is_processed(command.stripe_event_id):
            return

        subscription = await self._subscriptions.get_by_stripe_subscription_id(
            command.stripe_subscription_id
        )
        if subscription is None:
            raise SubscriptionNotFoundError(
                f"No subscription found for {command.stripe_subscription_id}."
            )

        renewed = subscription.renew(
            current_period_end=command.new_current_period_end, now=command.now
        )
        await self._subscriptions.save(renewed)

        event = build_subscription_renewed_event(
            subscription=renewed, correlation_id=command.correlation_id
        )
        await self._outbox.enqueue(event)

        await self._processed_events.mark_processed(command.stripe_event_id)
