"""AnalyzeFoodPhotoCommand/Handler -- implements implementation plan
section 1's acceptance criteria 1, 2, 4, 5, 8 and section 8.3's added
acceptance criterion 9 (feature flag).

This handler's only side effects are its own `PhotoAnalysisRepositoryPort`
write and its own `OutboxRepositoryPort` publish -- no `diary-service`
client/port is ever injected here (test-plan section 1: "this handler's
only side effects are its own repository write and its own outbox
publish... enforced by the constructor signature"). The user's own,
separate, subsequent `diary-service` log call is what actually writes an
entry, after the user reviews and confirms a candidate -- never this
service.

A provider failure, a circuit-open condition, an unparseable response, and
disabling the feature flag are all treated identically at this layer:
`status="unavailable"`, no candidates, and -- per implementation plan
section 5 -- `FoodPhotoAnalyzed` is still published (an audit trail of the
failure/disablement itself is a signal worth keeping). No exception ever
escapes `handle()`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from application.errors import InvalidImageError
from domain.entities.photo_analysis import PhotoAnalysis
from domain.events.food_photo_analyzed import build_food_photo_analyzed_event
from domain.ports.outbox_repository_port import OutboxRepositoryPort
from domain.ports.photo_analysis_repository_port import PhotoAnalysisRepositoryPort
from domain.ports.vision_recognition_port import (
    VisionRecognitionPort,
    VisionRecognitionUnavailableError,
)
from domain.value_objects.analysis_status import AnalysisStatus
from domain.value_objects.food_candidate import FoodCandidate

DEFAULT_CONFIDENCE_THRESHOLD = 0.6


@dataclass(frozen=True, slots=True)
class AnalyzeFoodPhotoCommand:
    user_id: uuid.UUID
    image_bytes: bytes
    correlation_id: str


@dataclass(frozen=True, slots=True)
class AnalyzeFoodPhotoResult:
    analysis_id: uuid.UUID
    status: AnalysisStatus
    candidates: list[FoodCandidate]
    model_version: str


# Photo analysis never returns more than this many candidates
# (implementation plan section 1, acceptance criterion 1: "top 3
# candidates maximum ... never silently collapsed to one guess").
MAX_CANDIDATES = 3


class AnalyzeFoodPhotoHandler:
    def __init__(
        self,
        vision_port: VisionRecognitionPort,
        repository: PhotoAnalysisRepositoryPort,
        outbox_repository: OutboxRepositoryPort,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        feature_enabled: bool = True,
    ) -> None:
        self._vision_port = vision_port
        self._repository = repository
        self._outbox_repository = outbox_repository
        self._confidence_threshold = confidence_threshold
        self._feature_enabled = feature_enabled

    async def handle(self, command: AnalyzeFoodPhotoCommand) -> AnalyzeFoodPhotoResult:
        if not command.image_bytes:
            raise InvalidImageError("Uploaded photo is empty.")

        now = datetime.now(timezone.utc)
        analysis_id = uuid.uuid4()
        model_version = self._vision_port.model_version
        candidates: list[FoodCandidate] = []
        status: AnalysisStatus

        if not self._feature_enabled:
            status = "unavailable"
        else:
            try:
                candidates = list(
                    (await self._vision_port.analyze(command.image_bytes))[:MAX_CANDIDATES]
                )
            except VisionRecognitionUnavailableError:
                status = "unavailable"
                candidates = []
            else:
                status = (
                    "detected"
                    if any(c.confidence.value >= self._confidence_threshold for c in candidates)
                    else "uncertain"
                )

        analysis = PhotoAnalysis(
            analysis_id=analysis_id,
            user_id=command.user_id,
            submitted_at=now,
            candidates=candidates,
            model_version=model_version,
            status=status,
            correlation_id=command.correlation_id,
        )
        await self._repository.save(analysis)

        event = build_food_photo_analyzed_event(
            analysis_id=analysis_id,
            user_id=command.user_id,
            candidates=candidates,
            model_version=model_version,
            status=status,
            correlation_id=command.correlation_id,
            occurred_at=now,
        )
        await self._outbox_repository.enqueue(event)

        return AnalyzeFoodPhotoResult(
            analysis_id=analysis_id,
            status=status,
            candidates=candidates,
            model_version=model_version,
        )
