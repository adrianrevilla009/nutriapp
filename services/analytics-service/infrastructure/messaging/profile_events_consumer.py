"""ProfileEventsConsumer -- subscribes to profile-service's `profile.events`
topic exchange (binding `profile.#`) and dispatches `WeightRecorded` to
its command handler. `BiometricConsentGranted`/`BodyMetricRecorded`/
`GoalSet`/`GoalUpdated` are acknowledged and ignored this pass
(implementation plan section 1's deferred scope) -- forward-compatible,
same convention as the other three consumers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.handle_weight_recorded import (
    HandleWeightRecordedCommand,
    HandleWeightRecordedHandler,
)
from infrastructure.messaging.resilient_topic_consumer import ResilientTopicConsumer
from infrastructure.persistence.postgres_processed_profile_events_repository import (
    PostgresProcessedProfileEventsRepository,
)
from infrastructure.persistence.postgres_weight_trend_repository import (
    PostgresWeightTrendRepository,
)

EXCHANGE_NAME = "profile.events"
BINDING_ROUTING_KEY = "profile.#"
QUEUE_NAME = "analytics-service.profile_events"
DLQ_NAME = "analytics-service.profile_events.dlq"
RETRY_HEADER = "x-analytics-service-retry-count"

_HANDLED_EVENT_TYPES = frozenset({"WeightRecorded"})


async def dispatch_profile_event(
    session: AsyncSession,
    event_type: str,
    event_id: uuid.UUID,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in _HANDLED_EVENT_TYPES:
        return

    processed_events = PostgresProcessedProfileEventsRepository(session)
    weight_trend = PostgresWeightTrendRepository(session)

    await HandleWeightRecordedHandler(processed_events, weight_trend).handle(
        HandleWeightRecordedCommand(
            event_id=event_id,
            user_id=uuid.UUID(payload["user_id"]),
            weight_kg_ciphertext=payload["weight_kg"],
            recorded_at=datetime.fromisoformat(payload["recorded_at"]),
        )
    )


class ProfileEventsConsumer(ResilientTopicConsumer):
    exchange_name = EXCHANGE_NAME
    binding_routing_key = BINDING_ROUTING_KEY
    queue_name = QUEUE_NAME
    dlq_name = DLQ_NAME
    retry_header = RETRY_HEADER
    processing_failed_log_event = "profile_event_processing_failed"
    dead_lettered_log_event = "profile_event_dead_lettered"

    async def dispatch(
        self,
        session: AsyncSession,
        event_type: str,
        event_id: uuid.UUID,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        await dispatch_profile_event(session, event_type, event_id, payload, metadata)
