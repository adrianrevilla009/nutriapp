"""GoalType -- own copy of profile-service's goal vocabulary (implementation
plan section 3)."""

from __future__ import annotations

from enum import Enum


class GoalType(str, Enum):
    LOSE = "LOSE"
    MAINTAIN = "MAINTAIN"
    GAIN = "GAIN"
