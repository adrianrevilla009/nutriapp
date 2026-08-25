"""SetGoalCommand + handler -- create-only; use UpdateGoalCommand for an
existing goal (test-plan assumption, section 1)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone

from application.dto.event_crypto import decrypt_event_stream, encrypt_event_payload
from application.errors import ProfileNotFoundError
from domain.entities.profile import Profile
from domain.ports.data_encryption_port import DataEncryptionPort
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.profile_event_store_port import ProfileEventStorePort
from domain.ports.snapshot_projector_port import SnapshotProjectorPort
from domain.services import goal_policy
from domain.value_objects.goal_target import GoalTarget
from domain.value_objects.goal_type import GoalType


@dataclass(frozen=True, slots=True)
class SetGoalCommand:
    user_id: uuid.UUID
    goal_type: str
    target_value: float | None
    target_date: date | None
    correlation_id: str


@dataclass(frozen=True, slots=True)
class SetGoalResult:
    goal_type: str
    target_value: float | None
    target_date: date | None


class SetGoalHandler:
    def __init__(
        self,
        event_store: ProfileEventStorePort,
        outbox: OutboxRepositoryPort,
        snapshot_projector: SnapshotProjectorPort,
        encryption: DataEncryptionPort,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._event_store = event_store
        self._outbox = outbox
        self._snapshot_projector = snapshot_projector
        self._encryption = encryption
        self._now_fn = now_fn

    async def handle(self, command: SetGoalCommand) -> SetGoalResult:
        events = await self._event_store.load(command.user_id)
        if not events:
            raise ProfileNotFoundError("No profile exists yet for this user_id.")
        plaintext_events = await decrypt_event_stream(events, self._encryption, command.user_id)
        profile = Profile.rebuild(plaintext_events)

        now = self._now_fn()
        goal_type = GoalType.from_value(command.goal_type)
        goal_target = GoalTarget(
            target_value=command.target_value, target_date=command.target_date, now=now
        )
        goal_policy.validate(goal_type, goal_target, latest_weight_kg=profile.weight_kg, now=now)

        event = profile.set_goal(
            goal_type, goal_target, set_at=now, correlation_id=command.correlation_id
        )
        encrypted_event = await encrypt_event_payload(event, self._encryption, command.user_id)
        await self._event_store.append(encrypted_event)
        await self._outbox.enqueue(encrypted_event)
        await self._snapshot_projector.apply(encrypted_event)
        return SetGoalResult(
            goal_type=goal_type.value,
            target_value=command.target_value,
            target_date=command.target_date,
        )
