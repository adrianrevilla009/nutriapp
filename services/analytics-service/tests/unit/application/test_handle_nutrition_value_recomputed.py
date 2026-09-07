from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from application.commands.handle_nutrition_value_recomputed import (
    HandleNutritionValueRecomputedCommand,
    HandleNutritionValueRecomputedHandler,
)
from tests.fixtures.factories import (
    FakeAnomalyAlertsRepository,
    FakeMicronutrientWindowRepository,
    FakeOutboxRepository,
    FakeProcessedNutritionCalculationEventsRepository,
)

TODAY = date(2026, 6, 8)
OCCURRED_AT = datetime(2026, 6, 8, tzinfo=timezone.utc)


def _handler(processed=None, window=None, alerts=None, outbox=None):
    return HandleNutritionValueRecomputedHandler(
        processed or FakeProcessedNutritionCalculationEventsRepository(),
        window or FakeMicronutrientWindowRepository(),
        alerts or FakeAnomalyAlertsRepository(),
        outbox or FakeOutboxRepository(),
    )


async def _seed_breach_window(
    window: FakeMicronutrientWindowRepository, user_id, nutrient="protein_g"
):
    """5 of the last 7 days below target_min=50 -- primes list_recent so the
    NEXT upserted day (today) tips the breach evaluation over the threshold."""
    for n in range(1, 6):
        await window.upsert(user_id, nutrient, TODAY - timedelta(days=n), 30.0, target_min=50.0)
    for n in (6, 7):
        await window.upsert(user_id, nutrient, TODAY - timedelta(days=n), 60.0, target_min=50.0)
    await window.set_current_target_min(user_id, nutrient, 50.0)


async def test_scope_day_upserts_micronutrient_window_for_tracked_nutrients():
    window = FakeMicronutrientWindowRepository()
    user_id = uuid.uuid4()
    handler = _handler(window=window)

    await handler.handle(
        HandleNutritionValueRecomputedCommand(
            event_id=uuid.uuid4(),
            user_id=user_id,
            scope="day",
            on_date=TODAY,
            macros={"protein_g": 40.0, "fat_g": 30.0, "calories_kcal": 1800.0, "carbs_g": 200.0},
            occurred_at=OCCURRED_AT,
            correlation_id="corr-1",
        )
    )

    assert window.window[(user_id, "protein_g", TODAY)]["value"] == 40.0
    assert window.window[(user_id, "fat_g", TODAY)]["value"] == 30.0
    assert ("calories_kcal", TODAY) not in {(n, d) for (_, n, d) in window.window}


async def test_scope_entry_is_ignored_not_projected():
    window = FakeMicronutrientWindowRepository()
    handler = _handler(window=window)

    await handler.handle(
        HandleNutritionValueRecomputedCommand(
            event_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            scope="entry",
            on_date=None,
            macros={"protein_g": 999.0},
            occurred_at=OCCURRED_AT,
            correlation_id="corr-2",
        )
    )

    assert window.window == {}


async def test_breach_detected_and_not_in_cooldown_publishes_and_records():
    window = FakeMicronutrientWindowRepository()
    alerts = FakeAnomalyAlertsRepository()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    await _seed_breach_window(window, user_id)
    handler = _handler(window=window, alerts=alerts, outbox=outbox)

    await handler.handle(
        HandleNutritionValueRecomputedCommand(
            event_id=uuid.uuid4(),
            user_id=user_id,
            scope="day",
            on_date=TODAY,
            macros={"protein_g": 30.0, "fat_g": 50.0},
            occurred_at=OCCURRED_AT,
            correlation_id="corr-3",
        )
    )

    assert alerts.record_detection_calls == 1
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == "NutrientDeficiencyDetected"
    assert event.payload["signal"] == "protein_g"
    assert "not a medical diagnosis" in event.payload["disclaimer"]


async def test_breach_within_14_day_cooldown_does_not_republish():
    window = FakeMicronutrientWindowRepository()
    alerts = FakeAnomalyAlertsRepository()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    await _seed_breach_window(window, user_id)
    await alerts.record_detection(user_id, "protein_g", 7, 30.0, OCCURRED_AT - timedelta(days=13))
    handler = _handler(window=window, alerts=alerts, outbox=outbox)

    await handler.handle(
        HandleNutritionValueRecomputedCommand(
            event_id=uuid.uuid4(),
            user_id=user_id,
            scope="day",
            on_date=TODAY,
            macros={"protein_g": 30.0, "fat_g": 50.0},
            occurred_at=OCCURRED_AT,
            correlation_id="corr-4",
        )
    )

    assert len(outbox.enqueued) == 0


async def test_breach_past_14_day_cooldown_republishes():
    window = FakeMicronutrientWindowRepository()
    alerts = FakeAnomalyAlertsRepository()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    await _seed_breach_window(window, user_id)
    await alerts.record_detection(user_id, "protein_g", 7, 30.0, OCCURRED_AT - timedelta(days=15))
    handler = _handler(window=window, alerts=alerts, outbox=outbox)

    await handler.handle(
        HandleNutritionValueRecomputedCommand(
            event_id=uuid.uuid4(),
            user_id=user_id,
            scope="day",
            on_date=TODAY,
            macros={"protein_g": 30.0, "fat_g": 50.0},
            occurred_at=OCCURRED_AT,
            correlation_id="corr-5",
        )
    )

    assert len(outbox.enqueued) == 1


async def test_no_breach_no_alert_no_publish():
    window = FakeMicronutrientWindowRepository()
    alerts = FakeAnomalyAlertsRepository()
    outbox = FakeOutboxRepository()
    user_id = uuid.uuid4()
    for n in range(1, 8):
        await window.upsert(user_id, "protein_g", TODAY - timedelta(days=n), 60.0, target_min=50.0)
    await window.set_current_target_min(user_id, "protein_g", 50.0)
    handler = _handler(window=window, alerts=alerts, outbox=outbox)

    await handler.handle(
        HandleNutritionValueRecomputedCommand(
            event_id=uuid.uuid4(),
            user_id=user_id,
            scope="day",
            on_date=TODAY,
            macros={"protein_g": 60.0, "fat_g": 60.0},
            occurred_at=OCCURRED_AT,
            correlation_id="corr-6",
        )
    )

    assert alerts.record_detection_calls == 0
    assert outbox.enqueued == []


async def test_redelivered_event_id_does_not_double_upsert_or_double_publish():
    window = FakeMicronutrientWindowRepository()
    alerts = FakeAnomalyAlertsRepository()
    outbox = FakeOutboxRepository()
    processed = FakeProcessedNutritionCalculationEventsRepository()
    user_id = uuid.uuid4()
    await _seed_breach_window(window, user_id)
    handler = _handler(processed=processed, window=window, alerts=alerts, outbox=outbox)
    command = HandleNutritionValueRecomputedCommand(
        event_id=uuid.uuid4(),
        user_id=user_id,
        scope="day",
        on_date=TODAY,
        macros={"protein_g": 30.0, "fat_g": 50.0},
        occurred_at=OCCURRED_AT,
        correlation_id="corr-7",
    )

    await handler.handle(command)
    await handler.handle(command)

    assert len(outbox.enqueued) == 1
    assert alerts.record_detection_calls == 1
