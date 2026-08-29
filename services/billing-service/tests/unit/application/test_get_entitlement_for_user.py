import uuid
from datetime import datetime, timedelta, timezone

from application.queries.get_entitlement_for_user import (
    GetEntitlementForUserHandler,
    GetEntitlementForUserQuery,
)
from domain.value_objects.subscription_status import SubscriptionStatus
from tests.fixtures.factories import FakeSubscriptionRepository, make_subscription

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


async def test_active_subscription_is_entitled():
    user_id = uuid.uuid4()
    sub = make_subscription(user_id=user_id, status=SubscriptionStatus.active())
    subs = FakeSubscriptionRepository(seed=[sub])
    handler = GetEntitlementForUserHandler(subs, now_fn=lambda: NOW)

    result = await handler.handle(GetEntitlementForUserQuery(user_id=user_id))
    assert result.entitled is True


async def test_cancel_at_period_end_past_period_end_not_entitled():
    user_id = uuid.uuid4()
    sub = make_subscription(
        user_id=user_id,
        status=SubscriptionStatus.active(),
        cancel_at_period_end=True,
        current_period_end=NOW - timedelta(days=1),
    )
    subs = FakeSubscriptionRepository(seed=[sub])
    handler = GetEntitlementForUserHandler(subs, now_fn=lambda: NOW)

    result = await handler.handle(GetEntitlementForUserQuery(user_id=user_id))
    assert result.entitled is False


async def test_cancel_at_period_end_before_period_end_still_entitled():
    user_id = uuid.uuid4()
    sub = make_subscription(
        user_id=user_id,
        status=SubscriptionStatus.active(),
        cancel_at_period_end=True,
        current_period_end=NOW + timedelta(days=5),
    )
    subs = FakeSubscriptionRepository(seed=[sub])
    handler = GetEntitlementForUserHandler(subs, now_fn=lambda: NOW)

    result = await handler.handle(GetEntitlementForUserQuery(user_id=user_id))
    assert result.entitled is True


async def test_no_subscription_record_not_entitled_no_error():
    subs = FakeSubscriptionRepository()
    handler = GetEntitlementForUserHandler(subs, now_fn=lambda: NOW)

    result = await handler.handle(GetEntitlementForUserQuery(user_id=uuid.uuid4()))
    assert result.entitled is False
