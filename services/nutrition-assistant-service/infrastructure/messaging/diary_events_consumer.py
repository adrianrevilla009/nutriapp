"""DiaryEventsConsumer -- subscribes to diary-service's `diary.events`
topic exchange (binding `diary.#`, forward-compatible with unhandled
future diary event types -- acknowledged and ignored, same convention
analytics-service's consumers use) and dispatches
FoodEntryLogged/FoodEntryCorrected/FoodEntryDeleted/WaterIntakeLogged/
WaterIntakeRemoved to their command handlers. Idempotent by event_id via
ProcessedDiaryEventsRepositoryPort -- ONE ledger shared across all five
diary event types.

Each event's client-supplied `source.snapshot`/`amount_ml` fields are
reduced to a short, human-readable `summary` string here -- this
service's diary_history projection stores a summary, not the full
structured macro breakdown (that lives in nutrition_history, projected
separately from nutrition-calculation-service's own events)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_food_entry_corrected import (
    HandleFoodEntryCorrectedCommand,
    HandleFoodEntryCorrectedHandler,
)
from application.commands.handle_food_entry_deleted import (
    HandleFoodEntryDeletedCommand,
    HandleFoodEntryDeletedHandler,
)
from application.commands.handle_food_entry_logged import (
    HandleFoodEntryLoggedCommand,
    HandleFoodEntryLoggedHandler,
)
from application.commands.handle_water_intake_logged import (
    HandleWaterIntakeLoggedCommand,
    HandleWaterIntakeLoggedHandler,
)
from application.commands.handle_water_intake_removed import (
    HandleWaterIntakeRemovedCommand,
    HandleWaterIntakeRemovedHandler,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_diary_history_repository import (
    PostgresDiaryHistoryRepository,
)
from infrastructure.persistence.postgres_processed_diary_events_repository import (
    PostgresDiaryEventsRepository,
)

EXCHANGE_NAME = "diary.events"
BINDING_ROUTING_KEY = "diary.#"
QUEUE_NAME = "nutrition-assistant-service.diary_events"
DLQ_NAME = "nutrition-assistant-service.diary_events.dlq"
RETRY_HEADER = "x-nutrition-assistant-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset(
    {
        "FoodEntryLogged",
        "FoodEntryCorrected",
        "FoodEntryDeleted",
        "WaterIntakeLogged",
        "WaterIntakeRemoved",
    }
)


def _food_entry_summary(payload: dict[str, Any]) -> str:
    snapshot = payload["source"]["snapshot"]
    return (
        f"{snapshot['quantity']}{snapshot['unit']} {snapshot['name']} "
        f"({payload.get('meal_slot', 'unspecified meal')})"
    )


def _water_intake_summary(payload: dict[str, Any]) -> str:
    return f"{payload['amount_ml']}ml water"


async def dispatch_diary_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresDiaryEventsRepository(session)
    diary_history = PostgresDiaryHistoryRepository(session)

    if event_type == "FoodEntryLogged":
        await HandleFoodEntryLoggedHandler(processed_events, diary_history).handle(
            HandleFoodEntryLoggedCommand(
                event_id=event_id,
                entry_id=uuid.UUID(payload["entry_id"]),
                user_id=uuid.UUID(payload["user_id"]),
                summary=_food_entry_summary(payload),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        )
    elif event_type == "FoodEntryCorrected":
        await HandleFoodEntryCorrectedHandler(processed_events, diary_history).handle(
            HandleFoodEntryCorrectedCommand(
                event_id=event_id,
                entry_id=uuid.UUID(payload["entry_id"]),
                user_id=uuid.UUID(payload["user_id"]),
                summary=_food_entry_summary(payload),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        )
    elif event_type == "FoodEntryDeleted":
        await HandleFoodEntryDeletedHandler(processed_events, diary_history).handle(
            HandleFoodEntryDeletedCommand(
                event_id=event_id, entry_id=uuid.UUID(payload["entry_id"])
            )
        )
    elif event_type == "WaterIntakeLogged":
        await HandleWaterIntakeLoggedHandler(processed_events, diary_history).handle(
            HandleWaterIntakeLoggedCommand(
                event_id=event_id,
                intake_id=uuid.UUID(payload["intake_id"]),
                user_id=uuid.UUID(payload["user_id"]),
                summary=_water_intake_summary(payload),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        )
    else:  # WaterIntakeRemoved
        await HandleWaterIntakeRemovedHandler(processed_events, diary_history).handle(
            HandleWaterIntakeRemovedCommand(
                event_id=event_id, intake_id=uuid.UUID(payload["intake_id"])
            )
        )


class DiaryEventsConsumer(ResilientTopicConsumer):
    exchange_name = EXCHANGE_NAME
    binding_routing_key = BINDING_ROUTING_KEY
    queue_name = QUEUE_NAME
    dlq_name = DLQ_NAME
    retry_header = RETRY_HEADER
    processing_failed_log_event = "diary_event_processing_failed"
    dead_lettered_log_event = "diary_event_dead_lettered"

    async def dispatch(
        self,
        session: AsyncSession,
        event_type: str,
        event_id: uuid.UUID,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        await dispatch_diary_event(session, event_type, event_id, payload, metadata)
