from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers, project_pending_outbox_events


def _food_source_body(name: str = "Oats") -> dict:
    return dict(
        source_type="catalog_product",
        source_reference_id="prod-1",
        snapshot=dict(
            name=name,
            brand=None,
            quantity=100.0,
            unit="g",
            macros_per_unit=dict(calories_kcal=100, protein_g=5, carbs_g=10, fat_g=2),
        ),
    )


async def _log_entry(client, user_id):
    return await client.post(
        "/api/v1/diary/food-entries",
        json=dict(
            source=_food_source_body(),
            meal_slot="breakfast",
            occurred_at="2026-08-26T08:00:00Z",
        ),
        headers=auth_headers(user_id),
    )


async def test_log_food_entry_happy_path_returns_201_equivalent_200(app_client):
    user_id = uuid.uuid4()
    response = await _log_entry(app_client, user_id)
    assert response.status_code == 200
    body = response.json()
    assert body["meal_slot"] == "breakfast"
    assert body["source"]["snapshot"]["name"] == "Oats"


async def test_correct_food_entry_happy_path(app_client):
    user_id = uuid.uuid4()
    logged = await _log_entry(app_client, user_id)
    entry_id = logged.json()["entry_id"]

    response = await app_client.patch(
        f"/api/v1/diary/food-entries/{entry_id}",
        json=dict(
            source=_food_source_body("Rice"),
            meal_slot="lunch",
            occurred_at="2026-08-26T12:00:00Z",
        ),
        headers=auth_headers(user_id),
    )
    assert response.status_code == 200
    assert response.json()["meal_slot"] == "lunch"


async def test_correct_another_users_entry_returns_403(app_client):
    owner_id = uuid.uuid4()
    logged = await _log_entry(app_client, owner_id)
    entry_id = logged.json()["entry_id"]

    response = await app_client.patch(
        f"/api/v1/diary/food-entries/{entry_id}",
        json=dict(
            source=_food_source_body(), meal_slot="lunch", occurred_at="2026-08-26T12:00:00Z"
        ),
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 403


async def test_correct_unknown_entry_returns_404(app_client):
    response = await app_client.patch(
        f"/api/v1/diary/food-entries/{uuid.uuid4()}",
        json=dict(
            source=_food_source_body(), meal_slot="lunch", occurred_at="2026-08-26T12:00:00Z"
        ),
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 404


async def test_delete_food_entry_happy_path(app_client):
    user_id = uuid.uuid4()
    logged = await _log_entry(app_client, user_id)
    entry_id = logged.json()["entry_id"]

    response = await app_client.delete(
        f"/api/v1/diary/food-entries/{entry_id}", headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True


async def test_delete_another_users_entry_returns_403(app_client):
    owner_id = uuid.uuid4()
    logged = await _log_entry(app_client, owner_id)
    entry_id = logged.json()["entry_id"]

    response = await app_client.delete(
        f"/api/v1/diary/food-entries/{entry_id}", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 403


async def test_list_food_entries_returns_logged_entry(app_client, db_engine):
    user_id = uuid.uuid4()
    await _log_entry(app_client, user_id)
    await project_pending_outbox_events(db_engine)
    response = await app_client.get("/api/v1/diary/food-entries", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 1


async def test_missing_authenticated_user_returns_401(app_client):
    response = await app_client.get("/api/v1/diary/food-entries")
    assert response.status_code == 401


async def test_log_food_entry_invalid_meal_slot_rejected_by_schema(app_client):
    response = await app_client.post(
        "/api/v1/diary/food-entries",
        json=dict(
            source=_food_source_body(), meal_slot="brunch", occurred_at="2026-08-26T08:00:00Z"
        ),
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_MEAL_SLOT"
