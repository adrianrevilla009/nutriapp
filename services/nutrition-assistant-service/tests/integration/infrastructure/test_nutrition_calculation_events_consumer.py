"""NutritionCalculationEventsConsumer -- dispatch-level integration test
against a REAL Postgres (testcontainers), calling dispatch_nutrition_calculation_event
directly rather than through a real RabbitMQ channel.

DEVIATION FROM THE FULL RABBITMQ-LEVEL TEST (flagged honestly, not
silently scoped down): test_diary_events_consumer.py exercises this
service's ONE full real-AMQP consumer test (publish -> consume -> DLQ),
proving ResilientTopicConsumer's retry/DLQ plumbing works end-to-end for
real. Since NutritionCalculationEventsConsumer and AnalyticsEventsConsumer
share that exact same base class and only differ in their dispatch
function (already unit-tested at the application layer), this test
exercises dispatch_nutrition_calculation_event's real-Postgres
idempotency directly instead of re-proving the shared AMQP plumbing a
second and third time -- a deliberate time-scoped choice, called out in
the final report rather than silently presented as equivalent coverage
to the diary consumer's real-AMQP test."""

from __future__ import annotations

import uuid

from infrastructure.messaging.nutrition_calculation_events_consumer import (
    dispatch_nutrition_calculation_event,
)
from infrastructure.persistence.postgres_nutrition_history_repository import (
    PostgresNutritionHistoryRepository,
)


def _value_recomputed_payload(user_id: uuid.UUID) -> dict:
    return {
        "user_id": str(user_id),
        "scope": "day",
        "entry_id": None,
        "date": "2026-09-07",
        "macros": {"calories_kcal": 1800.0, "protein_g": 120.0, "carbs_g": 200.0, "fat_g": 60.0},
        "micronutrients": None,
        "micronutrients_status": "unavailable",
        "is_estimated": False,
        "confidence_range": None,
        "formula_version": "v1",
        "reason": "food_entry_logged",
        "recomputed_at": "2026-09-07T12:00:00+00:00",
    }


async def test_value_recomputed_idempotent_replay(session_factory) -> None:
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    payload = _value_recomputed_payload(user_id)

    async with session_factory() as session:
        await dispatch_nutrition_calculation_event(
            session, "NutritionValueRecomputed", event_id, payload
        )
        await dispatch_nutrition_calculation_event(
            session, "NutritionValueRecomputed", event_id, payload
        )
        await session.commit()

    async with session_factory() as session:
        records = await PostgresNutritionHistoryRepository(session).recent_for_user(user_id)
        matching = [r for r in records if "1800.0" in r.content]
        assert len(matching) == 1  # applied exactly once despite duplicate delivery


async def test_target_updated_projects_current_target(session_factory) -> None:
    user_id = uuid.uuid4()
    payload = {
        "user_id": str(user_id),
        "bmr_kcal": 1500.0,
        "tdee_kcal": 2200.0,
        "calorie_target_kcal": 2000.0,
        "macro_targets": {
            "protein_g_min": 100.0,
            "protein_g_max": 180.0,
            "fat_g_min": 50.0,
            "carbs_g": 220.0,
        },
        "goal_type": "MAINTAIN",
        "activity_level": "MODERATE",
        "activity_adjustment_kcal": None,
        "clamped": False,
        "clamp_reason": None,
        "formula_version": "v1",
        "reason": "weight_recorded",
        "effective_from": "2026-09-07T12:00:00+00:00",
    }
    async with session_factory() as session:
        await dispatch_nutrition_calculation_event(
            session, "NutritionTargetUpdated", uuid.uuid4(), payload
        )
        await session.commit()

    async with session_factory() as session:
        records = await PostgresNutritionHistoryRepository(session).recent_for_user(user_id)
        assert any("target" in r.record_id for r in records)


async def test_unhandled_event_type_is_ignored(session_factory) -> None:
    async with session_factory() as session:
        # Must not raise -- forward-compatible with a future, unhandled event type.
        await dispatch_nutrition_calculation_event(session, "SomeFutureEventType", uuid.uuid4(), {})
        await session.commit()
