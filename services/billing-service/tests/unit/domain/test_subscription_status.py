import pytest

from domain.value_objects.subscription_status import (
    InvalidSubscriptionStatusError,
    SubscriptionStatus,
)


@pytest.mark.parametrize("value", ["active", "past_due", "canceled"])
def test_accepts_valid_values(value):
    assert SubscriptionStatus(value).value == value


@pytest.mark.parametrize("value", ["", "ACTIVE", "trialing", "unpaid", "cancelled"])
def test_rejects_invalid_values(value):
    with pytest.raises(InvalidSubscriptionStatusError):
        SubscriptionStatus(value)


def test_factory_methods():
    assert SubscriptionStatus.active() == SubscriptionStatus("active")
    assert SubscriptionStatus.past_due() == SubscriptionStatus("past_due")
    assert SubscriptionStatus.canceled() == SubscriptionStatus("canceled")


def test_str():
    assert str(SubscriptionStatus.active()) == "active"
