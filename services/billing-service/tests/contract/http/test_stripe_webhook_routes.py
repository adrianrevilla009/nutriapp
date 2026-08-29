"""POST /internal/v1/billing/webhooks/stripe -- test-plan section 3, plus
route-level dispatch coverage for all five handled event types
(qa-agent finding: invoice_paid/subscription_deleted/invoice_payment_failed
fixtures existed but were never posted through the real route before)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from domain.value_objects.stripe_ids import StripeSubscriptionId
from infrastructure.persistence.postgres_entitlement_revocation_schedule_repository import (
    PostgresEntitlementRevocationScheduleRepository,
)
from infrastructure.persistence.postgres_subscription_repository import (
    PostgresSubscriptionRepository,
)
from tests.fixtures.stripe_webhooks.signing import sign_payload

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "stripe_webhooks")

TEST_SUBSCRIPTION_ID = StripeSubscriptionId("sub_QzTestSubscription01")
# Matches invoice_paid.json / subscription_deleted.json / subscription_created.json's
# shared current_period_end/period_end fixture value (a real ~31-day calendar
# month from checkout_session_completed.json's `created` timestamp, not a
# flat 30-day guess).
REAL_PERIOD_END = datetime.fromtimestamp(1719878400, tz=timezone.utc)


def _load_fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES_DIR, name), "rb") as f:
        return f.read()


def _webhook_headers(signature_header: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    headers["Stripe-Signature"] = signature_header
    headers["Content-Type"] = "application/json"
    return headers


async def _post_webhook(client: httpx.AsyncClient, fixture_name: str) -> httpx.Response:
    payload = _load_fixture(fixture_name)
    header = sign_payload(payload)
    return await client.post(
        "/internal/v1/billing/webhooks/stripe", content=payload, headers=_webhook_headers(header)
    )


async def test_valid_signature_recognized_event_returns_200(app_client, db_engine):
    client, _container = app_client
    payload = _load_fixture("checkout_session_completed.json")
    header = sign_payload(payload)

    response = await client.post(
        "/internal/v1/billing/webhooks/stripe", content=payload, headers=_webhook_headers(header)
    )
    assert response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        saved = await repo.get_by_stripe_subscription_id(
            StripeSubscriptionId("sub_QzTestSubscription01")
        )
    assert saved is not None
    assert saved.status.value == "active"


async def test_invalid_signature_rejected_no_side_effect(app_client, db_engine):
    client, _container = app_client
    payload = _load_fixture("checkout_session_completed.json")

    response = await client.post(
        "/internal/v1/billing/webhooks/stripe",
        content=payload,
        headers=_webhook_headers("t=1,v1=invalidsignature"),
    )
    assert response.status_code == 401

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        saved = await repo.get_by_stripe_subscription_id(
            StripeSubscriptionId("sub_QzTestSubscription01")
        )
    assert saved is None


async def test_missing_signature_rejected(app_client):
    client, _container = app_client
    payload = _load_fixture("checkout_session_completed.json")

    response = await client.post(
        "/internal/v1/billing/webhooks/stripe", content=payload, headers=_webhook_headers("")
    )
    assert response.status_code == 401


async def test_replayed_event_id_is_a_no_op_not_an_error(app_client, db_engine):
    client, _container = app_client
    payload = _load_fixture("checkout_session_completed.json")
    header = sign_payload(payload)

    first = await client.post(
        "/internal/v1/billing/webhooks/stripe", content=payload, headers=_webhook_headers(header)
    )
    assert first.status_code == 200

    second = await client.post(
        "/internal/v1/billing/webhooks/stripe", content=payload, headers=_webhook_headers(header)
    )
    assert second.status_code == 200


async def test_unhandled_event_type_returns_200_no_op(app_client):
    client, _container = app_client
    payload = _load_fixture("unhandled_event_type.json")
    header = sign_payload(payload)

    response = await client.post(
        "/internal/v1/billing/webhooks/stripe", content=payload, headers=_webhook_headers(header)
    )
    assert response.status_code == 200
    assert response.json()["event_type"] == "customer.updated"


async def test_subscription_deleted_route_defers_revocation(app_client, db_engine):
    """qa-agent gap: subscription_deleted.json existed but was never
    posted through the real route -- prioritized first per the deferred-
    revocation safety property this backs."""
    client, _container = app_client
    checkout_response = await _post_webhook(client, "checkout_session_completed.json")
    assert checkout_response.status_code == 200

    response = await _post_webhook(client, "subscription_deleted.json")
    assert response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        subs_repo = PostgresSubscriptionRepository(session)
        saved = await subs_repo.get_by_stripe_subscription_id(TEST_SUBSCRIPTION_ID)
        assert saved is not None
        assert saved.cancel_at_period_end is True
        # Cancellation never immediately revokes entitlement.
        assert saved.status.value == "active"

        revocation_repo = PostgresEntitlementRevocationScheduleRepository(session)
        due_far_future = await revocation_repo.list_due(saved.current_period_end)
        assert any(entry.user_id == saved.user_id for entry in due_far_future)


async def test_invoice_paid_route_extends_period(app_client, db_engine):
    """qa-agent gap: invoice_paid.json existed but was never posted
    through the real route."""
    client, _container = app_client
    checkout_response = await _post_webhook(client, "checkout_session_completed.json")
    assert checkout_response.status_code == 200

    response = await _post_webhook(client, "invoice_paid.json")
    assert response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        saved = await repo.get_by_stripe_subscription_id(TEST_SUBSCRIPTION_ID)
    assert saved is not None
    assert saved.current_period_end == REAL_PERIOD_END
    assert saved.status.value == "active"


async def test_invoice_payment_failed_route_marks_past_due(app_client, db_engine):
    """qa-agent gap: invoice_payment_failed.json existed but was never
    posted through the real route."""
    client, _container = app_client
    checkout_response = await _post_webhook(client, "checkout_session_completed.json")
    assert checkout_response.status_code == 200

    response = await _post_webhook(client, "invoice_payment_failed.json")
    assert response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        saved = await repo.get_by_stripe_subscription_id(TEST_SUBSCRIPTION_ID)
    assert saved is not None
    assert saved.status.value == "past_due"
    # Payment failure alone never revokes entitlement (Stripe's dunning
    # window governs whether a later customer.subscription.deleted follows).
    assert saved.is_entitled(datetime.now(timezone.utc)) is True


async def test_subscription_created_arriving_first_persists_real_period_end(app_client, db_engine):
    """The ordering-safety fix's primary case: customer.subscription.created
    (real current_period_end) arrives BEFORE checkout.session.completed --
    the row it creates must survive checkout.session.completed's arrival
    unchanged, never overwritten by the 30-day estimate. Directly
    supersedes qa-agent's original "no test pins the hardcoded value"
    finding."""
    client, _container = app_client
    created_response = await _post_webhook(client, "subscription_created.json")
    assert created_response.status_code == 200

    checkout_response = await _post_webhook(client, "checkout_session_completed.json")
    assert checkout_response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        saved = await repo.get_by_stripe_subscription_id(TEST_SUBSCRIPTION_ID)
    assert saved is not None
    assert saved.current_period_end == REAL_PERIOD_END
    assert saved.status.value == "active"


async def test_subscription_created_arriving_second_corrects_real_period_end(app_client, db_engine):
    """The other arrival order: checkout.session.completed (estimate)
    arrives first, customer.subscription.created (real value) second --
    the estimate must be corrected to the real value, not left standing."""
    client, _container = app_client
    checkout_response = await _post_webhook(client, "checkout_session_completed.json")
    assert checkout_response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        after_checkout = await repo.get_by_stripe_subscription_id(TEST_SUBSCRIPTION_ID)
    assert after_checkout is not None
    assert after_checkout.current_period_end != REAL_PERIOD_END

    created_response = await _post_webhook(client, "subscription_created.json")
    assert created_response.status_code == 200

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresSubscriptionRepository(session)
        after_created = await repo.get_by_stripe_subscription_id(TEST_SUBSCRIPTION_ID)
    assert after_created is not None
    assert after_created.current_period_end == REAL_PERIOD_END
