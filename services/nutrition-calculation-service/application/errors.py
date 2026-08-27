"""Application-layer exceptions -- mapped to HTTP responses in
infrastructure/http/error_mapping.py, per api-conventions SKILL.md."""

from __future__ import annotations


class NutritionTargetNotFoundError(Exception):
    """Raised when a user has no computed nutrition target yet (e.g. no
    profile metrics/goal recorded, or the first recompute hasn't run)."""


class DailyNutritionTotalNotFoundError(Exception):
    """Raised when a user has no computed daily total for the requested
    date (no diary entries logged that day, or not yet recomputed)."""
