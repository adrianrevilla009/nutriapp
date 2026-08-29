from datetime import datetime, timezone

import pytest

from application.commands.handle_payment_failed import (
    HandlePaymentFailedCommand,
    HandlePaymentFailedHandler,
)
from application.errors import SubscriptionNotFoundError
from domain.value_objects.stripe_ids import StripeSubscriptionId
from tests.fixtures.factories import (
    FakeOutboxRepository,
    FakeProcessedWebhookEventsRepository,
    FakeSubscriptionRepository,
    make_subscription,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_marks_past_due_and_publishes_payment_failed_without_revoking():
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_abc"))
    subs = FakeSubscriptionRepository(seed=[sub])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandlePaymentFailedHandler(subs, processed, outbox)

    await handler.handle(
        HandlePaymentFailedCommand(
            stripe_event_id="evt_6",
            stripe_subscription_id=StripeSubscriptionId("sub_abc"),
            correlation_id="corr-6",
            now=NOW,
        )
    )

    saved = await subs.get_by_stripe_subscription_id(StripeSubscriptionId("sub_abc"))
    assert saved.status.value == "past_due"
    assert saved.is_entitled(NOW) is True
    assert [e.event_type for e in outbox.enqueued] == ["SubscriptionPaymentFailed"]


async def test_unknown_subscription_raises():
    subs = FakeSubscriptionRepository()
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandlePaymentFailedHandler(subs, processed, outbox)

    with pytest.raises(SubscriptionNotFoundError):
        await handler.handle(
            HandlePaymentFailedCommand(
                stripe_event_id="evt_7",
                stripe_subscription_id=StripeSubscriptionId("sub_missing"),
                correlation_id="corr-7",
                now=NOW,
            )
        )


async def test_replayed_event_id_is_a_no_op():
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_abc"))
    subs = FakeSubscriptionRepository(seed=[sub])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandlePaymentFailedHandler(subs, processed, outbox)

    command = HandlePaymentFailedCommand(
        stripe_event_id="evt_replay",
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        correlation_id="corr-replay",
        now=NOW,
    )
    await handler.handle(command)
    await handler.handle(command)

    assert len(outbox.enqueued) == 1
