"""RecordBodyMetricCommand + handler.

One generic command for all four metric_type values (implementation plan
section 9.4, kept as-is: simpler, fewer files; per-metric commands can be
split out later if per-metric type safety at the command layer is
preferred instead).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from application.dto.event_crypto import decrypt_event_stream, encrypt_event_payload
from application.errors import ProfileNotFoundError
from domain.entities.profile import Profile, UnsupportedMetricTypeError
from domain.ports.data_encryption_port import DataEncryptionPort
from domain.ports.evolution_projector_port import EvolutionProjectorPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.profile_event_store_port import ProfileEventStorePort
from domain.ports.snapshot_projector_port import SnapshotProjectorPort
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.age import Age
from domain.value_objects.height_cm import HeightCm
from domain.value_objects.sex import Sex


def _cast_input_value(metric_type: str, value: Any) -> Any:
    if metric_type == "height":
        return float(HeightCm(float(value)))
    if metric_type == "age":
        return int(Age(int(value)))
    if metric_type == "sex":
        return Sex.from_value(value).value
    if metric_type == "activity_level":
        return ActivityLevel.from_value(value).value
    raise UnsupportedMetricTypeError(f"Unsupported metric_type: {metric_type!r}")


@dataclass(frozen=True, slots=True)
class RecordBodyMetricCommand:
    user_id: uuid.UUID
    metric_type: str
    value: Any
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RecordBodyMetricResult:
    metric_type: str
    value: Any


class RecordBodyMetricHandler:
    def __init__(
        self,
        event_store: ProfileEventStorePort,
        outbox: OutboxRepositoryPort,
        snapshot_projector: SnapshotProjectorPort,
        evolution_projector: EvolutionProjectorPort,
        encryption: DataEncryptionPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._snapshot_projector = snapshot_projector
        self._evolution_projector = evolution_projector
        self._encryption = encryption
        self._now_fn = now_fn

    async def handle(self, command: RecordBodyMetricCommand) -> RecordBodyMetricResult:
        events = await self._event_store.load(command.user_id)
        if not events:
            raise ProfileNotFoundError("No profile exists yet for this user_id.")
        plaintext_events = await decrypt_event_stream(events, self._encryption, command.user_id)
        profile = Profile.rebuild(plaintext_events)

        casted_value = _cast_input_value(command.metric_type, command.value)
        event = profile.record_body_metric(
            command.metric_type,
            casted_value,
            recorded_at=self._now_fn(),
            correlation_id=command.correlation_id,
        )
        encrypted_event = await encrypt_event_payload(event, self._encryption, command.user_id)
        await self._event_store.append(encrypted_event)
        await self._outbox.enqueue(encrypted_event)
        await self._snapshot_projector.apply(encrypted_event)
        await self._evolution_projector.apply(encrypted_event)
        return RecordBodyMetricResult(metric_type=command.metric_type, value=casted_value)
