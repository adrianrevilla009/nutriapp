import uuid
from datetime import timedelta

import jwt
import pytest
from jwt import algorithms

from domain.value_objects.role import Role
from infrastructure.security.jwt_token_issuer import JwtTokenIssuer, generate_rsa_key_pair


def make_issuer(ttl=timedelta(minutes=15)):
    private_pem, public_pem = generate_rsa_key_pair()
    return JwtTokenIssuer(private_pem, public_pem, key_id="key-1", access_token_ttl=ttl)


def public_key_from_jwks(issuer: JwtTokenIssuer):
    jwk = issuer.get_jwks()["keys"][0]
    return algorithms.RSAAlgorithm.from_jwk(jwk)


def test_jwt_issuer__issued_token__verifies_against_own_published_public_key():
    issuer = make_issuer()
    user_id = uuid.uuid4()
    token = issuer.issue_access_token(user_id, frozenset({Role.USER}))

    public_key = public_key_from_jwks(issuer)
    decoded = jwt.decode(token, public_key, algorithms=["RS256"])

    assert decoded["user_id"] == str(user_id)
    assert decoded["roles"] == ["USER"]


def test_jwt_issuer__claims_are_exactly_user_id_and_roles_plus_standard_claims():
    issuer = make_issuer()
    token = issuer.issue_access_token(uuid.uuid4(), frozenset({Role.USER, Role.ADMIN}))
    public_key = public_key_from_jwks(issuer)
    decoded = jwt.decode(token, public_key, algorithms=["RS256"])
    assert set(decoded.keys()) == {"user_id", "roles", "iat", "exp", "iss"}
    assert decoded["roles"] == ["ADMIN", "USER"]


def test_jwt_issuer__tampered_payload__fails_verification():
    issuer = make_issuer()
    token = issuer.issue_access_token(uuid.uuid4(), frozenset({Role.USER}))
    public_key = public_key_from_jwks(issuer)

    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}extra.{signature}"
    with pytest.raises(jwt.exceptions.InvalidTokenError):
        jwt.decode(tampered, public_key, algorithms=["RS256"])


def test_jwt_issuer__expired_token__fails_verification():
    issuer = make_issuer(ttl=timedelta(seconds=-1))
    token = issuer.issue_access_token(uuid.uuid4(), frozenset({Role.USER}))
    public_key = public_key_from_jwks(issuer)
    with pytest.raises(jwt.exceptions.ExpiredSignatureError):
        jwt.decode(token, public_key, algorithms=["RS256"])


def test_jwt_issuer__jwks_response__is_valid_jwk_set_with_only_public_key_material():
    issuer = make_issuer()
    jwks = issuer.get_jwks()
    assert "keys" in jwks
    key = jwks["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    # Only public key fields (n, e) — never a private exponent (d) or other
    # private key material.
    assert set(key.keys()) == {"kty", "use", "alg", "kid", "n", "e"}
