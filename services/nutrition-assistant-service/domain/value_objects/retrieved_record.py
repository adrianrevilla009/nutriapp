"""RetrievedRecord -- one piece of grounding context assembled into a chat
prompt, either a structured record (diary/nutrition/analytics, read
directly from this service's own Postgres projections) or an unstructured
knowledge-base snippet (from Qdrant). `source` is required precisely so a
prompt/audit consumer can always distinguish "your data" from "general
guidance" at the type level (rag-conventions SKILL.md's grounding rule),
never by string-sniffing the `content` field."""

from __future__ import annotations

from dataclasses import dataclass

VALID_SOURCES = frozenset({"diary", "nutrition", "analytics", "knowledge_base"})


class InvalidRetrievedRecordError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RetrievedRecord:
    record_id: str
    source: str
    content: str

    def __post_init__(self) -> None:
        if self.source not in VALID_SOURCES:
            raise InvalidRetrievedRecordError(
                f"RetrievedRecord.source must be one of {sorted(VALID_SOURCES)}, "
                f"got {self.source!r}."
            )
        if not self.record_id:
            raise InvalidRetrievedRecordError("RetrievedRecord.record_id must not be empty.")
        if not self.content or not self.content.strip():
            raise InvalidRetrievedRecordError("RetrievedRecord.content must not be empty.")

    @property
    def is_user_specific(self) -> bool:
        """True for the requesting user's own structured history sources,
        False for the (never per-user) knowledge-base collection -- used by
        prompt_assembler.py to route into the correct labeled section."""
        return self.source != "knowledge_base"
