"""DeliveryStatus transitions (test-plan section 1)."""

from __future__ import annotations

import pytest

from domain.value_objects.delivery_status import (
    DeliveryStatus,
    InvalidDeliveryStatusTransitionError,
    transition,
)


@pytest.mark.parametrize(
    "target", [DeliveryStatus.DELIVERED, DeliveryStatus.BOUNCED, DeliveryStatus.FAILED]
)
def test_sent_to_terminal_states_are_valid(target):
    assert transition(DeliveryStatus.SENT, target) == target


def test_delivered_to_sent_is_invalid():
    with pytest.raises(InvalidDeliveryStatusTransitionError):
        transition(DeliveryStatus.DELIVERED, DeliveryStatus.SENT)


def test_bounced_to_sent_is_invalid():
    with pytest.raises(InvalidDeliveryStatusTransitionError):
        transition(DeliveryStatus.BOUNCED, DeliveryStatus.SENT)
