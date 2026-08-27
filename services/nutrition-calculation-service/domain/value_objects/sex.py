"""Sex (biometric input) and CalculationSexConstant (the Mifflin-St Jeor
constant actually applied) -- kept as two distinct types deliberately.

`Sex` is the user's recorded value from profile-service (MALE|FEMALE|OTHER).
`CalculationSexConstant` is which of the two published Mifflin-St Jeor
constants was actually used for a given BMR calculation. For MALE/FEMALE
these always coincide; for OTHER, implementation plan Addendum 1 section
9.8 requires an explicit user selection of one or the other for
calculation purposes only -- never defaulted, never silently discarded
after use (stored alongside the computed target for traceability).
"""

from __future__ import annotations

from enum import Enum


class Sex(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class CalculationSexConstant(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
