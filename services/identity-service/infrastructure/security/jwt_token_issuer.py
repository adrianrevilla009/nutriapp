"""JwtTokenIssuer — implements TokenIssuerPort per ADR-0022.

Issues short-lived RS256 access tokens carrying only `user_id` + `roles`
claims, and exposes the public key as a JWK Set for
`/.well-known/jwks.json`. Only identity-service ever holds the private key.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from domain.value_objects.role import Role

DEFAULT_ACCESS_TOKEN_TTL = timedelta(minutes=15)


def generate_rsa_key_pair() -> tuple[bytes, bytes]:
    """Generates a fresh RSA key pair (PEM-encoded). Used at service
    bootstrap / by the platform-infra `secrets` Terraform module
    (`tls_private_key`, per the platform-infra plan section 6) — exposed
    here too so local dev / tests don't need Terraform to run."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def _int_to_base64url(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class JwtTokenIssuer:
    """Implements domain.ports.token_issuer_port.TokenIssuerPort."""

    def __init__(
        self,
        private_key_pem: bytes,
        public_key_pem: bytes,
        key_id: str,
        access_token_ttl: timedelta = DEFAULT_ACCESS_TOKEN_TTL,
        issuer: str = "identity-service",
    ) -> None:
        # This service only ever generates/expects RSA keys (ADR-0022, RS256)
        # -- serialization.load_pem_*_key's return type is a broad union
        # covering every key algorithm the `cryptography` library supports.
        # Narrowing here (rather than typing these attributes as that union)
        # is both a real type-safety improvement and a genuine runtime
        # validation: a non-RSA PEM fails loudly here, not confusingly at
        # first-use downstream.
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise TypeError("identity-service's signing key must be RSA (ADR-0022).")
        self._private_key: rsa.RSAPrivateKey = private_key

        public_key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise TypeError("identity-service's public key must be RSA (ADR-0022).")
        self._public_key: rsa.RSAPublicKey = public_key
        self._key_id = key_id
        self._ttl = access_token_ttl
        self._issuer = issuer

    def issue_access_token(self, user_id: uuid.UUID, roles: frozenset[Role]) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "user_id": str(user_id),
            "roles": sorted(role.value for role in roles),
            "iat": now,
            "exp": now + self._ttl,
            "iss": self._issuer,
        }
        return jwt.encode(
            payload,
            self._private_key,
            algorithm="RS256",
            headers={"kid": self._key_id},
        )

    def get_jwks(self) -> dict[str, Any]:
        public_numbers = self._public_key.public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self._key_id,
                    "n": _int_to_base64url(public_numbers.n),
                    "e": _int_to_base64url(public_numbers.e),
                }
            ]
        }
