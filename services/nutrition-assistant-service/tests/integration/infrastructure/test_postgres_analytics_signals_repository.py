from __future__ import annotations

import uuid

from infrastructure.persistence.postgres_analytics_signals_repository import (
    PostgresAnalyticsSignalsRepository,
)


async def test_deficiency_signal_round_trip_preserves_disclaimer(session_factory) -> None:
    user_id = uuid.uuid4()
    disclaimer = "This is not a medical diagnosis, consult a professional."
    async with session_factory() as session:
        repo = PostgresAnalyticsSignalsRepository(session)
        await repo.upsert_deficiency_signal(
            user_id, "protein_g", "below target 5/7 days", disclaimer
        )
        await session.commit()

    async with session_factory() as session:
        repo = PostgresAnalyticsSignalsRepository(session)
        records = await repo.recent_for_user(user_id)
        assert len(records) == 1
        assert disclaimer in records[0].content
        assert records[0].source == "analytics"
