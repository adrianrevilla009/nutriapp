"""ReminderScheduleEntry -- a row in the reminder_schedule projection
(implementation plan section 3). Populated by consuming diary-service
events, scanned periodically by ScanAndSendDueRemindersHandler."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.reminder_status import ReminderStatus


@dataclass(slots=True)
class ReminderScheduleEntry:
    schedule_id: uuid.UUID
    user_id: uuid.UUID
    category: NotificationCategory
    source_aggregate_id: str
    due_at: datetime
    relevance_expires_at: datetime
    status: ReminderStatus = ReminderStatus.PENDING
    next_eligible_check_at: datetime | None = None
