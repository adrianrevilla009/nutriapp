"""SectionStatus -- the one piece of genuine domain state this service
has (implementation plan section 2): a per-section "did this downstream
call succeed" marker, never a computed/business value. Every aggregation
endpoint's response is built entirely out of these, wrapping whatever a
downstream service already computed.

Two documented `unavailable` reasons only (a closed set, not free text,
per test-plan section 1):
  - "downstream_error": the call itself failed (transport error, 5xx,
    open circuit breaker) -- a genuine health signal.
  - "not_yet_computed": the downstream call succeeded and reported, in a
    well-formed way, that nothing exists yet for this user (e.g.
    nutrition-calculation-service's documented `Sex.OTHER`/deferred-
    recompute gap -- see that service's README.md) -- an expected,
    non-exceptional business response, not a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

T = TypeVar("T")

SectionStatusValue = Literal["available", "unavailable"]
UnavailableReason = Literal["downstream_error", "not_yet_computed"]

_VALID_UNAVAILABLE_REASONS: frozenset[str] = frozenset({"downstream_error", "not_yet_computed"})


@dataclass(frozen=True, slots=True)
class SectionStatus(Generic[T]):
    status: SectionStatusValue
    data: T | None
    reason: UnavailableReason | None

    @classmethod
    def available(cls, data: T) -> SectionStatus[T]:
        return cls(status="available", data=data, reason=None)

    @classmethod
    def unavailable(cls, reason: str) -> SectionStatus[T]:
        if reason not in _VALID_UNAVAILABLE_REASONS:
            raise ValueError(
                f"Unrecognized SectionStatus unavailable reason: {reason!r}. "
                f"Must be one of {sorted(_VALID_UNAVAILABLE_REASONS)}."
            )
        return cls(status="unavailable", data=None, reason=reason)  # type: ignore[arg-type]
