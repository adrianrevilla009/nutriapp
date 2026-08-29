"""TemplateId -- versioned template identifier ("template_id@version",
docs/notifications.md section 3). Never string-built inline content
bypasses this -- every send resolves a TemplateId first.
"""

from __future__ import annotations

from dataclasses import dataclass


class InvalidTemplateVersionError(ValueError):
    """Raised when a template version is not a positive integer."""


@dataclass(frozen=True, slots=True)
class TemplateId:
    name: str
    version: int

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise InvalidTemplateVersionError(
                f"Template version must be a positive int, got {self.version}."
            )

    @property
    def qualified_name(self) -> str:
        return f"{self.name}@{self.version}"
