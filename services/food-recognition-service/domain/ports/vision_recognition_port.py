"""VisionRecognitionPort -- the hexagonal boundary (ADR-0001) between the
application layer and whatever vision provider is behind it. Concrete
adapter: `infrastructure.external.claude_vision_adapter.ClaudeVisionAdapter`.
The domain/application layers never import the Anthropic SDK or know it
exists -- swapping providers means writing a new adapter, never touching
this contract or any code that depends on it.
"""

from __future__ import annotations

from typing import Protocol

from domain.value_objects.food_candidate import FoodCandidate


class VisionRecognitionUnavailableError(Exception):
    """Raised when the vision provider cannot be reached (circuit open,
    retries exhausted, timeout) or returns an unparseable response. A
    parse failure is treated identically to a total detection failure --
    never a partial/best-effort parse (implementation plan section 4)."""


class VisionRecognitionPort(Protocol):
    @property
    def model_version(self) -> str:
        """The exact provider model string this adapter calls, recorded
        alongside every detection event regardless of outcome
        (media-recognition-conventions SKILL.md's "Model Lifecycle" rule)
        -- known statically, without needing a successful call first."""
        ...

    async def analyze(self, image_bytes: bytes) -> list[FoodCandidate]: ...
