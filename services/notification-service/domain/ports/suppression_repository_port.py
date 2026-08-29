"""SuppressionRepositoryPort -- the permanent suppression list
(docs/notifications.md section 4), checked before every non-transactional
send and every soft/hard-bounce webhook. Postgres adapter:
postgres_suppression_repository.py."""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.value_objects.notification_category import Channel
from domain.value_objects.suppression_reason import SuppressionReason


class SuppressionRepositoryPort(Protocol):
    async def is_suppressed(
        self, user_id: uuid.UUID, channel: Channel, address_or_device: str
    ) -> bool: ...

    async def add(
        self,
        user_id: uuid.UUID,
        channel: Channel,
        address_or_device: str,
        reason: SuppressionReason,
    ) -> None: ...
