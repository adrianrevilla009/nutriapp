"""DisclaimerFlag -- the structural (not LLM-trusted) enforcement vehicle
for CLAUDE.md section 8's professional-advice boundary. `required=True`
demands a non-empty disclaimer string at construction time -- the
application layer is structurally prevented from creating a "required but
empty" disclaimer, which would otherwise silently defeat the whole point
of enforcing this outside the LLM's own judgement (implementation plan
section 9 resolution 4)."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_DISCLAIMER_TEXT = (
    "This is not a medical diagnosis. For any question about a possible "
    "nutrient deficiency, symptom, or health condition, please consult a "
    "qualified dietitian or physician."
)


class InvalidDisclaimerFlagError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DisclaimerFlag:
    required: bool
    text: str = DEFAULT_DISCLAIMER_TEXT

    def __post_init__(self) -> None:
        if self.required and not self.text.strip():
            raise InvalidDisclaimerFlagError(
                "DisclaimerFlag.text must not be empty when required=True."
            )
