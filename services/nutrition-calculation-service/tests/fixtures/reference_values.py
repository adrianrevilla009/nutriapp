"""Published Mifflin-St Jeor worked examples, used by test_bmr_calculator.py
(domain-calculation-conventions SKILL.md: "test against known reference
values"). 70kg/175cm/25y is a commonly cited textbook worked example.

Male:   (10*70) + (6.25*175) - (5*25) + 5   = 700 + 1093.75 - 125 + 5   = 1673.75
Female: (10*65) + (6.25*165) - (5*30) - 161 = 650 + 1031.25 - 150 - 161 = 1370.25
"""

from __future__ import annotations

MALE_WORKED_EXAMPLE = {
    "weight_kg": 70.0,
    "height_cm": 175.0,
    "age": 25,
    "expected_bmr_kcal": 1673.75,
}

FEMALE_WORKED_EXAMPLE = {
    "weight_kg": 65.0,
    "height_cm": 165.0,
    "age": 30,
    "expected_bmr_kcal": 1370.25,
}
