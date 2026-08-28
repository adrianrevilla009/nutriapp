"""DeliveryStatus -- delivery-log status transitions (docs/notifications.md
section 4): sent -> delivered | bounced | failed are the only valid
forward transitions; going backward (e.g. delivered -> sent) is invalid.
"""

from __future__ import annotations

from enum import Enum


class DeliveryStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class InvalidDeliveryStatusTransitionError(ValueError):
    """Raised on an invalid delivery-status transition."""


_VALID_TRANSITIONS: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.SENT: frozenset(
        {DeliveryStatus.DELIVERED, DeliveryStatus.BOUNCED, DeliveryStatus.FAILED}
    ),
}


def transition(current: DeliveryStatus, target: DeliveryStatus) -> DeliveryStatus:
    allowed = _VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidDeliveryStatusTransitionError(
            f"{current.value} -> {target.value} is not allowed."
        )
    return target
