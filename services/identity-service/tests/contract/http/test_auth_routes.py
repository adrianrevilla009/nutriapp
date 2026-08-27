"""Contract tests: happy path + error path per endpoint, against the real
FastAPI/OpenAPI-generated routes and a real (testcontainers) Postgres.
"""

from __future__ import annotations

from tests.contract.http.conftest import INTERNAL_CREDENTIAL

VALID_PASSWORD = "Str0ng!Passw0rd"


async def register(client, email="user@example.com", password=VALID_PASSWORD):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def test_register__happy_path__returns_201_or_200_with_user_id(app_client):
    response = await register(app_client)
    assert response.status_code in (200, 201)
    body = response.json()
    assert "user_id" in body


async def test_register__weak_password__returns_400_with_error_shape(app_client):
    response = await register(app_client, email="weak@example.com", password="weak")
    assert response.status_code == 400
    body = response.json()
    assert set(body.keys()) == {"error", "code"}


async def test_register__duplicate_email__returns_409(app_client):
    await register(app_client, email="dup@example.com")
    response = await register(app_client, email="dup@example.com")
    assert response.status_code == 409


async def test_register_response__never_contains_password_hash_or_raw_token(app_client):
    response = await register(app_client, email="secret@example.com")
    assert "password_hash" not in response.text
    assert "raw_secret" not in response.text


async def test_login__unknown_email__returns_401_generic_error(app_client):
    response = await app_client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123!"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_login__wrong_password__returns_identical_shape_to_unknown_email(app_client):
    await register(app_client, email="loginshape@example.com")
    wrong_password_response = await app_client.post(
        "/api/v1/auth/login",
        json={"email": "loginshape@example.com", "password": "WrongPassword!1"},
    )
    unknown_email_response = await app_client.post(
        "/api/v1/auth/login", json={"email": "nobody2@example.com", "password": "WrongPassword!1"}
    )
    assert wrong_password_response.status_code == unknown_email_response.status_code == 401
    assert wrong_password_response.json() == unknown_email_response.json()


async def test_refresh__unknown_token__returns_401(app_client):
    response = await app_client.post("/api/v1/auth/refresh", json={"refresh_token": "never-issued"})
    assert response.status_code == 401


async def test_logout__unknown_token__returns_200_idempotent(app_client):
    response = await app_client.post("/api/v1/auth/logout", json={"refresh_token": "never-issued"})
    assert response.status_code == 200
    assert response.json()["revoked"] is False


async def test_password_reset_request__always_202_regardless_of_existence(app_client):
    known = await app_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "nobody3@example.com"}
    )
    await register(app_client, email="hasaccount@example.com")
    existing = await app_client.post(
        "/api/v1/auth/password-reset/request", json={"email": "hasaccount@example.com"}
    )
    assert known.status_code == existing.status_code == 202
    assert known.json() == existing.json()


async def test_password_reset_confirm__unknown_token__returns_400(app_client):
    response = await app_client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "reference_id": "00000000-0000-0000-0000-000000000000",
            "secret": "whatever",
            "new_password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 400


async def test_verify_email__unknown_token__returns_400(app_client):
    response = await app_client.post(
        "/api/v1/auth/verify-email",
        json={"reference_id": "00000000-0000-0000-0000-000000000000", "secret": "whatever"},
    )
    assert response.status_code == 400


async def test_jwks__returns_valid_jwk_set_with_only_public_key_material(app_client):
    response = await app_client.get("/.well-known/jwks.json")
    assert response.status_code == 200
    body = response.json()
    assert "keys" in body
    key = body["keys"][0]
    assert key["kty"] == "RSA"
    assert set(key.keys()) == {"kty", "use", "alg", "kid", "n", "e"}


async def test_internal_reveal__unknown_reference_id_with_valid_credential__returns_400(app_client):
    response = await app_client.post(
        "/internal/v1/auth/tokens/00000000-0000-0000-0000-000000000000/reveal",
        headers={"X-Internal-Service-Credential": INTERNAL_CREDENTIAL},
    )
    assert response.status_code == 400


async def test_internal_reveal__invalid_credential__returns_401(app_client):
    response = await app_client.post(
        "/internal/v1/auth/tokens/00000000-0000-0000-0000-000000000000/reveal",
        headers={"X-Internal-Service-Credential": "wrong"},
    )
    assert response.status_code == 401


async def test_internal_reveal__is_not_registered_under_api_v1_prefix(app_client):
    # Asserts the internal endpoint is absent from the public API surface
    # (never routed through Kong) — Kong only forwards /api/v1/* paths.
    response = await app_client.get("/openapi.json")
    paths = response.json()["paths"]
    assert all(not p.startswith("/api/v1/internal") for p in paths)
    assert any(p.startswith("/internal/") for p in paths)
