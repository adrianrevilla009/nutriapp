from __future__ import annotations

import uuid

import pytest

from infrastructure.persistence.postgres_processed_analytics_events_repository import (
    PostgresAnalyticsEventsRepository,
)
from infrastructure.persistence.postgres_processed_diary_events_repository import (
    PostgresDiaryEventsRepository,
)
from infrastructure.persistence.postgres_processed_entitlement_events_repository import (
    PostgresEntitlementEventsRepository,
)
from infrastructure.persistence.postgres_processed_nutrition_calculation_events_repository import (
    PostgresNutritionCalculationEventsRepository,
)

REPO_CLASSES = [
    PostgresDiaryEventsRepository,
    PostgresNutritionCalculationEventsRepository,
    PostgresAnalyticsEventsRepository,
    PostgresEntitlementEventsRepository,
]


@pytest.mark.parametrize("repo_class", REPO_CLASSES)
async def test_mark_processed_then_already_processed(session_factory, repo_class) -> None:
    event_id = uuid.uuid4()
    async with session_factory() as session:
        repo = repo_class(session)
        assert await repo.already_processed(event_id) is False
        await repo.mark_processed(event_id)
        await session.commit()

    async with session_factory() as session:
        repo = repo_class(session)
        assert await repo.already_processed(event_id) is True


@pytest.mark.parametrize("repo_class", REPO_CLASSES)
async def test_mark_processed_twice_does_not_error(session_factory, repo_class) -> None:
    event_id = uuid.uuid4()
    async with session_factory() as session:
        repo = repo_class(session)
        await repo.mark_processed(event_id)
        await repo.mark_processed(event_id)  # duplicate -- must not raise
        await session.commit()
