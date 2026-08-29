import uuid
from datetime import datetime, timedelta, timezone

from application.commands.handle_checkout_completed import (
    HandleCheckoutCompletedCommand,
    HandleCheckoutCompletedHandler,
)
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId
from tests.fixtures.factories import (
    FakeOutboxRepository,
    FakeProcessedWebhookEventsRepository,
    FakeSubscriptionRepository,
    make_subscription,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _command(event_id="evt_1", user_id=None):
    return HandleCheckoutCompletedCommand(
        stripe_event_id=event_id,
        user_id=user_id or uuid.uuid4(),
        stripe_customer_id=StripeCustomerId("cus_abc"),
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        current_period_end_estimate=NOW + timedelta(days=30),
        correlation_id="corr-1",
        now=NOW,
    )


async def test_persists_subscription_and_publishes_events_exactly_once():
    subs = FakeSubscriptionRepository()
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandleCheckoutCompletedHandler(subs, processed, outbox)

    command = _command()
    await handler.handle(command)

    assert subs.save_calls == 1
    saved = await subs.get_by_user_id(command.user_id)
    assert saved is not None
    assert saved.status.value == "active"
    event_types = [e.event_type for e in outbox.enqueued]
    assert event_types == ["SubscriptionStarted", "EntitlementGranted"]


async def test_replayed_event_id_is_a_no_op():
    subs = FakeSubscriptionRepository()
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandleCheckoutCompletedHandler(subs, processed, outbox)

    command = _command(event_id="evt_replay")
    await handler.handle(command)
    await handler.handle(command)

    assert subs.save_calls == 1
    assert len(outbox.enqueued) == 2


async def test_reuses_existing_real_period_end_never_overwrites_with_estimate():
    """Ordering-safety fix (reviewer-agent finding): if
    customer.subscription.created already created the row with the REAL
    current_period_end before checkout.session.completed arrives, this
    handler must reuse that real value, never clobber it with the
    best-effort estimate."""
    user_id = uuid.uuid4()
    real_period_end = NOW + timedelta(days=31)  # a real calendar month, not the 30-day guess
    existing = make_subscription(
        user_id=user_id,
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        current_period_end=real_period_end,
    )
    subs = FakeSubscriptionRepository(seed=[existing])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    handler = HandleCheckoutCompletedHandler(subs, processed, outbox)

    command = _command(user_id=user_id)
    await handler.handle(command)

    # No new row created -- the existing one (with its real period end) is reused.
    assert subs.save_calls == 0
    saved = await subs.get_by_user_id(user_id)
    assert saved.current_period_end == real_period_end
    event_types = [e.event_type for e in outbox.enqueued]
    assert event_types == ["SubscriptionStarted", "EntitlementGranted"]
    started_event = outbox.enqueued[0]
    assert started_event.payload["current_period_end"] == real_period_end.isoformat()
