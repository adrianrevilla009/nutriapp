"""PostgresSubscriptionRepository -- implements SubscriptionRepositoryPort."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.subscription import Subscription
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId
from domain.value_objects.subscription_status import SubscriptionStatus
from infrastructure.persistence.models import SubscriptionModel


def _to_domain(row: SubscriptionModel) -> Subscription:
    return Subscription(
        subscription_id=row.subscription_id,
        user_id=row.user_id,
        stripe_customer_id=StripeCustomerId(row.stripe_customer_id),
        stripe_subscription_id=StripeSubscriptionId(row.stripe_subscription_id),
        status=SubscriptionStatus(row.status),
        current_period_end=row.current_period_end,
        cancel_at_period_end=row.cancel_at_period_end,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresSubscriptionRepository:
    """Implements domain.ports.subscription_repository_port.SubscriptionRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> Subscription | None:
        stmt = select(SubscriptionModel).where(SubscriptionModel.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def get_by_stripe_subscription_id(
        self, stripe_subscription_id: StripeSubscriptionId
    ) -> Subscription | None:
        stmt = select(SubscriptionModel).where(
            SubscriptionModel.stripe_subscription_id == str(stripe_subscription_id)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def save(self, subscription: Subscription) -> None:
        row = await self._session.get(SubscriptionModel, subscription.subscription_id)
        if row is None:
            row = SubscriptionModel(subscription_id=subscription.subscription_id)
            self._session.add(row)
        row.user_id = subscription.user_id
        row.stripe_customer_id = str(subscription.stripe_customer_id)
        row.stripe_subscription_id = str(subscription.stripe_subscription_id)
        row.status = subscription.status.value
        row.current_period_end = subscription.current_period_end
        row.cancel_at_period_end = subscription.cancel_at_period_end
        row.created_at = subscription.created_at
        row.updated_at = subscription.updated_at
        await self._session.flush()
