"""GetEntitlementForUserHandler -- backs `GET /internal/v1/billing/entitlements/{user_id}`,
the synchronous fallback compensation path for `ProUpgradeEntitlementPropagation`
(docs/sagas-and-distributed-transactions.md). A user with no subscription
record at all is "not entitled", never an error -- a lagging/absent
consumer must fail safe (billing-agent.md, saga-conventions SKILL.md)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.dto.entitlement_result import EntitlementResult
from domain.ports.subscription_repository_port import SubscriptionRepositoryPort


@dataclass(frozen=True, slots=True)
class GetEntitlementForUserQuery:
    user_id: uuid.UUID


class GetEntitlementForUserHandler:
    def __init__(
        self,
        subscriptions: SubscriptionRepositoryPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._subscriptions = subscriptions
        self._now_fn = now_fn

    async def handle(self, query: GetEntitlementForUserQuery) -> EntitlementResult:
        subscription = await self._subscriptions.get_by_user_id(query.user_id)
        if subscription is None:
            return EntitlementResult(entitled=False)
        return EntitlementResult(entitled=subscription.is_entitled(self._now_fn()))
