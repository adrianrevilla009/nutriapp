"""Application-layer error types."""

from __future__ import annotations


class FoodEntryNotFoundError(Exception):
    """Raised when a command/query targets a food entry_id with no stream yet."""


class WaterIntakeEntryNotFoundError(Exception):
    """Raised when a command/query targets an intake_id with no stream yet."""


class MealPlanEntryNotFoundError(Exception):
    """Raised when a command/query targets a plan_entry_id with no stream yet."""


class FoodEntryAccessDeniedError(Exception):
    """Raised when a command/query targets a food entry_id owned by another user."""


class WaterIntakeAccessDeniedError(Exception):
    """Raised when a command/query targets an intake_id owned by another user."""


class MealPlanAccessDeniedError(Exception):
    """Raised when a command/query targets a plan_entry_id owned by another user."""
