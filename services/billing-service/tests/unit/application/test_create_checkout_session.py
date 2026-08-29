import uuid

import pytest

from application.commands.create_checkout_session import (
    CreateCheckoutSessionCommand,
    CreateCheckoutSessionHandler,
)
from application.errors import SubscriptionAlreadyActiveError
from domain.value_objects.subscription_status import SubscriptionStatus
from tests.fixtures.factories import (
    FakePaymentProvider,
    FakeSubscriptionRepository,
    make_subscription,
)


async def test_creates_checkout_session_for_new_user():
    subs = FakeSubscriptionRepository()
    provider = FakePaymentProvider()
    handler = CreateCheckoutSessionHandler(subs, provider)
    user_id = uuid.uuid4()

    result = await handler.handle(
        CreateCheckoutSessionCommand(
            user_id=user_id,
            customer_email="user@example.com",
            success_url="https://app.nutriapp.example/success",
            cancel_url="https://app.nutriapp.example/cancel",
            idempotency_key="idem-1",
        )
    )

    assert result.url == provider.checkout_url
    assert len(provider.create_checkout_session_calls) == 1


async def test_rejects_when_already_active():
    user_id = uuid.uuid4()
    existing = make_subscription(user_id=user_id, status=SubscriptionStatus.active())
    subs = FakeSubscriptionRepository(seed=[existing])
    provider = FakePaymentProvider()
    handler = CreateCheckoutSessionHandler(subs, provider)

    with pytest.raises(SubscriptionAlreadyActiveError):
        await handler.handle(
            CreateCheckoutSessionCommand(
                user_id=user_id,
                customer_email="user@example.com",
                success_url="https://app.nutriapp.example/success",
                cancel_url="https://app.nutriapp.example/cancel",
                idempotency_key="idem-2",
            )
        )

    assert provider.create_checkout_session_calls == []
