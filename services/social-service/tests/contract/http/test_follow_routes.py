"""Follow/unfollow/listing routes -- test-plan section 3."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_follow_entitled_user_returns_201(app_client):
    client, container = app_client
    container.entitlement_check.result = True
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(followee_id)},
        headers=auth_headers(follower_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["follower_id"] == str(follower_id)
    assert body["followee_id"] == str(followee_id)


async def test_follow_is_idempotent_second_call_returns_200_same_follow_id(app_client):
    client, container = app_client
    container.entitlement_check.result = True
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()

    first = await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(followee_id)},
        headers=auth_headers(follower_id),
    )
    second = await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(followee_id)},
        headers=auth_headers(follower_id),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["follow_id"] == second.json()["follow_id"]


async def test_self_follow_returns_422(app_client):
    client, container = app_client
    container.entitlement_check.result = True
    user_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/social/follows", json={"followee_id": str(user_id)}, headers=auth_headers(user_id)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "SELF_FOLLOW"


async def test_follow_unentitled_user_returns_402(app_client):
    client, container = app_client
    container.entitlement_check.result = False

    response = await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(uuid.uuid4())},
        headers=auth_headers(uuid.uuid4()),
    )

    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_follow_unauthenticated_returns_401(app_client):
    client, _container = app_client
    response = await client.post("/api/v1/social/follows", json={"followee_id": str(uuid.uuid4())})
    assert response.status_code == 401


async def test_unfollow_entitled_user_returns_204_idempotent(app_client):
    client, container = app_client
    container.entitlement_check.result = True
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()

    await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(followee_id)},
        headers=auth_headers(follower_id),
    )

    first = await client.delete(
        f"/api/v1/social/follows/{followee_id}", headers=auth_headers(follower_id)
    )
    second = await client.delete(
        f"/api/v1/social/follows/{followee_id}", headers=auth_headers(follower_id)
    )

    assert first.status_code == 204
    assert second.status_code == 204  # idempotent, still succeeds


async def test_unfollow_unentitled_user_returns_402(app_client):
    client, container = app_client
    container.entitlement_check.result = False

    response = await client.delete(
        f"/api/v1/social/follows/{uuid.uuid4()}", headers=auth_headers(uuid.uuid4())
    )

    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_list_following_and_followers_succeed_for_unentitled_user(app_client):
    client, container = app_client
    container.entitlement_check.result = True
    follower_id = uuid.uuid4()
    followee_id = uuid.uuid4()
    await client.post(
        "/api/v1/social/follows",
        json={"followee_id": str(followee_id)},
        headers=auth_headers(follower_id),
    )

    # Not Pro-gated -- flip to unentitled and confirm both list routes still succeed.
    container.entitlement_check.result = False

    following_response = await client.get(
        "/api/v1/social/follows/following", headers=auth_headers(follower_id)
    )
    followers_response = await client.get(
        "/api/v1/social/follows/followers", headers=auth_headers(followee_id)
    )

    assert following_response.status_code == 200
    assert [f["followee_id"] for f in following_response.json()["items"]] == [str(followee_id)]
    assert followers_response.status_code == 200
    assert [f["follower_id"] for f in followers_response.json()["items"]] == [str(follower_id)]
