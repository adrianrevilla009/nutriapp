from datetime import datetime, timedelta, timezone

import pytest

from application.commands.handle_invoice_paid import (
    HandleInvoicePaidCommand,
    HandleInvoicePaidHandler,
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


async def test_renewal_extends_period_and_publishes_event():
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_abc"))
    subs = FakeSubscriptionRepository(seed=[sub])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandleInvoicePaidHandler(subs, processed, outbox)

    new_period_end = NOW + timedelta(days=60)
    await handler.handle(
        HandleInvoicePaidCommand(
            stripe_event_id="evt_2",
            stripe_subscription_id=StripeSubscriptionId("sub_abc"),
            new_current_period_end=new_period_end,
            correlation_id="corr-2",
            now=NOW,
        )
    )

    saved = await subs.get_by_stripe_subscription_id(StripeSubscriptionId("sub_abc"))
    assert saved.current_period_end == new_period_end
    assert [e.event_type for e in outbox.enqueued] == ["SubscriptionRenewed"]


async def test_unknown_subscription_raises_typed_error_and_publishes_nothing():
    subs = FakeSubscriptionRepository()
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandleInvoicePaidHandler(subs, processed, outbox)

    with pytest.raises(SubscriptionNotFoundError):
        await handler.handle(
            HandleInvoicePaidCommand(
                stripe_event_id="evt_3",
                stripe_subscription_id=StripeSubscriptionId("sub_missing"),
                new_current_period_end=NOW,
                correlation_id="corr-3",
                now=NOW,
            )
        )

    assert outbox.enqueued == []


async def test_replayed_event_id_is_a_no_op():
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_abc"))
    subs = FakeSubscriptionRepository(seed=[sub])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandleInvoicePaidHandler(subs, processed, outbox)

    command = HandleInvoicePaidCommand(
        stripe_event_id="evt_replay",
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        new_current_period_end=NOW + timedelta(days=60),
        correlation_id="corr-replay",
        now=NOW,
    )
    await handler.handle(command)
    await handler.handle(command)

    assert len(outbox.enqueued) == 1
