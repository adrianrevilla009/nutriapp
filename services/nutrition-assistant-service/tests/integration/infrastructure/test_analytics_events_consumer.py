"""AnalyticsEventsConsumer -- dispatch-level integration test against a
REAL Postgres, same scoped-down-from-full-AMQP rationale as
test_nutrition_calculation_events_consumer.py's docstring."""

from __future__ import annotations

import uuid

from infrastructure.messaging.analytics_events_consumer import dispatch_analytics_event
from infrastructure.persistence.postgres_analytics_signals_repository import (
    PostgresAnalyticsSignalsRepository,
)


def _deficiency_payload(user_id: uuid.UUID, disclaimer: str) -> dict:
    return {
        "user_id": str(user_id),
        "signal": "protein_g",
        "window_days": 7,
        "value": 60.0,
        "target_min": 100.0,
        "sample_size": 6,
        "disclaimer": disclaimer,
    }


async def test_deficiency_signal_idempotent_replay_preserves_disclaimer(session_factory) -> None:
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    disclaimer = "This is not a medical diagnosis, consult a professional."
    payload = _deficiency_payload(user_id, disclaimer)

    async with session_factory() as session:
        await dispatch_analytics_event(session, "NutrientDeficiencyDetected", event_id, payload)
        await dispatch_analytics_event(session, "NutrientDeficiencyDetected", event_id, payload)
        await session.commit()

    async with session_factory() as session:
        records = await PostgresAnalyticsSignalsRepository(session).recent_for_user(user_id)
        assert len(records) == 1  # applied exactly once
        assert disclaimer in records[0].content


async def test_unhandled_event_type_is_ignored(session_factory) -> None:
    async with session_factory() as session:
        await dispatch_analytics_event(session, "SomeFutureAnalyticsEvent", uuid.uuid4(), {})
        await session.commit()
