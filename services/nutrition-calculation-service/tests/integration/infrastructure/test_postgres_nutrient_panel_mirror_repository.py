from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from infrastructure.persistence.postgres_nutrient_panel_mirror_repository import (
    PostgresNutrientPanelMirrorRepository,
)


async def test_upsert_on_catalogued_then_updated_updates_in_place(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = PostgresNutrientPanelMirrorRepository(session)
        assert await repo.get_by_reference_id("product-1") is None

        await repo.upsert("product-1", {"calories_kcal": 100.0, "sugars_g": 5.0})
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutrientPanelMirrorRepository(session)
        panel = await repo.get_by_reference_id("product-1")
        assert panel["calories_kcal"] == 100.0

        await repo.upsert("product-1", {"calories_kcal": 250.0, "sugars_g": 8.0})
        await session.commit()

    async with session_factory() as session:
        repo = PostgresNutrientPanelMirrorRepository(session)
        panel = await repo.get_by_reference_id("product-1")
        assert panel["calories_kcal"] == 250.0
        assert panel["sugars_g"] == 8.0
