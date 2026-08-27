"""PhotoAnalysis -- an append-only audit record of one photo-analysis
attempt (implementation plan section 2: conventional persistence,
event-driven CRUD, not event-sourced -- a simple record, no
aggregate/replay behavior). One row is written per analysis request,
success or failure alike, mirroring the `FoodPhotoAnalyzed` event this
service always publishes for it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from domain.value_objects.analysis_status import AnalysisStatus
from domain.value_objects.food_candidate import FoodCandidate


@dataclass(frozen=True, slots=True)
class PhotoAnalysis:
    analysis_id: uuid.UUID
    user_id: uuid.UUID
    submitted_at: datetime
    candidates: list[FoodCandidate]
    model_version: str
    status: AnalysisStatus
    correlation_id: str = field(default="")
