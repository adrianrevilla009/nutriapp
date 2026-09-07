"""NutritionCalculationEventsConsumer -- subscribes to
nutrition-calculation-service's `nutrition-calculation.events` topic
exchange and dispatches NutritionValueRecomputed/NutritionTargetUpdated to
their command handlers. Idempotent by event_id via
ProcessedNutritionCalculationEventsRepositoryPort."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_nutrition_target_updated import (
    HandleNutritionTargetUpdatedCommand,
    HandleNutritionTargetUpdatedHandler,
)
from application.commands.handle_nutrition_value_recomputed import (
    HandleNutritionValueRecomputedCommand,
    HandleNutritionValueRecomputedHandler,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_nutrition_history_repository import (
    PostgresNutritionHistoryRepository,
)
from infrastructure.persistence.postgres_processed_nutrition_calculation_events_repository import (
    PostgresNutritionCalculationEventsRepository,
)

EXCHANGE_NAME = "nutrition-calculation.events"
BINDING_ROUTING_KEY = "nutrition-calculation.#"
QUEUE_NAME = "nutrition-assistant-service.nutrition_calculation_events"
DLQ_NAME = "nutrition-assistant-service.nutrition_calculation_events.dlq"
RETRY_HEADER = "x-nutrition-assistant-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset({"NutritionValueRecomputed", "NutritionTargetUpdated"})


def _value_summary(payload: dict[str, Any]) -> str:
    macros = payload["macros"]
    return (
        f"{macros['calories_kcal']} kcal, {macros['protein_g']}g protein, "
        f"{macros['carbs_g']}g carbs, {macros['fat_g']}g fat "
        f"({payload['scope']} scope, {'estimated' if payload.get('is_estimated') else 'measured'})"
    )


def _target_summary(payload: dict[str, Any]) -> str:
    targets = payload["macro_targets"]
    return (
        f"target: {payload['calorie_target_kcal']} kcal, "
        f"{targets['protein_g_min']}-{targets['protein_g_max']}g protein min-max, "
        f"{targets['fat_g_min']}g fat min, {targets['carbs_g']}g carbs, "
        f"goal={payload['goal_type']}"
    )


async def dispatch_nutrition_calculation_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresNutritionCalculationEventsRepository(session)
    nutrition_history = PostgresNutritionHistoryRepository(session)

    if event_type == "NutritionValueRecomputed":
        on_date_raw = payload.get("date")
        reference_id = payload.get("entry_id") or payload.get("date") or "unknown"
        await HandleNutritionValueRecomputedHandler(processed_events, nutrition_history).handle(
            HandleNutritionValueRecomputedCommand(
                event_id=event_id,
                user_id=uuid.UUID(payload["user_id"]),
                scope=payload["scope"],
                reference_id=str(reference_id),
                on_date=date.fromisoformat(on_date_raw) if on_date_raw else None,
                summary=_value_summary(payload),
            )
        )
    else:  # NutritionTargetUpdated
        await HandleNutritionTargetUpdatedHandler(processed_events, nutrition_history).handle(
            HandleNutritionTargetUpdatedCommand(
                event_id=event_id,
                user_id=uuid.UUID(payload["user_id"]),
                summary=_target_summary(payload),
            )
        )


class NutritionCalculationEventsConsumer(ResilientTopicConsumer):
    exchange_name = EXCHANGE_NAME
    binding_routing_key = BINDING_ROUTING_KEY
    queue_name = QUEUE_NAME
    dlq_name = DLQ_NAME
    retry_header = RETRY_HEADER
    processing_failed_log_event = "nutrition_calculation_event_processing_failed"
    dead_lettered_log_event = "nutrition_calculation_event_dead_lettered"

    async def dispatch(
        self,
        session: AsyncSession,
        event_type: str,
        event_id: uuid.UUID,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        await dispatch_nutrition_calculation_event(session, event_type, event_id, payload, metadata)
