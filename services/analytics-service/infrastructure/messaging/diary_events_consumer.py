"""DiaryEventsConsumer -- subscribes to diary-service's `diary.events`
topic exchange (binding `diary.#`, forward-compatible with any future
diary event type this service doesn't yet handle -- unhandled types are
acknowledged and ignored, same convention `billing_events_consumer.py`
uses) and dispatches `FoodEntryLogged`/`FoodEntryCorrected`/
`FoodEntryDeleted`/`WaterIntakeLogged`/`WaterIntakeRemoved` to their
command handlers. Idempotent by `event_id` via
`ProcessedDiaryEventsRepositoryPort` -- ONE ledger shared across all five
diary event types (they're all diary-service's own events, one logical
upstream), unlike the per-producer split across the four consumers."""

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
from infrastructure.persistence.postgres_daily_log_summary_repository import (
    PostgresDailyLogSummaryRepository,
)
from infrastructure.persistence.postgres_processed_diary_events_repository import (
    PostgresProcessedDiaryEventsRepository,
)

EXCHANGE_NAME = "diary.events"
BINDING_ROUTING_KEY = "diary.#"
QUEUE_NAME = "analytics-service.diary_events"
DLQ_NAME = "analytics-service.diary_events.dlq"
RETRY_HEADER = "x-analytics-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset(
    {
        "FoodEntryLogged",
        "FoodEntryCorrected",
        "FoodEntryDeleted",
        "WaterIntakeLogged",
        "WaterIntakeRemoved",
    }
)


def _macros_per_unit(payload: dict[str, Any]) -> dict[str, float]:
    # `payload` is a decoded JSON dict typed as dict[str, Any] -- indexing
    # into it is necessarily Any-typed to mypy, but the actual shape here
    # is guaranteed by FoodEntryLogged/FoodEntryCorrected's documented
    # schema (docs/events-catalog.md), verified independently by the
    # payload-shape contract tests in tests/contract/events/. Genuine
    # false positive, not a suppressed real finding.
    return payload["source"]["snapshot"]["macros_per_unit"]  # type: ignore[no-any-return]


async def dispatch_diary_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresProcessedDiaryEventsRepository(session)
    daily_log_summary = PostgresDailyLogSummaryRepository(session)

    if event_type == "FoodEntryLogged":
        macros = _macros_per_unit(payload)
        snapshot = payload["source"]["snapshot"]
        await HandleFoodEntryLoggedHandler(processed_events, daily_log_summary).handle(
            HandleFoodEntryLoggedCommand(
                event_id=event_id,
                entry_id=uuid.UUID(payload["entry_id"]),
                user_id=uuid.UUID(payload["user_id"]),
                quantity=float(snapshot["quantity"]),
                calories_kcal_per_unit=float(macros["calories_kcal"]),
                protein_g_per_unit=float(macros["protein_g"]),
                carbs_g_per_unit=float(macros["carbs_g"]),
                fat_g_per_unit=float(macros["fat_g"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        )
    elif event_type == "FoodEntryCorrected":
        macros = _macros_per_unit(payload)
        snapshot = payload["source"]["snapshot"]
        await HandleFoodEntryCorrectedHandler(processed_events, daily_log_summary).handle(
            HandleFoodEntryCorrectedCommand(
                event_id=event_id,
                entry_id=uuid.UUID(payload["entry_id"]),
                user_id=uuid.UUID(payload["user_id"]),
                quantity=float(snapshot["quantity"]),
                calories_kcal_per_unit=float(macros["calories_kcal"]),
                protein_g_per_unit=float(macros["protein_g"]),
                carbs_g_per_unit=float(macros["carbs_g"]),
                fat_g_per_unit=float(macros["fat_g"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        )
    elif event_type == "FoodEntryDeleted":
        await HandleFoodEntryDeletedHandler(processed_events, daily_log_summary).handle(
            HandleFoodEntryDeletedCommand(
                event_id=event_id, entry_id=uuid.UUID(payload["entry_id"])
            )
        )
    elif event_type == "WaterIntakeLogged":
        await HandleWaterIntakeLoggedHandler(processed_events, daily_log_summary).handle(
            HandleWaterIntakeLoggedCommand(
                event_id=event_id,
                intake_id=uuid.UUID(payload["intake_id"]),
                user_id=uuid.UUID(payload["user_id"]),
                amount_ml=float(payload["amount_ml"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        )
    else:  # WaterIntakeRemoved
        await HandleWaterIntakeRemovedHandler(processed_events, daily_log_summary).handle(
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
