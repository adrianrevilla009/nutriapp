from __future__ import annotations

from typing import Protocol

from domain.entities.photo_analysis import PhotoAnalysis


class PhotoAnalysisRepositoryPort(Protocol):
    async def save(self, analysis: PhotoAnalysis) -> None: ...
