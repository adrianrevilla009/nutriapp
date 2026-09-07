"""RetrievalGap -- a structured statement of what was NOT available for a
given chat response, surfaced to the user per rag-conventions SKILL.md's
"if there isn't enough indexed context, say so explicitly" rule and
implementation-plan acceptance criterion 4. Distinct from
GroundedContext.has_sufficient_context (a boolean judgement) -- this is
the human-readable explanation of *why*."""

from __future__ import annotations

from dataclasses import dataclass

INSUFFICIENT_CONTEXT_MESSAGE = (
    "There isn't enough of your history indexed yet to answer this well. "
    "I don't want to guess, so please log a bit more data or ask again once "
    "more of your history is available."
)

KNOWLEDGE_BASE_UNAVAILABLE_MESSAGE = (
    "General nutrition guidance lookup was temporarily unavailable for this "
    "response, so this answer is based only on your own logged data."
)


@dataclass(frozen=True, slots=True)
class RetrievalGap:
    insufficient_user_data: bool
    knowledge_base_unavailable: bool

    @property
    def has_gap(self) -> bool:
        return self.insufficient_user_data or self.knowledge_base_unavailable

    def describe(self) -> str:
        parts: list[str] = []
        if self.insufficient_user_data:
            parts.append(INSUFFICIENT_CONTEXT_MESSAGE)
        if self.knowledge_base_unavailable:
            parts.append(KNOWLEDGE_BASE_UNAVAILABLE_MESSAGE)
        return " ".join(parts)
