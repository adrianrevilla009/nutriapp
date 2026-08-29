"""SubscriptionRepositoryPort -- the write-model persistence boundary for
the `Subscription` aggregate (event-driven CRUD, ADR-0002)."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.entities.subscription import Subscription
from domain.value_objects.stripe_ids import StripeSubscriptionId


class SubscriptionRepositoryPort(Protocol):
    async def get_by_user_id(self, user_id: uuid.UUID) -> Subscription | None: ...

    async def get_by_stripe_subscription_id(
        self, stripe_subscription_id: StripeSubscriptionId
    ) -> Subscription | None: ...

    async def save(self, subscription: Subscription) -> None: ...
