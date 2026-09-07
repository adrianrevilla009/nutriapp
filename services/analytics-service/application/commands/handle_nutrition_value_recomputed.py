"""HandleNutritionValueRecomputedHandler -- projects `NutritionValueRecomputed`
(nutrition-calculation-service, `scope == "day"` only -- `scope == "entry"`
events are ignored, this service tracks daily totals, not per-entry
micro-detail) into `micronutrient_window` for each tracked nutrient
(`domain.tracked_nutrients.TRACKED_NUTRIENTS`), then evaluates a
sustained-deficiency breach via `application.detect_nutrient_deficiency`.

Idempotent by `event_id`: a redelivered event must not double-upsert a
`micronutrient_window` row nor double-evaluate/double-publish a
deficiency signal."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from application.detect_nutrient_deficiency import detect_and_record_deficiency
from domain.ports.anomaly_alerts_repository_port import AnomalyAlertsRepositoryPort
from domain.ports.micronutrient_window_repository_port import MicronutrientWindowRepositoryPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.processed_nutrition_calculation_events_repository_port import (
    ProcessedNutritionCalculationEventsRepositoryPort,
)
from domain.tracked_nutrients import TRACKED_NUTRIENTS

EVALUATION_LOOKBACK_DAYS = 7


@dataclass(frozen=True, slots=True)
class HandleNutritionValueRecomputedCommand:
    event_id: uuid.UUID
    user_id: uuid.UUID
    scope: str
    on_date: date | None
    macros: dict[str, float]
    occurred_at: datetime
    correlation_id: str


class HandleNutritionValueRecomputedHandler:
    def __init__(
        self,
        processed_events: ProcessedNutritionCalculationEventsRepositoryPort,
        micronutrient_window: MicronutrientWindowRepositoryPort,
        anomaly_alerts: AnomalyAlertsRepositoryPort,
        outbox: OutboxRepositoryPort,
    ) -> None:
        self._processed_events = processed_events
        self._micronutrient_window = micronutrient_window
        self._anomaly_alerts = anomaly_alerts
        self._outbox = outbox

    async def handle(self, command: HandleNutritionValueRecomputedCommand) -> None:
        if await self._processed_events.is_processed(command.event_id):
            return

        if command.scope == "day" and command.on_date is not None:
            for nutrient in TRACKED_NUTRIENTS:
                value = command.macros.get(nutrient)
                if value is None:
                    continue

                target_min = await self._micronutrient_window.get_current_target_min(
                    command.user_id, nutrient
                )
                await self._micronutrient_window.upsert(
                    command.user_id, nutrient, command.on_date, value, target_min
                )

                recent_points = await self._micronutrient_window.list_recent(
                    command.user_id, nutrient, EVALUATION_LOOKBACK_DAYS
                )
                await detect_and_record_deficiency(
                    user_id=command.user_id,
                    nutrient=nutrient,
                    recent_points=recent_points,
                    target_min=target_min,
                    anomaly_alerts=self._anomaly_alerts,
                    outbox=self._outbox,
                    correlation_id=command.correlation_id,
                    now_fn=lambda: command.occurred_at,
                )

        await self._processed_events.mark_processed(command.event_id)
