"""Direct tests of infrastructure/http/dependencies.py's OWN wiring --
NOT a re-test of shared_contracts.auth's JWT verification mechanics
(signature validation, expiry, wrong-issuer, missing/malformed header,
JWKS-fetch-failure fail-closed behavior, etc.), which is already covered
by packages/shared-contracts/tests/test_jwt_verifier.py and is identical
across every consuming service (re-proving it here per-service is pure
duplication, not additional coverage). The unauthenticated -> 401 path
is exercised end-to-end at the full-route level in
tests/contract/http/test_exercise_routes.py::test_post_unauthenticated_returns_401,
so it is deliberately not re-verified here too.

Scoped to exactly what this module adds on top of the shared dependency:
`get_container` (this service's own trivial accessor, zero shared logic)
and confirming `get_authenticated_user_id`'s lambda correctly resolves
*this service's* `Container.jwt_verifier` end-to-end for the success
path.
"""

from __future__ import annotations

import types
import uuid

from shared_contracts.testing.jwt_fixtures import (
    build_signed_token,
    build_test_jwt_verifier,
    generate_test_rsa_key_pair,
)

from infrastructure.http.dependencies import get_authenticated_user_id, get_container


def _fake_request(headers: dict, container) -> types.SimpleNamespace:
    app = types.SimpleNamespace(state=types.SimpleNamespace(container=container))
    return types.SimpleNamespace(headers=headers, app=app)


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
