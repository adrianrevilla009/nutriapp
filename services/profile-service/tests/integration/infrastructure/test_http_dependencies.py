"""infrastructure.http.dependencies.get_authenticated_user_id -- JWT
verification via a fake (in-memory) JWKS HTTP client, exercising the real
verification code path (shared_contracts.auth.jwt_verifier.JwtVerifier)
without a real identity-service or network call. No Postgres/RabbitMQ
needed -- this dependency is pure HTTP + crypto."""

from __future__ import annotations

import uuid
from datetime import timedelta

import httpx
import pytest
from fastapi import Depends, FastAPI
from shared_contracts.auth.jwt_verifier import JwksCircuitOpenError, JwtVerifier

from infrastructure.http.dependencies import get_authenticated_user_id
from tests.fixtures.jwt_fixtures import (
    FakeJwksHttpClient,
    build_jwks_document,
    build_signed_token,
    generate_test_rsa_key_pair,
)


class _FakeContainer:
    def __init__(self, jwt_verifier: JwtVerifier) -> None:
        self.jwt_verifier = jwt_verifier


def _build_app(jwt_verifier: JwtVerifier) -> FastAPI:
    app = FastAPI()
    app.state.container = _FakeContainer(jwt_verifier)

    @app.get("/whoami")
    async def whoami(user_id: uuid.UUID = Depends(get_authenticated_user_id)):
        return {"user_id": str(user_id)}

    return app


@pytest.fixture()
def keypair():
    private_key = generate_test_rsa_key_pair()
    return private_key, "test-key-1"


@pytest.fixture()
async def client(keypair):
    private_key, kid = keypair
    verifier = JwtVerifier(
        jwks_url="http://identity-service.test/.well-known/jwks.json",
        issuer="identity-service",
        http_client=FakeJwksHttpClient(build_jwks_document(private_key, kid)),
    )
    app = _build_app(verifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def test_valid_bearer_token_is_accepted_and_user_id_extracted(client, keypair):
    private_key, kid = keypair
    user_id = uuid.uuid4()
    token = build_signed_token(private_key, user_id, kid=kid)

    response = await client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == str(user_id)


async def test_missing_authorization_header_returns_401(client):
    response = await client.get("/whoami")
    assert response.status_code == 401


async def test_non_bearer_authorization_header_returns_401(client):
    response = await client.get("/whoami", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401


async def test_empty_bearer_token_returns_401(client):
    response = await client.get("/whoami", headers={"Authorization": "Bearer "})
    assert response.status_code == 401


async def test_tampered_token_returns_401(client, keypair):
    private_key, kid = keypair
    token = build_signed_token(private_key, uuid.uuid4(), kid=kid)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}extra.{signature}"

    response = await client.get("/whoami", headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401


async def test_expired_token_returns_401(client, keypair):
    private_key, kid = keypair
    token = build_signed_token(private_key, uuid.uuid4(), kid=kid, ttl=timedelta(seconds=-1))

    response = await client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


async def test_token_signed_by_unknown_key_returns_401(client):
    wrong_signer_key = generate_test_rsa_key_pair()
    token = build_signed_token(wrong_signer_key, uuid.uuid4(), kid="test-key-1")

    response = await client.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


async def test_jwks_fetch_failure_fails_closed_with_401(keypair):
    private_key, kid = keypair
    token = build_signed_token(private_key, uuid.uuid4(), kid=kid)

    class _AlwaysFailingHttpClient:
        def get(self, url, *args, **kwargs):
            raise RuntimeError("Simulated JWKS fetch failure.")

    verifier = JwtVerifier(
        jwks_url="http://identity-service.test/.well-known/jwks.json",
        issuer="identity-service",
        http_client=_AlwaysFailingHttpClient(),
        overall_timeout_seconds=2.0,
    )
    app = _build_app(verifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        response = await c.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


async def test_jwks_circuit_open_fails_closed_with_401(keypair):
    """Once the JWKS-fetch circuit is open, a request must still fail
    closed (401), not raise an unhandled JwksCircuitOpenError."""
    private_key, kid = keypair
    token = build_signed_token(private_key, uuid.uuid4(), kid=kid)

    class _AlwaysFailingHttpClient:
        def get(self, url, *args, **kwargs):
            raise RuntimeError("Simulated JWKS fetch failure.")

    verifier = JwtVerifier(
        jwks_url="http://identity-service.test/.well-known/jwks.json",
        issuer="identity-service",
        http_client=_AlwaysFailingHttpClient(),
        fail_max=1,
        reset_timeout_seconds=30,
        overall_timeout_seconds=2.0,
    )
    app = _build_app(verifier)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        first = await c.get("/whoami", headers={"Authorization": f"Bearer {token}"})
        second = await c.get("/whoami", headers={"Authorization": f"Bearer {token}"})

    assert first.status_code == 401
    assert second.status_code == 401
    # Sanity check on the fixture itself: the breaker really did open.
    with pytest.raises(JwksCircuitOpenError):
        await verifier.verify(token)
