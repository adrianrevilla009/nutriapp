from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.services.nutrient_total_calculator import calculate_entry_nutrient_total
from infrastructure.persistence.postgres_daily_nutrition_total_repository import (
    PostgresDailyNutritionTotalRepository,
)

MACROS = {"calories_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0}


async def test_upsert_by_user_id_and_date_round_trip(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    total_date = date(2026, 8, 25)

    line = calculate_entry_nutrient_total(
        quantity_grams=150.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        micronutrient_panel_per_100g=None,
    )

    async with session_factory() as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        assert await repo.get(user_id, total_date) is None

        total = DailyNutritionTotal(user_id=user_id, total_date=total_date)
        total = total.with_entry_upserted(entry_id, line)
        await repo.upsert(total)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        fetched = await repo.get(user_id, total_date)
        assert fetched is not None
        assert fetched.compute_total().macros.calories_kcal == 300.0
        assert entry_id in fetched.entries


async def test_find_date_for_entry_resolves_and_none_when_missing(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    total_date = date(2026, 8, 25)
    line = calculate_entry_nutrient_total(
        quantity_grams=100.0,
        macros_per_unit=MACROS,
        source_type="catalog_product",
        micronutrient_panel_per_100g=None,
    )

    async with session_factory() as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        total = DailyNutritionTotal(user_id=user_id, total_date=total_date)
        total = total.with_entry_upserted(entry_id, line)
        await repo.upsert(total)
        await session.commit()

    async with session_factory() as session:
        repo = PostgresDailyNutritionTotalRepository(session)
        found_date = await repo.find_date_for_entry(user_id, entry_id)
        assert found_date == total_date

        missing = await repo.find_date_for_entry(user_id, uuid.uuid4())
        assert missing is None
