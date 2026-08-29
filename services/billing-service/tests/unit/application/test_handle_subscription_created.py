"""HandleSubscriptionCreatedHandler -- the ordering-safety fix
(reviewer-agent finding). Pins the corrected behavior superseding the old
hardcoded PRO_TIER_BILLING_PERIOD_DAYS=30 guess: the real
customer.subscription.created payload's current_period_end is what ends
up persisted, in either arrival order."""

import uuid
from datetime import datetime, timedelta, timezone

from application.commands.handle_subscription_created import (
    HandleSubscriptionCreatedCommand,
    HandleSubscriptionCreatedHandler,
)
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId
from domain.value_objects.subscription_status import SubscriptionStatus
from tests.fixtures.factories import (
    FakeProcessedWebhookEventsRepository,
    FakeSubscriptionRepository,
    make_subscription,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _command(event_id="evt_sub_created_1", user_id=None):
    return HandleSubscriptionCreatedCommand(
        stripe_event_id=event_id,
        user_id=user_id or uuid.uuid4(),
        stripe_customer_id=StripeCustomerId("cus_abc"),
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        current_period_end=NOW + timedelta(days=31),  # a real calendar month, not a 30-day guess
        now=NOW,
    )


async def test_creates_row_with_real_period_end_when_arriving_before_checkout_completed():
    """subscription.created arrives FIRST (no existing row) -- creates the
    subscription using its own real current_period_end and the user_id
    from its metadata."""
    subs = FakeSubscriptionRepository()
    processed = FakeProcessedWebhookEventsRepository()
    handler = HandleSubscriptionCreatedHandler(subs, processed)

    user_id = uuid.uuid4()
    command = _command(user_id=user_id)
    await handler.handle(command)

    saved = await subs.get_by_user_id(user_id)
    assert saved is not None
    assert saved.current_period_end == command.current_period_end
    assert saved.status == SubscriptionStatus.active()
    assert saved.cancel_at_period_end is False


async def test_corrects_existing_row_real_period_end_when_arriving_after_checkout_completed():
    """subscription.created arrives SECOND (checkout.session.completed
    already created the row with its best-effort estimate) -- corrects
    ONLY current_period_end to the real value, leaves every other field
    untouched."""
    user_id = uuid.uuid4()
    estimated_period_end = NOW + timedelta(days=30)
    existing = make_subscription(
        user_id=user_id,
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        current_period_end=estimated_period_end,
        status=SubscriptionStatus.active(),
        cancel_at_period_end=False,
    )
    subs = FakeSubscriptionRepository(seed=[existing])
    processed = FakeProcessedWebhookEventsRepository()
    handler = HandleSubscriptionCreatedHandler(subs, processed)

    command = _command(user_id=user_id)
    await handler.handle(command)

    saved = await subs.get_by_user_id(user_id)
    assert saved.current_period_end == command.current_period_end
    assert saved.current_period_end != estimated_period_end
    assert saved.status == SubscriptionStatus.active()
    assert saved.cancel_at_period_end is False


async def test_replayed_event_id_is_a_no_op():
    subs = FakeSubscriptionRepository()
    processed = FakeProcessedWebhookEventsRepository()
    handler = HandleSubscriptionCreatedHandler(subs, processed)

    user_id = uuid.uuid4()
    command = _command(event_id="evt_replay", user_id=user_id)
    await handler.handle(command)
    first_save_count = subs.save_calls
    await handler.handle(command)

    assert subs.save_calls == first_save_count
