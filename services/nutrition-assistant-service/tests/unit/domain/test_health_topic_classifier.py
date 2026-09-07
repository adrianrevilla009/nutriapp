"""Test plan section 1 -- health_topic_classifier.

Per the implementation plan section 9 resolution 4, this rule-based
classifier is a FIRST CUT with real precision/recall limits, not a solved
problem. The ambiguous-phrasing cases below document its actual current
behavior explicitly, rather than asserting an idealized behavior that
doesn't exist -- this is the point of this test file, per the persisted
test plan section 1."""

from __future__ import annotations

import pytest

from domain.services.health_topic_classifier import is_health_adjacent

HEALTH_ADJACENT_PROBES = [
    "am I deficient in iron",
    "is my fatigue caused by low protein",
    "should I take a supplement for this condition",
    "do I have a vitamin D deficiency",
    "is my eating pattern disordered",
]

BENIGN_PROBES = [
    "how many calories did I log yesterday",
    "what is fiber",
    "what did I eat for breakfast",
]


@pytest.mark.parametrize("query", HEALTH_ADJACENT_PROBES)
def test_flags_health_adjacent_probes(query: str) -> None:
    assert is_health_adjacent(query) is True


@pytest.mark.parametrize("query", BENIGN_PROBES)
def test_does_not_flag_benign_probes(query: str) -> None:
    assert is_health_adjacent(query) is False


def test_empty_input_is_false() -> None:
    assert is_health_adjacent("") is False


def test_whitespace_only_input_is_false() -> None:
    assert is_health_adjacent("   ") is False


class TestKnownPrecisionRecallGap:
    """Documents the classifier's ACTUAL current behavior on genuinely
    ambiguous phrasing -- a known limitation, not a claim these are
    correctly handled. Flagged for security-agent/architecture-agent
    review before staging/prod (implementation plan section 9 resolution
    4, test plan 'Flagged for review' section item 1)."""

    def test_vague_tiredness_statement_is_not_flagged(self) -> None:
        # A real health-adjacent question phrased without any of the
        # classifier's keyword patterns ("deficient", "diagnose",
        # "symptom", etc.) slips through unflagged -- a genuine false
        # negative this rule-based first cut does not catch.
        assert is_health_adjacent("I've been really tired lately") is False

    def test_generic_how_am_i_doing_is_not_flagged(self) -> None:
        assert is_health_adjacent("how am I doing") is False
