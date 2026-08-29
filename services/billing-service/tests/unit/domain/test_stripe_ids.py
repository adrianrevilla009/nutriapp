import pytest

from domain.value_objects.stripe_ids import (
    InvalidStripeIdError,
    StripeCustomerId,
    StripeSubscriptionId,
)


def test_valid_stripe_customer_id():
    assert str(StripeCustomerId("cus_ABC123")) == "cus_ABC123"


def test_valid_stripe_subscription_id():
    assert str(StripeSubscriptionId("sub_ABC123")) == "sub_ABC123"


@pytest.mark.parametrize("value", ["", "sub_ABC123", "cus_", "notaprefix"])
def test_invalid_customer_id(value):
    with pytest.raises(InvalidStripeIdError):
        StripeCustomerId(value)


@pytest.mark.parametrize("value", ["", "cus_ABC123", "sub_", "notaprefix"])
def test_invalid_subscription_id(value):
    with pytest.raises(InvalidStripeIdError):
        StripeSubscriptionId(value)
