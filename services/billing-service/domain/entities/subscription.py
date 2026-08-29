"""Subscription — the write-model aggregate for this service's one
aggregate root (event-driven CRUD, ADR-0002: conventional persistence,
not event-sourced). One row per user's subscription, updated in place as
Stripe webhooks arrive.

Immutable (frozen dataclass), mirroring every other service's domain
entity convention (e.g. catalog-service's `Product`) — every transition
method returns a NEW `Subscription` instance rather than mutating in
place; the application layer is responsible for persisting the returned
instance.

Resolved ambiguity (flagged in the final implementation report per this
session's instructions): the test plan describes `cancel()` (does not
change `status` away from `active`) and, separately, "`mark_past_due()`/
`mark_canceled()` (from webhook-driven state transitions) ... an already-
`canceled` subscription receiving another `customer.subscription.deleted`
is idempotent". Taken together with `GetEntitlementForUserHandler`'s own
cases (a "canceled" subscription is described as entitled/not-entitled
purely based on `current_period_end`, never on `status` alone), the only
internally-consistent reading is: `status` never actually transitions to
`CANCELED` in this MVP's scope -- entitlement is derived from `status` +
`cancel_at_period_end` + `current_period_end` (`is_entitled` below), and
the test plan's prose "a canceled subscription" describes the business
scenario (the user requested cancellation, i.e. `cancel_at_period_end`
is set), not a literal `status == CANCELED` check. `cancel()` is
idempotent by construction (setting `cancel_at_period_end = True` a
second time changes nothing and raises nothing) -- this is what the
"mark_canceled()" bullet's idempotency case exercises; no second,
separately-named method exists. `SubscriptionStatus.canceled()` remains a
valid, VO-accepted value (used defensively by `is_entitled` below) that
no currently-implemented transition produces -- a full finalization step
(flipping `status` to `CANCELED` once `ProcessDueRevocationsHandler`
actually revokes entitlement at period end) is a reasonable future
increment, out of this plan's explicit scope (§1's "Explicitly out of
scope": no proration/reactivation flow beyond a single Pro tier).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime

from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId
from domain.value_objects.subscription_status import SubscriptionStatus


@dataclass(frozen=True, slots=True)
class Subscription:
    subscription_id: uuid.UUID
    user_id: uuid.UUID
    stripe_customer_id: StripeCustomerId
    stripe_subscription_id: StripeSubscriptionId
    status: SubscriptionStatus
    current_period_end: datetime
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def start(
        cls,
        *,
        subscription_id: uuid.UUID,
        user_id: uuid.UUID,
        stripe_customer_id: StripeCustomerId,
        stripe_subscription_id: StripeSubscriptionId,
        current_period_end: datetime,
        now: datetime,
    ) -> Subscription:
        """`checkout.session.completed` — a brand new subscription starts
        `active`, never cancel-at-period-end."""
        return cls(
            subscription_id=subscription_id,
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=SubscriptionStatus.active(),
            current_period_end=current_period_end,
            cancel_at_period_end=False,
            created_at=now,
            updated_at=now,
        )

    def renew(self, *, current_period_end: datetime, now: datetime) -> Subscription:
        """`invoice.paid` — extends the paid period and clears any prior
        `past_due` state (Stripe's own dunning recovery: a successful
        invoice payment means the subscription is current again)."""
        return replace(
            self,
            status=SubscriptionStatus.active(),
            current_period_end=current_period_end,
            cancel_at_period_end=False,
            updated_at=now,
        )

    def cancel(self, now: datetime) -> Subscription:
        """`customer.subscription.deleted` — records the cancellation and
        defers revocation to `current_period_end` (billing-agent.md: never
        revoke access the moment a user clicks cancel). Idempotent:
        replaying the same webhook event twice yields the same resulting
        state, never an exception."""
        return replace(self, cancel_at_period_end=True, updated_at=now)

    def mark_past_due(self, now: datetime) -> Subscription:
        """`invoice.payment_failed` — entitlement is NOT revoked by this
        transition alone; Stripe's own dunning/retry window determines if/
        when the subscription is ultimately canceled (that is `cancel()`'s
        job, triggered by a later `customer.subscription.deleted`)."""
        return replace(self, status=SubscriptionStatus.past_due(), updated_at=now)

    def correct_period_end(self, current_period_end: datetime, now: datetime) -> Subscription:
        """`customer.subscription.created` — Stripe's real Subscription
        object is the authoritative source for `current_period_end`
        (unlike `checkout.session.completed`'s payload, which never
        carries it — see `HandleCheckoutCompletedHandler`'s
        best-estimate fallback). Replaces ONLY `current_period_end`;
        never touches `status`/`cancel_at_period_end` — this method exists
        purely to correct a previously-guessed value, not to re-run any
        other transition. Safe to call whenever this event arrives,
        before or after `checkout.session.completed` (Stripe does not
        strictly order the two)."""
        return replace(self, current_period_end=current_period_end, updated_at=now)

    def is_entitled(self, now: datetime) -> bool:
        """Single source of truth for "does this subscription currently
        grant Pro access" -- used by both `GetEntitlementForUserHandler`
        (the internal sync fallback endpoint) and anywhere else this
        service itself needs the answer."""
        if self.status == SubscriptionStatus.canceled():
            return False
        if self.cancel_at_period_end:
            return now < self.current_period_end
        return self.status in (SubscriptionStatus.active(), SubscriptionStatus.past_due())
