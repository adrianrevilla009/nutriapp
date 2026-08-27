"""PostgresPhotoAnalysisRepository -- implements PhotoAnalysisRepositoryPort.
Append-only writes only (implementation plan section 4: "no update/delete
use case exists")."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.photo_analysis import PhotoAnalysis
from domain.value_objects.confidence_score import ConfidenceScore
from domain.value_objects.food_candidate import FoodCandidate
from domain.value_objects.portion_range_grams import PortionRangeGrams
from infrastructure.persistence.models import PhotoAnalysisModel


def _candidate_to_dict(candidate: FoodCandidate) -> dict[str, object]:
    return {
        "name": candidate.name,
        "portion_range_min_g": candidate.portion_range.min_g,
        "portion_range_max_g": candidate.portion_range.max_g,
        "confidence": candidate.confidence.value,
    }


def _candidate_from_dict(raw: dict[str, object]) -> FoodCandidate:
    return FoodCandidate(
        name=str(raw["name"]),
        portion_range=PortionRangeGrams(
            min_g=float(raw["portion_range_min_g"]),  # type: ignore[arg-type]
            max_g=float(raw["portion_range_max_g"]),  # type: ignore[arg-type]
        ),
        confidence=ConfidenceScore(float(raw["confidence"])),  # type: ignore[arg-type]
    )


class PostgresPhotoAnalysisRepository:
    """Implements domain.ports.photo_analysis_repository_port.PhotoAnalysisRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, analysis: PhotoAnalysis) -> None:
        row = PhotoAnalysisModel(
            analysis_id=analysis.analysis_id,
            user_id=analysis.user_id,
            submitted_at=analysis.submitted_at,
            candidates=[_candidate_to_dict(c) for c in analysis.candidates],
            model_version=analysis.model_version,
            status=analysis.status,
            correlation_id=analysis.correlation_id,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_by_id(self, analysis_id: object) -> PhotoAnalysis | None:
        row = await self._session.get(PhotoAnalysisModel, analysis_id)
        if row is None:
            return None
        return PhotoAnalysis(
            analysis_id=row.analysis_id,
            user_id=row.user_id,
            submitted_at=row.submitted_at,
            candidates=[_candidate_from_dict(c) for c in row.candidates],
            model_version=row.model_version,
            status=row.status,  # type: ignore[arg-type]
            correlation_id=row.correlation_id,
        )
