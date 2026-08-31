"""GET /api/v1/recipes/search -- test-plan section 3."""

from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers


async def test_entitled_search_returns_matching_published_recipes(app_client):
    client, container = app_client
    author_id = uuid.uuid4()
    searcher_id = uuid.uuid4()

    create_response = await client.post(
        "/api/v1/recipes",
        json={"title": "Chocolate Cake", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(author_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    container.entitlement_check.result = True
    await client.post(f"/api/v1/recipes/{recipe_id}/publish", headers=auth_headers(author_id))

    response = await client.get(
        "/api/v1/recipes/search?q=chocolate", headers=auth_headers(searcher_id)
    )
    assert response.status_code == 200
    titles = [r["title"] for r in response.json()["items"]]
    assert titles == ["Chocolate Cake"]


async def test_unentitled_search_returns_402(app_client):
    client, container = app_client
    searcher_id = uuid.uuid4()
    container.entitlement_check.result = False

    response = await client.get(
        "/api/v1/recipes/search?q=anything", headers=auth_headers(searcher_id)
    )
    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_search_never_returns_an_unpublished_recipe_even_the_searchers_own(app_client):
    client, container = app_client
    searcher_id = uuid.uuid4()
    container.entitlement_check.result = True

    await client.post(
        "/api/v1/recipes",
        json={"title": "Chocolate Draft", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(searcher_id),
    )

    response = await client.get(
        "/api/v1/recipes/search?q=chocolate", headers=auth_headers(searcher_id)
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
