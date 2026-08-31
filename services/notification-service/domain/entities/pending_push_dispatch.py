"""PendingPushDispatch -- a one-shot non-transactional push notification
that landed during the recipient's quiet hours and is held for retry at
`earliest_dispatch_at`, instead of being sent immediately or dropped
(docs/notifications.md section 2: "delay non-transactional sends to the
next allowed window -- never drop them silently").

Deliberately distinct from ReminderScheduleEntry: that projection is
periodic (rebuilt from diary events, with a natural "next occurrence" to
retry a delayed send against). A triggering event like `UserFollowed` is
one-shot -- there is no next occurrence to fall back on, so a delayed send
has to be persisted here explicitly and retried by
`PendingPushDispatchScanWorker` until it is due.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.notification_category import NotificationCategory
from domain.value_objects.pending_dispatch_status import PendingDispatchStatus
from domain.value_objects.template_id import TemplateId


@dataclass(slots=True)
class PendingPushDispatch:
    dispatch_id: uuid.UUID
    user_id: uuid.UUID
    category: NotificationCategory
    template_id: TemplateId
    context: dict[str, str]
    correlation_id: str
    earliest_dispatch_at: datetime
    status: PendingDispatchStatus = PendingDispatchStatus.PENDING
