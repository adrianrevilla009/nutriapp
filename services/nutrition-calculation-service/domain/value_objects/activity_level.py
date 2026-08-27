"""ActivityLevel -- own copy of profile-service's activity-level vocabulary
(implementation plan section 3): this service's TDEE calculation depends
on the exact 5-tier taxonomy, so it is a first-class local value object
rather than a bare string threaded through from an event payload.
"""

from __future__ import annotations

from enum import Enum


class ActivityLevel(str, Enum):
    SEDENTARY = "SEDENTARY"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    ACTIVE = "ACTIVE"
    VERY_ACTIVE = "VERY_ACTIVE"
