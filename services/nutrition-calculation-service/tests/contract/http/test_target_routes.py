from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.nutrition_target import NutritionTarget
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from domain.value_objects.sex import CalculationSexConstant
from infrastructure.persistence.postgres_nutrition_target_repository import (
    PostgresNutritionTargetRepository,
)
from infrastructure.persistence.postgres_target_history_repository import (
    PostgresTargetHistoryRepository,
)
from tests.contract.http.conftest import auth_headers

pytestmark = pytest.mark.usefixtures("db_engine")


def _make_target(user_id: uuid.UUID) -> NutritionTarget:
    return NutritionTarget(
        user_id=user_id,
        bmr_kcal=1673.75,
        tdee_kcal=2593.0,
        calorie_target_kcal=2093.0,
        macro_targets=MacroTargetRange(
            protein_g_min=112.0,
            protein_g_max=154.0,
            fat_g_min=46.5,
            carbs_g=200.0,
            carbs_floored=False,
        ),
        goal_type=GoalType.LOSE,
        activity_level=ActivityLevel.MODERATE,
        sex_constant_used=CalculationSexConstant.MALE,
        clamped=False,
        clamp_reason=None,
        formula_version="2026.1",
        reason="weight_recorded",
        effective_from=datetime.now(timezone.utc),
    )


async def test_get_target_returns_200_with_disclaimer(app_client, db_engine):
    user_id = uuid.uuid4()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresNutritionTargetRepository(session)
        await repo.upsert(_make_target(user_id))
        await session.commit()

    response = await app_client.get("/api/v1/nutrition/target", headers=auth_headers(user_id))

    assert response.status_code == 200
    body = response.json()
    assert body["calorie_target_kcal"] == 2093.0
    assert "informational estimate" in body["disclaimer"].lower()


async def test_get_target_without_jwt_returns_401(app_client):
    response = await app_client.get("/api/v1/nutrition/target")
    assert response.status_code == 401


async def test_get_target_not_found_returns_404(app_client):
    response = await app_client.get("/api/v1/nutrition/target", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["code"] == "NUTRITION_TARGET_NOT_FOUND"


async def test_get_target_history_returns_200(app_client, db_engine):
    user_id = uuid.uuid4()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        repo = PostgresTargetHistoryRepository(session)
        await repo.append(_make_target(user_id))
        await session.commit()

    response = await app_client.get(
        "/api/v1/nutrition/target/history", headers=auth_headers(user_id)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["history"]) == 1


async def test_get_target_history_without_jwt_returns_401(app_client):
    response = await app_client.get("/api/v1/nutrition/target/history")
    assert response.status_code == 401
