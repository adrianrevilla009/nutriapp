"""HandleSubscriptionCreatedHandler -- `customer.subscription.created`
webhook (reviewer-agent finding, this session's fix): Stripe's real
Subscription object payload carries the authoritative `current_period_end`
(unlike `checkout.session.completed`'s payload, which never does) --
consuming this event replaces `HandleCheckoutCompletedHandler`'s
best-estimate fallback with the real value, without adding a third
`PaymentProviderPort` operation (an outbound "retrieve subscription"
call).

Publishes NO domain event of its own -- `SubscriptionStarted`/
`EntitlementGranted` remain exclusively `HandleCheckoutCompletedHandler`'s
responsibility (this event is an internal Stripe-webhook-consumption
detail feeding that existing flow, not a new user-facing fact).

Ordering safety: Stripe does not strictly guarantee `checkout.session.completed`
arrives before or after `customer.subscription.created` for the same new
subscription. Both handlers are safe in either order:
- If this event arrives FIRST (no existing row): creates the subscription
  row now, using this event's own `metadata.user_id` (set at Checkout
  Session creation via `subscription_data[metadata][user_id]` --
  `StripePaymentAdapter._build_checkout_session_form_body`) and its real
  `current_period_end`. `HandleCheckoutCompletedHandler`, when it later
  arrives, finds the row already correct and does not overwrite
  `current_period_end` with a guess.
- If this event arrives SECOND (row already exists, created by
  `HandleCheckoutCompletedHandler`'s guess): corrects `current_period_end`
  to the authoritative value via `Subscription.correct_period_end`,
  leaving every other field untouched.
Both branches are idempotent (dedupe by this event's own Stripe `event_id`,
distinct from `checkout.session.completed`'s).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.entities.subscription import Subscription
from domain.ports.processed_webhook_events_repository_port import (
    ProcessedWebhookEventsRepositoryPort,
)
from domain.ports.subscription_repository_port import SubscriptionRepositoryPort
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId


@dataclass(frozen=True, slots=True)
class HandleSubscriptionCreatedCommand:
    stripe_event_id: str
    user_id: uuid.UUID
    stripe_customer_id: StripeCustomerId
    stripe_subscription_id: StripeSubscriptionId
    current_period_end: datetime
    now: datetime


class HandleSubscriptionCreatedHandler:
    def __init__(
        self,
        subscriptions: SubscriptionRepositoryPort,
        processed_events: ProcessedWebhookEventsRepositoryPort,
    ) -> None:
        self._subscriptions = subscriptions
        self._processed_events = processed_events

    async def handle(self, command: HandleSubscriptionCreatedCommand) -> None:
        if await self._processed_events.is_processed(command.stripe_event_id):
            return

        existing = await self._subscriptions.get_by_stripe_subscription_id(
            command.stripe_subscription_id
        )
        if existing is not None:
            corrected = existing.correct_period_end(command.current_period_end, command.now)
            await self._subscriptions.save(corrected)
        else:
            created = Subscription.start(
                subscription_id=uuid.uuid4(),
                user_id=command.user_id,
                stripe_customer_id=command.stripe_customer_id,
                stripe_subscription_id=command.stripe_subscription_id,
                current_period_end=command.current_period_end,
                now=command.now,
            )
            await self._subscriptions.save(created)

        await self._processed_events.mark_processed(command.stripe_event_id)
