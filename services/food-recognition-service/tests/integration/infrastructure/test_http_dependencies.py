"""Direct tests of infrastructure/http/dependencies.py's authentication
dependency -- covers the branches contract tests (which swap in a fake
Container/JwtVerifier per-route) don't reach: bad-signature token, missing
'Bearer ' prefix, an empty bearer token, and the JWKS-fetch-failure
fail-closed path."""

from __future__ import annotations

import types
import uuid

import pytest
from fastapi import HTTPException
from shared_contracts.auth.jwt_verifier import JwtVerifier

from infrastructure.http.dependencies import (
    get_authenticated_user_id,
    get_container,
    get_correlation_id,
)
from shared_contracts.testing.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)


def _fake_request(headers: dict, container) -> types.SimpleNamespace:
    app = types.SimpleNamespace(state=types.SimpleNamespace(container=container))
    return types.SimpleNamespace(headers=headers, app=app)


async def test_missing_authorization_header_raises_401():
    request = _fake_request({}, container=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user_id(request)
    assert exc_info.value.status_code == 401


async def test_non_bearer_authorization_header_raises_401():
    request = _fake_request({"Authorization": "Basic abc"}, container=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user_id(request)
    assert exc_info.value.status_code == 401


async def test_empty_bearer_token_raises_401():
    request = _fake_request({"Authorization": "Bearer   "}, container=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user_id(request)
    assert exc_info.value.status_code == 401


async def test_invalid_signature_token_raises_401():
    private_key = generate_test_rsa_key_pair()
    other_private_key = generate_test_rsa_key_pair()
    verifier = build_test_jwt_verifier(private_key)
    bad_token = build_signed_token(other_private_key, uuid.uuid4())

    container = types.SimpleNamespace(jwt_verifier=verifier)
    request = _fake_request({"Authorization": f"Bearer {bad_token}"}, container=container)

    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user_id(request)
    assert exc_info.value.status_code == 401


async def test_jwks_fetch_failure_fails_closed_with_401():
    class _FailingHttpClient:
        def get(self, *args, **kwargs):
            raise RuntimeError("network down")

    verifier = JwtVerifier(
        jwks_url="http://identity-service.test/.well-known/jwks.json",
        issuer="identity-service",
        http_client=_FailingHttpClient(),
    )
    private_key = generate_test_rsa_key_pair()
    token = build_signed_token(private_key, uuid.uuid4())
    container = types.SimpleNamespace(jwt_verifier=verifier)
    request = _fake_request({"Authorization": f"Bearer {token}"}, container=container)

    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user_id(request)
    assert exc_info.value.status_code == 401


async def test_valid_token_returns_user_id():
    private_key = generate_test_rsa_key_pair()
    verifier = build_test_jwt_verifier(private_key)
    user_id = uuid.uuid4()
    token = build_signed_token(private_key, user_id)
    container = types.SimpleNamespace(jwt_verifier=verifier)
    request = _fake_request({"Authorization": f"Bearer {token}"}, container=container)

    result = await get_authenticated_user_id(request)
    assert result == user_id


def test_get_container_returns_app_state_container():
    container = object()
    request = _fake_request({}, container=container)
    assert get_container(request) is container


def test_get_correlation_id_generates_when_absent():
    request = _fake_request({}, container=None)
    assert get_correlation_id(request)


def test_get_correlation_id_propagates_existing_header():
    request = _fake_request({"X-Correlation-Id": "abc-123"}, container=None)
    assert get_correlation_id(request) == "abc-123"
