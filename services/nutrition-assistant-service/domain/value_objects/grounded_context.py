"""GroundedContext -- the full retrieval result handed to prompt_assembler.py.

`has_sufficient_context` is a required, non-defaultable field (mirrors
analytics-service's `sample_size`-at-the-type-level precedent) so a caller
is structurally forced to make an explicit judgement rather than silently
falling through to "assume there's enough." Constructing this value object
with zero records still requires the caller to pass `False` explicitly --
there is no default that would let that decision be skipped."""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.value_objects.retrieved_record import RetrievedRecord


@dataclass(frozen=True, slots=True)
class GroundedContext:
    records: tuple[RetrievedRecord, ...]
    has_sufficient_context: bool
    knowledge_base_unavailable: bool = field(default=False)

    @property
    def user_data_records(self) -> tuple[RetrievedRecord, ...]:
        return tuple(r for r in self.records if r.is_user_specific)

    @property
    def general_guidance_records(self) -> tuple[RetrievedRecord, ...]:
        return tuple(r for r in self.records if not r.is_user_specific)
