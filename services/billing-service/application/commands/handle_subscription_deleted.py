"""HandleSubscriptionDeletedHandler -- `customer.subscription.deleted`
webhook (implementation plan section 1.2/1.5): records the cancellation
and defers `EntitlementRevoked` to `current_period_end` -- billing-agent.md's
"cancellation retains access through the paid period's end" rule.
Publishes `SubscriptionCancelled` immediately (it is a true fact about
what happened now); `EntitlementRevoked` is published later, only once
`ProcessDueRevocationsHandler` finds the resulting revocation-schedule row
actually due.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from application.errors import SubscriptionNotFoundError
from domain.events.subscription_cancelled import build_subscription_cancelled_event
from domain.ports.entitlement_revocation_schedule_repository_port import (
    EntitlementRevocationScheduleRepositoryPort,
)
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.processed_webhook_events_repository_port import (
    ProcessedWebhookEventsRepositoryPort,
)
from domain.ports.subscription_repository_port import SubscriptionRepositoryPort
from domain.value_objects.stripe_ids import StripeSubscriptionId


@dataclass(frozen=True, slots=True)
class HandleSubscriptionDeletedCommand:
    stripe_event_id: str
    stripe_subscription_id: StripeSubscriptionId
    correlation_id: str
    now: datetime


class HandleSubscriptionDeletedHandler:
    def __init__(
        self,
        subscriptions: SubscriptionRepositoryPort,
        processed_events: ProcessedWebhookEventsRepositoryPort,
        outbox: OutboxRepositoryPort,
        revocation_schedule: EntitlementRevocationScheduleRepositoryPort,
    ) -> None:
        self._subscriptions = subscriptions
        self._processed_events = processed_events
        self._outbox = outbox
        self._revocation_schedule = revocation_schedule

    async def handle(self, command: HandleSubscriptionDeletedCommand) -> None:
        if await self._processed_events.is_processed(command.stripe_event_id):
            return

        subscription = await self._subscriptions.get_by_stripe_subscription_id(
            command.stripe_subscription_id
        )
        if subscription is None:
            raise SubscriptionNotFoundError(
                f"No subscription found for {command.stripe_subscription_id}."
            )

        cancelled = subscription.cancel(command.now)
        await self._subscriptions.save(cancelled)

        event = build_subscription_cancelled_event(
            subscription=cancelled, correlation_id=command.correlation_id
        )
        await self._outbox.enqueue(event)

        # Deferred revocation (never immediate) -- billing-agent.md.
        await self._revocation_schedule.upsert_pending(
            cancelled.user_id, cancelled.current_period_end
        )

        await self._processed_events.mark_processed(command.stripe_event_id)
