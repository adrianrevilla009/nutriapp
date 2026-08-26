from __future__ import annotations

import uuid

from tests.contract.http.conftest import auth_headers, project_pending_outbox_events


def _food_source_body(name: str = "Rice") -> dict:
    return dict(
        source_type="catalog_product",
        source_reference_id="prod-2",
        snapshot=dict(
            name=name,
            brand=None,
            quantity=150.0,
            unit="g",
            macros_per_unit=dict(calories_kcal=200, protein_g=4, carbs_g=45, fat_g=1),
        ),
    )


async def _plan_meal(client, user_id):
    return await client.post(
        "/api/v1/diary/meal-plan",
        json=dict(
            source=_food_source_body(), meal_slot="dinner", planned_for="2026-08-27T19:00:00Z"
        ),
        headers=auth_headers(user_id),
    )


async def test_plan_meal_happy_path(app_client):
    user_id = uuid.uuid4()
    response = await _plan_meal(app_client, user_id)
    assert response.status_code == 200
    assert response.json()["meal_slot"] == "dinner"


async def test_update_meal_plan_happy_path(app_client):
    user_id = uuid.uuid4()
    planned = await _plan_meal(app_client, user_id)
    plan_entry_id = planned.json()["plan_entry_id"]

    response = await app_client.patch(
        f"/api/v1/diary/meal-plan/{plan_entry_id}",
        json=dict(
            source=_food_source_body("Quinoa"),
            meal_slot="lunch",
            planned_for="2026-08-27T13:00:00Z",
        ),
        headers=auth_headers(user_id),
    )
    assert response.status_code == 200
    assert response.json()["meal_slot"] == "lunch"


async def test_update_another_users_plan_returns_403(app_client):
    owner_id = uuid.uuid4()
    planned = await _plan_meal(app_client, owner_id)
    plan_entry_id = planned.json()["plan_entry_id"]

    response = await app_client.patch(
        f"/api/v1/diary/meal-plan/{plan_entry_id}",
        json=dict(
            source=_food_source_body(), meal_slot="lunch", planned_for="2026-08-27T13:00:00Z"
        ),
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 403


async def test_remove_meal_plan_happy_path(app_client):
    user_id = uuid.uuid4()
    planned = await _plan_meal(app_client, user_id)
    plan_entry_id = planned.json()["plan_entry_id"]

    response = await app_client.delete(
        f"/api/v1/diary/meal-plan/{plan_entry_id}", headers=auth_headers(user_id)
    )
    assert response.status_code == 200
    assert response.json()["removed"] is True


async def test_get_meal_plan_calendar_returns_planned_entry(app_client, db_engine):
    user_id = uuid.uuid4()
    await _plan_meal(app_client, user_id)
    await project_pending_outbox_events(db_engine)
    response = await app_client.get(
        "/api/v1/diary/meal-plan",
        params={"from": "2026-08-01", "to": "2026-08-31"},
        headers=auth_headers(user_id),
    )
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 1
