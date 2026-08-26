"""ConfidenceRange -- reserved seam for food-recognition-service's
AI-estimated confidence range (implementation plan section 1, item 2: "not
built this pass"). Declared now so `NutrientTotalLine`/`NutritionValueRecomputed`
have a stable field shape when the seam is eventually wired; always `None`
in this pass, per domain-calculation-conventions SKILL.md's "carry the
uncertainty through rather than collapsing it to a point value" rule for
when it *is* wired.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceRange:
    min: float
    max: float
