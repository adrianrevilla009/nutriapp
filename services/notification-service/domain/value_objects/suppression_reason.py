"""SuppressionReason -- why an address/device was added to the permanent
suppression list (docs/notifications.md section 4). Re-addition to the
allowed set always requires new, explicit consent -- never automatic
(CLAUDE.md rules)."""

from __future__ import annotations

from enum import Enum


class SuppressionReason(str, Enum):
    HARD_BOUNCE = "hard_bounce"
    UNSUBSCRIBE = "unsubscribe"
