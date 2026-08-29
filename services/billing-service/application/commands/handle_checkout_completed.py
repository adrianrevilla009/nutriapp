"""HandleCheckoutCompletedHandler -- `checkout.session.completed` webhook
(implementation plan section 1.2): a brand new Pro subscription was paid
for via Stripe's hosted Checkout. Persists the subscription, then
publishes `SubscriptionStarted` and `EntitlementGranted` via the Outbox
(ADR-0002/messaging-conventions SKILL.md) -- never a direct publish.

Idempotent: replaying the same Stripe `event_id` is a no-op (test-plan
section 1's mandatory idempotency case) -- the dedupe check runs BEFORE
any repository write or event enqueue.

`current_period_end_estimate` (reviewer-agent finding, this session's
fix): Stripe's `checkout.session.completed` payload never carries the
new subscription's real `current_period_end` -- only
`customer.subscription.created`'s payload does
(`handle_subscription_created.py`). Stripe does not strictly order the
two events, so this handler is ordering-safe: if a subscription row
already exists for this `stripe_subscription_id` (meaning
`customer.subscription.created` arrived FIRST, already carrying the
authoritative value), this handler reuses that row's real
`current_period_end` and never overwrites it with the estimate. Only when
creating a brand new row (this event arrived first) does it fall back to
`current_period_end_estimate` as a best-effort placeholder, corrected
shortly after once `customer.subscription.created` arrives.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.entities.subscription import Subscription
from domain.events.entitlement_granted import build_entitlement_granted_event
from domain.events.subscription_started import build_subscription_started_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.processed_webhook_events_repository_port import (
    ProcessedWebhookEventsRepositoryPort,
)
from domain.ports.subscription_repository_port import SubscriptionRepositoryPort
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId


@dataclass(frozen=True, slots=True)
class HandleCheckoutCompletedCommand:
    stripe_event_id: str
    user_id: uuid.UUID
    stripe_customer_id: StripeCustomerId
    stripe_subscription_id: StripeSubscriptionId
    # Best-effort placeholder, used ONLY if no row exists yet for this
    # stripe_subscription_id -- see module docstring's ordering-safety note.
    current_period_end_estimate: datetime
    correlation_id: str
    now: datetime


class HandleCheckoutCompletedHandler:
    def __init__(
        self,
        subscriptions: SubscriptionRepositoryPort,
        processed_events: ProcessedWebhookEventsRepositoryPort,
        outbox: OutboxRepositoryPort,
    ) -> None:
        self._subscriptions = subscriptions
        self._processed_events = processed_events
        self._outbox = outbox

    async def handle(self, command: HandleCheckoutCompletedCommand) -> None:
        if await self._processed_events.is_processed(command.stripe_event_id):
            return

        existing = await self._subscriptions.get_by_stripe_subscription_id(
            command.stripe_subscription_id
        )
        if existing is not None:
            # customer.subscription.created already arrived and created
            # this row with the REAL current_period_end -- reuse it as-is,
            # never overwrite with the estimate.
            subscription = existing
        else:
            subscription = Subscription.start(
                subscription_id=uuid.uuid4(),
                user_id=command.user_id,
                stripe_customer_id=command.stripe_customer_id,
                stripe_subscription_id=command.stripe_subscription_id,
                current_period_end=command.current_period_end_estimate,
                now=command.now,
            )
            await self._subscriptions.save(subscription)

        started_event = build_subscription_started_event(
            subscription=subscription, correlation_id=command.correlation_id
        )
        await self._outbox.enqueue(started_event)
        granted_event = build_entitlement_granted_event(
            user_id=command.user_id,
            correlation_id=command.correlation_id,
            causation_id=str(started_event.event_id),
        )
        await self._outbox.enqueue(granted_event)

        await self._processed_events.mark_processed(command.stripe_event_id)
