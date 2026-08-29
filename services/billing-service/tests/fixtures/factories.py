"""Shared test fixtures/factories -- Subscription builders and in-memory
fake port implementations (hexagonal-architecture SKILL.md: "Application:
unit tests using fake/in-memory implementations of ports, not the real
adapters")."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from domain.entities.subscription import Subscription
from domain.events.base import DomainEvent
from domain.ports.entitlement_revocation_schedule_repository_port import RevocationScheduleEntry
from domain.value_objects.stripe_ids import StripeCustomerId, StripeSubscriptionId
from domain.value_objects.subscription_status import SubscriptionStatus

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def make_subscription(**overrides) -> Subscription:
    defaults = dict(
        subscription_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        stripe_customer_id=StripeCustomerId("cus_test123"),
        stripe_subscription_id=StripeSubscriptionId("sub_test123"),
        status=SubscriptionStatus.active(),
        current_period_end=NOW + timedelta(days=30),
        cancel_at_period_end=False,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Subscription(**defaults)


class FakeSubscriptionRepository:
    def __init__(self, seed: list[Subscription] | None = None) -> None:
        self.by_id: dict[uuid.UUID, Subscription] = {s.subscription_id: s for s in (seed or [])}
        self.save_calls = 0

    async def get_by_user_id(self, user_id: uuid.UUID) -> Subscription | None:
        for sub in self.by_id.values():
            if sub.user_id == user_id:
                return sub
        return None

    async def get_by_stripe_subscription_id(self, stripe_subscription_id):
        for sub in self.by_id.values():
            if sub.stripe_subscription_id == stripe_subscription_id:
                return sub
        return None

    async def save(self, subscription: Subscription) -> None:
        self.save_calls += 1
        self.by_id[subscription.subscription_id] = subscription


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.enqueued: list[DomainEvent] = []
        self.published_ids: set[uuid.UUID] = set()

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return [e for e in self.enqueued if e.event_id not in self.published_ids][:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        self.published_ids.add(event_id)


class FakeProcessedWebhookEventsRepository:
    def __init__(self) -> None:
        self.processed: set[str] = set()

    async def is_processed(self, stripe_event_id: str) -> bool:
        return stripe_event_id in self.processed

    async def mark_processed(self, stripe_event_id: str) -> None:
        self.processed.add(stripe_event_id)


class FakeEntitlementRevocationScheduleRepository:
    def __init__(self, seed: list[RevocationScheduleEntry] | None = None) -> None:
        self.by_user: dict[uuid.UUID, RevocationScheduleEntry] = {
            e.user_id: e for e in (seed or [])
        }
        self.upsert_calls = 0

    async def upsert_pending(self, user_id: uuid.UUID, revoke_at: datetime) -> None:
        self.upsert_calls += 1
        existing = self.by_user.get(user_id)
        if existing is not None and existing.processed:
            return
        self.by_user[user_id] = RevocationScheduleEntry(
            user_id=user_id, revoke_at=revoke_at, processed=False
        )

    async def list_due(self, now: datetime, limit: int = 100) -> list[RevocationScheduleEntry]:
        due = [e for e in self.by_user.values() if not e.processed and e.revoke_at <= now]
        return due[:limit]

    async def mark_processed(self, user_id: uuid.UUID) -> None:
        existing = self.by_user[user_id]
        self.by_user[user_id] = RevocationScheduleEntry(
            user_id=existing.user_id, revoke_at=existing.revoke_at, processed=True
        )


class FakePaymentProvider:
    def __init__(self, checkout_url: str = "https://checkout.stripe.com/c/pay/test") -> None:
        self.checkout_url = checkout_url
        self.create_checkout_session_calls: list[dict] = []

    async def create_checkout_session(
        self, *, user_id, customer_email, success_url, cancel_url, idempotency_key
    ):
        from domain.ports.payment_provider_port import CheckoutSession

        self.create_checkout_session_calls.append(
            dict(
                user_id=user_id,
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                idempotency_key=idempotency_key,
            )
        )
        return CheckoutSession(stripe_session_id="cs_test_123", url=self.checkout_url)

    def verify_webhook_signature(self, *, payload: bytes, signature_header: str):
        raise NotImplementedError("Not used by application-layer unit tests")
