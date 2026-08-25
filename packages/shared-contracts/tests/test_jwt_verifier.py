"""shared_contracts.auth.jwt_verifier -- unit tests using a fake HTTP
client (no real JWKS server needed) and locally-generated RSA keypairs, so
timeouts/failures are simulated explicitly, not relied on from a real
slow dependency (mirrors identity-service's own JWT tests' style and
profile-service's KMS resilience test conventions)."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from shared_contracts.auth.jwt_verifier import (
    AuthenticatedPrincipal,
    JwksCircuitOpenError,
    JwksFetchError,
    JwtVerificationError,
    JwtVerifier,
)

ISSUER = "identity-service"


def _generate_rsa_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64url_uint(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _jwk_from_private_key(private_key, kid: str) -> dict:
    numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }


def _sign_token(
    private_key,
    kid: str,
    user_id: uuid.UUID,
    roles: tuple[str, ...] = ("USER",),
    ttl: timedelta = timedelta(minutes=15),
    issuer: str = ISSUER,
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


class _FakeResponse:
    def __init__(self, json_body: dict, status_code: int = 200) -> None:
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"Simulated HTTP {self.status_code}")

    def json(self) -> dict:
        return self._json_body


class _FakeHttpClient:
    """Stand-in for httpx.Client -- JwtVerifier only ever calls .get()."""

    def __init__(self, jwks_document: dict | None = None, mode: str = "normal") -> None:
        self.jwks_document = jwks_document or {"keys": []}
        self.mode = mode  # "normal" | "always_fail"
        self.call_count = 0

    def get(self, url, *args, **kwargs):
        self.call_count += 1
        if self.mode == "always_fail":
            raise RuntimeError("Simulated JWKS fetch failure.")
        return _FakeResponse(self.jwks_document)


@pytest.fixture()
def keypair():
    private_key = _generate_rsa_private_key()
    return private_key, "key-1"


@pytest.fixture()
def jwks_client(keypair):
    private_key, kid = keypair
    return _FakeHttpClient({"keys": [_jwk_from_private_key(private_key, kid)]})


def make_verifier(http_client, issuer: str | None = ISSUER, **kwargs) -> JwtVerifier:
    return JwtVerifier(
        jwks_url="http://identity-service/.well-known/jwks.json",
        issuer=issuer,
        http_client=http_client,
        **kwargs,
    )


async def test_jwt_verifier__valid_token__is_accepted_and_claims_extracted(keypair, jwks_client):
    private_key, kid = keypair
    user_id = uuid.uuid4()
    token = _sign_token(private_key, kid, user_id, roles=("USER", "ADMIN"))

    principal = await make_verifier(jwks_client).verify(token)

    assert principal == AuthenticatedPrincipal(user_id=user_id, roles=frozenset({"USER", "ADMIN"}))


async def test_jwt_verifier__caches_jwks_and_does_not_refetch_within_ttl(keypair, jwks_client):
    private_key, kid = keypair
    token = _sign_token(private_key, kid, uuid.uuid4())
    verifier = make_verifier(jwks_client, cache_ttl_seconds=600)

    await verifier.verify(token)
    await verifier.verify(token)

    assert jwks_client.call_count == 1


async def test_jwt_verifier__cache_expired_by_ttl__refetches_jwks(keypair, jwks_client):
    private_key, kid = keypair
    token = _sign_token(private_key, kid, uuid.uuid4())
    # 1st verify(): cached_at is None -> straight to refresh -> 1 clock
    # call sets cached_at=0.0. 2nd verify(): age check consumes a clock
    # call (1000.0 - 0.0 = 1000 > ttl 600 -> refetch) -> refresh consumes
    # one more, setting cached_at=1000.0.
    clock = iter([0.0, 1000.0, 1000.0]).__next__
    verifier = make_verifier(jwks_client, cache_ttl_seconds=600, clock=clock)

    await verifier.verify(token)  # cached_at = 0.0
    await verifier.verify(token)  # now = 1000.0, age 1000 > ttl 600 -- refetch

    assert jwks_client.call_count == 2


async def test_jwt_verifier__tampered_payload__is_rejected(keypair, jwks_client):
    private_key, kid = keypair
    token = _sign_token(private_key, kid, uuid.uuid4())
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}extra.{signature}"

    with pytest.raises(JwtVerificationError):
        await make_verifier(jwks_client).verify(tampered)


async def test_jwt_verifier__expired_token__is_rejected(keypair, jwks_client):
    private_key, kid = keypair
    token = _sign_token(private_key, kid, uuid.uuid4(), ttl=timedelta(seconds=-1))

    with pytest.raises(JwtVerificationError):
        await make_verifier(jwks_client).verify(token)


async def test_jwt_verifier__token_signed_by_a_different_keypair__is_rejected(jwks_client):
    wrong_signer_key = _generate_rsa_private_key()
    # Claims the SAME kid as the one published in the JWKS, but is signed
    # by a DIFFERENT private key -- signature verification must fail.
    token = _sign_token(wrong_signer_key, "key-1", uuid.uuid4())

    with pytest.raises(JwtVerificationError):
        await make_verifier(jwks_client).verify(token)


async def test_jwt_verifier__unknown_kid__is_rejected(keypair, jwks_client):
    private_key, _kid = keypair
    token = _sign_token(private_key, "some-other-kid", uuid.uuid4())

    with pytest.raises(JwtVerificationError):
        await make_verifier(jwks_client).verify(token)


async def test_jwt_verifier__wrong_issuer__is_rejected(keypair, jwks_client):
    private_key, kid = keypair
    token = _sign_token(private_key, kid, uuid.uuid4(), issuer="some-other-issuer")

    with pytest.raises(JwtVerificationError):
        await make_verifier(jwks_client, issuer=ISSUER).verify(token)


async def test_jwt_verifier__missing_user_id_claim__is_rejected(keypair, jwks_client):
    private_key, kid = keypair
    now = datetime.now(timezone.utc)
    payload = {"roles": ["USER"], "iat": now, "exp": now + timedelta(minutes=15), "iss": ISSUER}
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})

    with pytest.raises(JwtVerificationError):
        await make_verifier(jwks_client).verify(token)


async def test_jwt_verifier__jwks_fetch_failure__raises_typed_error(keypair):
    private_key, kid = keypair
    token = _sign_token(private_key, kid, uuid.uuid4())
    failing_client = _FakeHttpClient(mode="always_fail")

    with pytest.raises(JwksFetchError):
        await make_verifier(failing_client, overall_timeout_seconds=2.0).verify(token)


async def test_jwt_verifier__jwks_circuit_opens_after_consecutive_failures(keypair):
    """Mirrors profile-service's KmsEnvelopeDataEncryption circuit-breaker
    test pattern: pybreaker counts the call that reaches fail_max as the
    one that trips the breaker -- that call itself surfaces as
    JwksCircuitOpenError, not the underlying failure. fail_max=2 means the
    1st call fails plainly, the 2nd already opens the circuit."""
    private_key, kid = _generate_rsa_private_key(), "key-1"
    token = _sign_token(private_key, kid, uuid.uuid4())
    failing_client = _FakeHttpClient(mode="always_fail")
    verifier = make_verifier(
        failing_client, fail_max=2, reset_timeout_seconds=30, overall_timeout_seconds=2.0
    )

    with pytest.raises(JwksFetchError):
        await verifier.verify(token)
    with pytest.raises(JwksCircuitOpenError):
        await verifier.verify(token)
