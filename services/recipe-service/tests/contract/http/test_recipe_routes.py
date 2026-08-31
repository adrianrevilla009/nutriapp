"""All 7 recipe-service HTTP routes -- test-plan section 3."""

from __future__ import annotations

import uuid

from domain.ports.catalog_product_port import ResolvedIngredientProduct
from domain.value_objects.nutrient_panel import NutrientPanel
from tests.contract.http.conftest import auth_headers


def _seed_resolvable_product(container, product_id: uuid.UUID) -> None:
    container.catalog_products.resolvable[product_id] = ResolvedIngredientProduct(
        product_id=product_id,
        nutrition_per_100g=NutrientPanel(
            energy_kcal=100.0, protein_g=5.0, carbohydrates_g=10.0, fat_g=2.0
        ),
    )


async def test_create_recipe_returns_201_with_computed_totals(app_client):
    client, container = app_client
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    _seed_resolvable_product(container, product_id)

    response = await client.post(
        "/api/v1/recipes",
        json={
            "title": "Omelette",
            "instructions": "Whisk and cook.",
            "servings": 2,
            "ingredients": [{"catalog_product_id": str(product_id), "quantity_grams": 200}],
        },
        headers=auth_headers(user_id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["computed_totals"]["per_recipe"]["macros"]["calories_kcal"] == 200.0
    assert body["computed_totals"]["per_serving"]["macros"]["calories_kcal"] == 100.0
    assert body["computed_totals"]["per_recipe"]["macros_status"] == "available"
    assert body["computed_totals"]["per_serving"]["macros_status"] == "available"
    assert body["is_published"] is False


async def test_create_recipe_unresolvable_ingredient_returns_422(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/recipes",
        json={
            "title": "Bad Recipe",
            "instructions": "N/A",
            "servings": 1,
            "ingredients": [{"catalog_product_id": str(uuid.uuid4()), "quantity_grams": 100}],
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNRESOLVABLE_INGREDIENT"


async def test_create_recipe_invalid_servings_returns_422(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/recipes",
        json={"title": "Bad Servings", "instructions": "N/A", "servings": 0, "ingredients": []},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 422


async def test_create_recipe_invalid_quantity_returns_422(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/recipes",
        json={
            "title": "Bad Quantity",
            "instructions": "N/A",
            "servings": 1,
            "ingredients": [{"catalog_product_id": str(uuid.uuid4()), "quantity_grams": -5}],
        },
        headers=auth_headers(user_id),
    )
    assert response.status_code == 422


async def test_create_recipe_unauthenticated_returns_401(app_client):
    client, _container = app_client
    response = await client.post(
        "/api/v1/recipes",
        json={"title": "N/A", "instructions": "N/A", "servings": 1, "ingredients": []},
    )
    assert response.status_code == 401


async def test_update_recipe_recomputes_totals(app_client):
    client, container = app_client
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    _seed_resolvable_product(container, product_id)

    create_response = await client.post(
        "/api/v1/recipes",
        json={"title": "Original", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(user_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    update_response = await client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={
            "title": "Updated",
            "instructions": "New steps.",
            "servings": 1,
            "ingredients": [{"catalog_product_id": str(product_id), "quantity_grams": 100}],
        },
        headers=auth_headers(user_id),
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["title"] == "Updated"
    assert body["computed_totals"]["per_recipe"]["macros"]["calories_kcal"] == 100.0


async def test_update_nonexistent_recipe_returns_404(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/recipes/{uuid.uuid4()}",
        json={"title": "N/A", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 404


async def test_update_another_users_recipe_returns_404(app_client):
    client, _container = app_client
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    create_response = await client.post(
        "/api/v1/recipes",
        json={"title": "Mine", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(owner_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    response = await client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={"title": "Hijacked", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(other_user_id),
    )
    assert response.status_code == 404


async def test_get_own_recipe_including_draft(app_client):
    client, _container = app_client
    user_id = uuid.uuid4()
    create_response = await client.post(
        "/api/v1/recipes",
        json={"title": "Draft", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(user_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    response = await client.get(f"/api/v1/recipes/{recipe_id}", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert response.json()["is_published"] is False


async def test_get_another_users_recipe_returns_404(app_client):
    client, _container = app_client
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    create_response = await client.post(
        "/api/v1/recipes",
        json={"title": "Mine", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(owner_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    response = await client.get(f"/api/v1/recipes/{recipe_id}", headers=auth_headers(other_user_id))
    assert response.status_code == 404


async def test_list_mine_includes_drafts_excludes_other_users(app_client):
    client, _container = app_client
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    await client.post(
        "/api/v1/recipes",
        json={"title": "Mine", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(owner_id),
    )
    await client.post(
        "/api/v1/recipes",
        json={"title": "Not Mine", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(other_user_id),
    )

    response = await client.get("/api/v1/recipes?mine=true", headers=auth_headers(owner_id))
    assert response.status_code == 200
    titles = [r["title"] for r in response.json()["items"]]
    assert titles == ["Mine"]


async def test_publish_entitled_user_all_ingredients_resolvable_returns_200(app_client):
    client, container = app_client
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    _seed_resolvable_product(container, product_id)
    container.entitlement_check.result = True

    create_response = await client.post(
        "/api/v1/recipes",
        json={
            "title": "Publishable",
            "instructions": "N/A",
            "servings": 1,
            "ingredients": [{"catalog_product_id": str(product_id), "quantity_grams": 100}],
        },
        headers=auth_headers(user_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    response = await client.post(
        f"/api/v1/recipes/{recipe_id}/publish", headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    assert response.json()["is_published"] is True


async def test_publish_unentitled_user_returns_402(app_client):
    client, container = app_client
    user_id = uuid.uuid4()
    container.entitlement_check.result = False

    create_response = await client.post(
        "/api/v1/recipes",
        json={"title": "N/A", "instructions": "N/A", "servings": 1, "ingredients": []},
        headers=auth_headers(user_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    response = await client.post(
        f"/api/v1/recipes/{recipe_id}/publish", headers=auth_headers(user_id)
    )
    assert response.status_code == 402
    assert response.json()["code"] == "NOT_ENTITLED"


async def test_publish_unresolvable_ingredient_returns_422(app_client):
    client, container = app_client
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    _seed_resolvable_product(container, product_id)
    container.entitlement_check.result = True

    create_response = await client.post(
        "/api/v1/recipes",
        json={
            "title": "Later Unresolvable",
            "instructions": "N/A",
            "servings": 1,
            "ingredients": [{"catalog_product_id": str(product_id), "quantity_grams": 100}],
        },
        headers=auth_headers(user_id),
    )
    recipe_id = create_response.json()["recipe_id"]

    # Product removed from catalog since creation.
    del container.catalog_products.resolvable[product_id]

    response = await client.post(
        f"/api/v1/recipes/{recipe_id}/publish", headers=auth_headers(user_id)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNRESOLVABLE_INGREDIENT"


async def test_unpublish_then_delete_are_idempotent(app_client):
    client, container = app_client
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    _seed_resolvable_product(container, product_id)
    container.entitlement_check.result = True

    create_response = await client.post(
        "/api/v1/recipes",
        json={
            "title": "To Unpublish",
            "instructions": "N/A",
            "servings": 1,
            "ingredients": [{"catalog_product_id": str(product_id), "quantity_grams": 100}],
        },
        headers=auth_headers(user_id),
    )
    recipe_id = create_response.json()["recipe_id"]
    await client.post(f"/api/v1/recipes/{recipe_id}/publish", headers=auth_headers(user_id))

    first = await client.post(
        f"/api/v1/recipes/{recipe_id}/unpublish", headers=auth_headers(user_id)
    )
    assert first.status_code == 200
    assert first.json()["is_published"] is False

    second = await client.post(
        f"/api/v1/recipes/{recipe_id}/unpublish", headers=auth_headers(user_id)
    )
    assert second.status_code == 200  # idempotent, still 200

    delete_response = await client.delete(
        f"/api/v1/recipes/{recipe_id}", headers=auth_headers(user_id)
    )
    assert delete_response.status_code == 204

    second_delete = await client.delete(
        f"/api/v1/recipes/{recipe_id}", headers=auth_headers(user_id)
    )
    assert second_delete.status_code == 204  # idempotent, still succeeds
