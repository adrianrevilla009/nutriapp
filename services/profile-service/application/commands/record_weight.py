"""RecordWeightCommand + handler."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from application.dto.event_crypto import decrypt_event_stream, encrypt_event_payload
from application.errors import ProfileNotFoundError
from domain.entities.profile import Profile
from domain.ports.data_encryption_port import DataEncryptionPort
from domain.ports.evolution_projector_port import EvolutionProjectorPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.profile_event_store_port import ProfileEventStorePort
from domain.ports.snapshot_projector_port import SnapshotProjectorPort
from domain.value_objects.weight_kg import WeightKg


@dataclass(frozen=True, slots=True)
class RecordWeightCommand:
    user_id: uuid.UUID
    weight_kg: float
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RecordWeightResult:
    weight_kg: float


class RecordWeightHandler:
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

    async def handle(self, command: RecordWeightCommand) -> RecordWeightResult:
        events = await self._event_store.load(command.user_id)
        if not events:
            raise ProfileNotFoundError("No profile exists yet for this user_id.")
        plaintext_events = await decrypt_event_stream(events, self._encryption, command.user_id)
        profile = Profile.rebuild(plaintext_events)

        event = profile.record_weight(
            WeightKg(command.weight_kg),
            recorded_at=self._now_fn(),
            correlation_id=command.correlation_id,
        )
        encrypted_event = await encrypt_event_payload(event, self._encryption, command.user_id)
        await self._event_store.append(encrypted_event)
        await self._outbox.enqueue(encrypted_event)
        await self._snapshot_projector.apply(encrypted_event)
        await self._evolution_projector.apply(encrypted_event)
        return RecordWeightResult(weight_kg=command.weight_kg)
