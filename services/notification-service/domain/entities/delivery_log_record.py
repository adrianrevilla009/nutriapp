"""DeliveryLogRecord -- one row per send attempt (docs/notifications.md
section 4), append-only audit/debugging record."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.delivery_status import DeliveryStatus
from domain.value_objects.notification_category import Channel
from domain.value_objects.template_id import TemplateId


@dataclass(frozen=True, slots=True)
class DeliveryLogRecord:
    delivery_id: uuid.UUID
    user_id: uuid.UUID
    channel: Channel
    template_id: TemplateId
    status: DeliveryStatus
    attempted_at: datetime
    failure_reason: str | None = None
