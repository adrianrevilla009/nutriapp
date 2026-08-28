"""FoodCandidate -- one identified item candidate from a photo analysis.

Never a single collapsed guess: `AnalyzeFoodPhotoHandler` returns up to 3
of these (implementation plan section 1, acceptance criterion 1), each
carrying its own `ConfidenceScore` and a genuine `PortionRangeGrams`
estimate -- never a bare label or a single precise number.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.confidence_score import ConfidenceScore
from domain.value_objects.portion_range_grams import PortionRangeGrams


@dataclass(frozen=True, slots=True)
class FoodCandidate:
    name: str
    portion_range: PortionRangeGrams
    confidence: ConfidenceScore
