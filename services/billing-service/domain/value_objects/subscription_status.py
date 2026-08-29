"""SubscriptionStatus value object — the three states a `Subscription`'s
own status field can hold.

Deliberately NOT a full mirror of every Stripe subscription status
(`trialing`, `incomplete`, `unpaid`, ...) — trial periods and incomplete/
unpaid handling are explicitly out of scope for this plan (implementation
plan §1's "Explicitly out of scope"). `active`/`past_due`/`canceled` are
the only three this service's webhook handlers ever produce.

Entitlement is derived from `status` + `Subscription.cancel_at_period_end`
+ `current_period_end` (see `domain/entities/subscription.py`'s
`is_entitled`), not from `status` alone — `cancel()` deliberately does
NOT transition `status` to `CANCELED` (billing-agent.md's "cancellation
retains access through the paid period's end" rule); see that module's
docstring for the full resolved-ambiguity note on why `CANCELED` is a
valid, VO-accepted value that no currently-implemented flow actually
produces yet.
"""

from __future__ import annotations

from dataclasses import dataclass

_VALID_VALUES = frozenset({"active", "past_due", "canceled"})


class InvalidSubscriptionStatusError(ValueError):
    """Raised for any status string other than active/past_due/canceled."""


@dataclass(frozen=True, slots=True)
class SubscriptionStatus:
    value: str

    def __post_init__(self) -> None:
        if self.value not in _VALID_VALUES:
            raise InvalidSubscriptionStatusError(
                f"Unrecognized subscription status: {self.value!r} (must be one of {sorted(_VALID_VALUES)})"
            )

    def __str__(self) -> str:
        return self.value

    @classmethod
    def active(cls) -> SubscriptionStatus:
        return cls("active")

    @classmethod
    def past_due(cls) -> SubscriptionStatus:
        return cls("past_due")

    @classmethod
    def canceled(cls) -> SubscriptionStatus:
        return cls("canceled")
