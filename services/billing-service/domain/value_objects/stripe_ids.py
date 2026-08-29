"""StripeCustomerId / StripeSubscriptionId value objects — validate
Stripe's own documented ID prefix convention (`cus_...` / `sub_...`,
https://stripe.com/docs/api — every Stripe object id is prefixed by its
object type). This service never invents its own subscription/customer
identifiers; it only ever stores the ones Stripe issues, so validating the
prefix here is a cheap, real defense against accidentally persisting a
malformed/wrong-object-type id from a bug elsewhere (e.g. a swapped
argument order), not a full Stripe id-format re-implementation.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidStripeIdError(ValueError):
    """Raised for an empty id or one missing its expected object-type prefix."""


def _validate(value: str, prefix: str, label: str) -> None:
    if not value or not value.startswith(prefix) or value == prefix:
        raise InvalidStripeIdError(
            f"{label} must be a non-empty string starting with {prefix!r}: {value!r}"
        )


@dataclass(frozen=True, slots=True)
class StripeCustomerId:
    value: str

    def __post_init__(self) -> None:
        _validate(self.value, "cus_", "StripeCustomerId")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class StripeSubscriptionId:
    value: str

    def __post_init__(self) -> None:
        _validate(self.value, "sub_", "StripeSubscriptionId")

    def __str__(self) -> str:
        return self.value
