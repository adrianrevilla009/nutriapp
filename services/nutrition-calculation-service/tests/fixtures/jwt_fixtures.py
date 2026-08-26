"""Test-only helpers for building a signed RS256 JWT (mirrors
identity-service's own JwtTokenIssuer output shape: `user_id` + `roles`
claims, `kid` header) and wiring a `JwtVerifier`
(shared_contracts.auth.jwt_verifier) against it without a real JWKS HTTP
server -- shared by every contract/integration test that needs an
authenticated request. Copied verbatim from services/diary-service's own
identical fixture (each service's test suite is independent; there is no
shared-contracts test-helper package)."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from shared_contracts.auth.jwt_verifier import JwtVerifier

TEST_ISSUER = "identity-service"
TEST_KID = "test-key-1"


def generate_test_rsa_key_pair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64url_uint(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def build_jwks_document(private_key, kid: str = TEST_KID) -> dict:
    numbers = private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


def build_signed_token(
    private_key,
    user_id: uuid.UUID,
    kid: str = TEST_KID,
    roles: tuple[str, ...] = ("USER",),
    ttl: timedelta = timedelta(minutes=15),
    issuer: str = TEST_ISSUER,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user_id),
        "roles": list(roles),
        "iat": now,
        "exp": now + ttl,
        "iss": issuer,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


class _FakeJwksResponse:
    def __init__(self, json_body: dict) -> None:
        self._json_body = json_body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._json_body


class FakeJwksHttpClient:
    """Stand-in for httpx.Client -- avoids a real JWKS HTTP server in
    tests, mirroring packages/shared-contracts/tests/test_jwt_verifier.py's
    own fake."""

    def __init__(self, jwks_document: dict) -> None:
        self._jwks_document = jwks_document
        self.call_count = 0

    def get(self, url, *args, **kwargs):
        self.call_count += 1
        return _FakeJwksResponse(self._jwks_document)


def build_test_jwt_verifier(private_key, issuer: str = TEST_ISSUER) -> JwtVerifier:
    """A JwtVerifier wired against a fake JWKS HTTP client serving the
    given keypair's public key -- no real network call."""
    return JwtVerifier(
        jwks_url="http://identity-service.test/.well-known/jwks.json",
        issuer=issuer,
        http_client=FakeJwksHttpClient(build_jwks_document(private_key)),
    )
