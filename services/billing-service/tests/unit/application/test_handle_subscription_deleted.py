from datetime import datetime, timezone

from application.commands.handle_subscription_deleted import (
    HandleSubscriptionDeletedCommand,
    HandleSubscriptionDeletedHandler,
)
from domain.value_objects.stripe_ids import StripeSubscriptionId
from tests.fixtures.factories import (
    FakeEntitlementRevocationScheduleRepository,
    FakeOutboxRepository,
    FakeProcessedWebhookEventsRepository,
    FakeSubscriptionRepository,
    make_subscription,
)

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_cancellation_publishes_cancelled_and_defers_revocation():
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_abc"))
    subs = FakeSubscriptionRepository(seed=[sub])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    revocation_schedule = FakeEntitlementRevocationScheduleRepository()
    handler = HandleSubscriptionDeletedHandler(subs, processed, outbox, revocation_schedule)

    await handler.handle(
        HandleSubscriptionDeletedCommand(
            stripe_event_id="evt_4",
            stripe_subscription_id=StripeSubscriptionId("sub_abc"),
            correlation_id="corr-4",
            now=NOW,
        )
    )

    event_types = [e.event_type for e in outbox.enqueued]
    assert event_types == ["SubscriptionCancelled"]
    assert "EntitlementRevoked" not in event_types

    saved = await subs.get_by_stripe_subscription_id(StripeSubscriptionId("sub_abc"))
    assert saved.cancel_at_period_end is True
    assert saved.status.value == "active"

    scheduled = revocation_schedule.by_user[sub.user_id]
    assert scheduled.processed is False
    assert scheduled.revoke_at == sub.current_period_end


async def test_replayed_delete_event_is_idempotent():
    sub = make_subscription(stripe_subscription_id=StripeSubscriptionId("sub_abc"))
    subs = FakeSubscriptionRepository(seed=[sub])
    processed = FakeProcessedWebhookEventsRepository()
    outbox = FakeOutboxRepository()
    revocation_schedule = FakeEntitlementRevocationScheduleRepository()
    handler = HandleSubscriptionDeletedHandler(subs, processed, outbox, revocation_schedule)

    command = HandleSubscriptionDeletedCommand(
        stripe_event_id="evt_5",
        stripe_subscription_id=StripeSubscriptionId("sub_abc"),
        correlation_id="corr-5",
        now=NOW,
    )
    await handler.handle(command)
    await handler.handle(command)

    assert len(outbox.enqueued) == 1
    assert revocation_schedule.upsert_calls == 1
