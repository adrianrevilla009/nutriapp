from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.services.nutrient_total_calculator import calculate_entry_nutrient_total
from infrastructure.persistence.postgres_daily_nutrition_total_repository import (
    PostgresDailyNutritionTotalRepository,
)
from tests.contract.http.conftest import auth_headers

pytestmark = pytest.mark.usefixtures("db_engine")

MACROS = {"calories_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0}


async def test_get_daily_total_returns_200_with_disclaimer(app_client, db_engine):
    user_id = uuid.uuid4()
    total_date = date(2026, 8, 25)
    line = calculate_entry_nutrient_total(
        quantity_grams=150.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        micronutrient_panel_per_100g=None,
    )
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        total = DailyNutritionTotal(user_id=user_id, total_date=total_date)
        total = total.with_entry_upserted(uuid.uuid4(), line)
        await repo.upsert(total)
        await session.commit()

    response = await app_client.get(
        f"/api/v1/nutrition/totals/{total_date.isoformat()}", headers=auth_headers(user_id)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["calories_kcal"] == 300.0
    assert body["micronutrients_status"] == "unavailable"
    assert "informational estimate" in body["disclaimer"].lower()


async def test_get_daily_total_without_jwt_returns_401(app_client):
    response = await app_client.get(f"/api/v1/nutrition/totals/{date(2026, 8, 25).isoformat()}")
    assert response.status_code == 401


async def test_get_daily_total_not_found_returns_404(app_client):
    response = await app_client.get(
        f"/api/v1/nutrition/totals/{date(2026, 8, 25).isoformat()}",
        headers=auth_headers(uuid.uuid4()),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "DAILY_NUTRITION_TOTAL_NOT_FOUND"
