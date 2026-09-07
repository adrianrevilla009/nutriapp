"""POST /api/v1/chat -- test plan section 4."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_entitled_user_gets_200_with_expected_shape(app_client):
    client, container = app_client
    user_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/chat", json={"query": "what did I eat yesterday"}, headers=auth_headers(user_id)
    )

    assert response.status_code == 200
    body = response.json()
    assert "response" in body
    assert "had_sufficient_context" in body
    assert "disclaimer_included" in body
    assert "retrieved_record_count" in body


async def test_unentitled_user_gets_402_not_entitled(app_client):
    client, container = app_client
    container.entitlement_check._result = False
    user_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/chat", json={"query": "what did I eat"}, headers=auth_headers(user_id)
    )

    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_unauthenticated_returns_401(app_client):
    client, _container = app_client
    response = await client.post("/api/v1/chat", json={"query": "hi"})
    assert response.status_code == 401


async def test_empty_query_is_rejected_with_422(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    response = await client.post("/api/v1/chat", json={"query": ""}, headers=auth_headers(user_id))
    assert response.status_code == 422
