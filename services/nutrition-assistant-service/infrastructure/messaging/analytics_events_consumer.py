"""AnalyticsEventsConsumer -- subscribes to analytics-service's
`analytics.events` topic exchange and dispatches NutrientDeficiencyDetected
to its command handler. Idempotent by event_id via
ProcessedAnalyticsEventsRepositoryPort. The event's `disclaimer` field is
passed through unmodified (implementation plan section 5)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_nutrient_deficiency_detected import (
    HandleNutrientDeficiencyDetectedCommand,
    HandleNutrientDeficiencyDetectedHandler,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_analytics_signals_repository import (
    PostgresAnalyticsSignalsRepository,
)
from infrastructure.persistence.postgres_processed_analytics_events_repository import (
    PostgresAnalyticsEventsRepository,
)

EXCHANGE_NAME = "analytics.events"
BINDING_ROUTING_KEY = "analytics.#"
QUEUE_NAME = "nutrition-assistant-service.analytics_events"
DLQ_NAME = "nutrition-assistant-service.analytics_events.dlq"
RETRY_HEADER = "x-nutrition-assistant-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset({"NutrientDeficiencyDetected"})


def _signal_summary(payload: dict[str, Any]) -> str:
    return (
        f"{payload['signal']} below target ({payload['value']} < {payload['target_min']}) "
        f"over the last {payload['window_days']} days "
        f"(sample size: {payload.get('sample_size', 'unknown')} days with data)"
    )


async def dispatch_analytics_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresAnalyticsEventsRepository(session)
    analytics_signals = PostgresAnalyticsSignalsRepository(session)

    await HandleNutrientDeficiencyDetectedHandler(processed_events, analytics_signals).handle(
        HandleNutrientDeficiencyDetectedCommand(
            event_id=event_id,
            user_id=uuid.UUID(payload["user_id"]),
            signal=payload["signal"],
            summary=_signal_summary(payload),
            disclaimer=payload["disclaimer"],
        )
    )


class AnalyticsEventsConsumer(ResilientTopicConsumer):
    exchange_name = EXCHANGE_NAME
    binding_routing_key = BINDING_ROUTING_KEY
    queue_name = QUEUE_NAME
    dlq_name = DLQ_NAME
    retry_header = RETRY_HEADER
    processing_failed_log_event = "analytics_event_processing_failed"
    dead_lettered_log_event = "analytics_event_dead_lettered"

    async def dispatch(
        self,
        session: AsyncSession,
        event_type: str,
        event_id: uuid.UUID,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        await dispatch_analytics_event(session, event_type, event_id, payload, metadata)
