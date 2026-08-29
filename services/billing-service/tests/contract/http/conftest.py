"""Contract-test app: real Postgres (testcontainers) behind the routes,
a fake PaymentProviderPort swapped in via dependency overrides so these
tests exercise real HTTP routing/serialization against a real DB without
needing a live Stripe account or RabbitMQ (testing-strategy SKILL.md).
Authenticated requests use a real signed RS256 JWT verified by a real
JwtVerifier wired against a fake (in-memory) JWKS HTTP client -- no real
identity-service or network call, but exercising the actual verification
code path (mirrors profile-service's identical precedent)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest
from fastapi import FastAPI
from shared_contracts.testing.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from domain.ports.payment_provider_port import WebhookSignatureVerificationError
from infrastructure.external.stripe_payment_adapter import _parse_signature_header
from infrastructure.http import dependencies as deps
from infrastructure.http.health import router as health_router
from infrastructure.http.routes.checkout_routes import router as checkout_router
from infrastructure.http.routes.internal_entitlement_routes import (
    router as internal_entitlement_router,
)
from infrastructure.http.routes.stripe_webhook_routes import router as stripe_webhook_router
from tests.fixtures.factories import FakePaymentProvider
from tests.fixtures.stripe_webhooks.signing import TEST_WEBHOOK_SECRET

_TEST_PRIVATE_KEY = generate_test_rsa_key_pair()
INTERNAL_ENTITLEMENT_CREDENTIAL = "test-internal-entitlement-credential"


class _FakeSettings:
    internal_entitlement_credential = INTERNAL_ENTITLEMENT_CREDENTIAL


class _StubStripeAdapter(FakePaymentProvider):
    """Extends the application-layer fake with a real, local
    verify_webhook_signature implementation (matching StripePaymentAdapter's
    documented HMAC scheme) so contract tests can exercise the webhook
    route's signature-verification branch without a live Stripe call."""

    def verify_webhook_signature(self, *, payload: bytes, signature_header: str):
        timestamp, signatures = _parse_signature_header(signature_header)
        if timestamp is None or not signatures:
            raise WebhookSignatureVerificationError("Missing or malformed Stripe-Signature header.")
        if abs(int(time.time()) - timestamp) > 300:
            raise WebhookSignatureVerificationError("Webhook timestamp outside tolerance.")
        signed_payload = f"{timestamp}.".encode("ascii") + payload
        expected = hmac.new(
            TEST_WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, sig) for sig in signatures):
            raise WebhookSignatureVerificationError("Signature verification failed.")
        return json.loads(payload)


class _FakeContainer:
    def __init__(self) -> None:
        self.payment_provider = _StubStripeAdapter()
        self.jwt_verifier = build_test_jwt_verifier(_TEST_PRIVATE_KEY)
        self.settings = _FakeSettings()


@pytest.fixture
async def app_client(db_engine: AsyncEngine):
    app = FastAPI()
    app.include_router(checkout_router)
    app.include_router(stripe_webhook_router)
    app.include_router(internal_entitlement_router)
    app.include_router(health_router)

    container = _FakeContainer()
    app.state.container = container

    async def override_get_session():
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    app.dependency_overrides[deps.get_container] = lambda: container

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, container


def auth_headers(user_id: uuid.UUID) -> dict:
    token = build_signed_token(_TEST_PRIVATE_KEY, user_id)
    headers: dict[str, str] = {}
    headers["Authorization"] = f"Bearer {token}"
    return headers
