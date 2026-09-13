"""NutritionCalculationEventsConsumer -- subscribes to
nutrition-calculation-service's `nutrition-calculation.events` topic
exchange (binding `nutrition-calculation.#`) and dispatches
`NutritionValueRecomputed`/`NutritionTargetUpdated` to their command
handlers. Idempotent by `event_id`, one shared ledger for both event
types (same upstream producer)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
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
from domain.tracked_nutrients import TRACKED_NUTRIENTS
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_anomaly_alerts_repository import (
    PostgresAnomalyAlertsRepository,
)
from infrastructure.persistence.postgres_micronutrient_window_repository import (
    PostgresMicronutrientWindowRepository,
)
from infrastructure.persistence.postgres_outbox_repository import PostgresOutboxRepository
from infrastructure.persistence.postgres_processed_nutrition_calculation_events_repository import (
    PostgresProcessedNutritionCalculationEventsRepository,
)

EXCHANGE_NAME = "nutrition-calculation.events"
BINDING_ROUTING_KEY = "nutrition-calculation.#"
QUEUE_NAME = "analytics-service.nutrition_calculation_events"
DLQ_NAME = "analytics-service.nutrition_calculation_events.dlq"
RETRY_HEADER = "x-analytics-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset({"NutritionValueRecomputed", "NutritionTargetUpdated"})


async def dispatch_nutrition_calculation_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresProcessedNutritionCalculationEventsRepository(session)

    if event_type == "NutritionValueRecomputed":
        micronutrient_window = PostgresMicronutrientWindowRepository(session)
        anomaly_alerts = PostgresAnomalyAlertsRepository(session)
        outbox = PostgresOutboxRepository(session)
        correlation_id = (metadata or {}).get("correlation_id") or str(event_id)

        on_date: date | None = date.fromisoformat(payload["date"]) if payload.get("date") else None
        await HandleNutritionValueRecomputedHandler(
            processed_events, micronutrient_window, anomaly_alerts, outbox
        ).handle(
            HandleNutritionValueRecomputedCommand(
                event_id=event_id,
                user_id=uuid.UUID(payload["user_id"]),
                scope=payload["scope"],
                on_date=on_date,
                macros=payload["macros"],
                occurred_at=datetime.fromisoformat(payload["recomputed_at"]),
                correlation_id=correlation_id,
            )
        )
    else:  # NutritionTargetUpdated
        micronutrient_window = PostgresMicronutrientWindowRepository(session)
        macro_targets = payload.get("macro_targets") or {}
        # `nutrient_targets_min` (added additively, still v1) is the
        # canonical, nutrient-name-keyed minimum-target map -- always
        # carries protein_g/fat_g, and (addendum 2026-09-12) also
        # calcium_mg/iron_mg/vitamin_c_mg when nutrition-calculation-service
        # resolved a real DRI/RDA minimum for this user. It may be entirely
        # absent on an event published before this field existed at all --
        # `macro_targets.protein_g_min`/`fat_g_min` remain the backward-
        # compatible source for those two in that case. The 3 newer keys
        # are NEVER sourced from anywhere else -- a missing entry means
        # "no target published", stored as None, never fabricated.
        nutrient_targets_min = payload.get("nutrient_targets_min") or {}
        target_min_by_nutrient = {
            nutrient: nutrient_targets_min.get(nutrient) for nutrient in TRACKED_NUTRIENTS
        }
        if target_min_by_nutrient.get("protein_g") is None:
            target_min_by_nutrient["protein_g"] = macro_targets.get("protein_g_min")
        if target_min_by_nutrient.get("fat_g") is None:
            target_min_by_nutrient["fat_g"] = macro_targets.get("fat_g_min")

        await HandleNutritionTargetUpdatedHandler(processed_events, micronutrient_window).handle(
            HandleNutritionTargetUpdatedCommand(
                event_id=event_id,
                user_id=uuid.UUID(payload["user_id"]),
                target_min_by_nutrient=target_min_by_nutrient,
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
