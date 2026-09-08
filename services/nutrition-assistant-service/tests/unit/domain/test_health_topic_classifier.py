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


class TestIndirectCausalPhrasingCoverage:
    """Closes the 2026-09-08 security-review gap: symptom/deficiency-
    adjacent causal questions phrased without the literal string
    "caused by" slipped through the original `\\bcaused?\\s+by\\b`-style
    rule entirely. These probes use "could X be why" / "is X the
    reason/problem/cause" framing instead."""

    def test_could_low_iron_be_why_tired_is_flagged(self) -> None:
        # Named verbatim in the security review as an unflagged
        # deficiency-adjacent question.
        assert is_health_adjacent("could low iron be why I'm so tired") is True

    def test_is_my_diet_the_problem_for_hair_loss_is_flagged(self) -> None:
        # Named verbatim in the security review.
        assert (
            is_health_adjacent("my hair has been falling out lately, is my diet the problem")
            is True
        )

    def test_could_x_be_why_generic_form_is_flagged(self) -> None:
        assert is_health_adjacent("could this be why I keep getting headaches") is True

    def test_is_that_the_reason_form_is_flagged(self) -> None:
        assert is_health_adjacent("is that the reason I feel so weak lately") is True


class TestPregnancyBreastfeedingInfantCoverage:
    """Closes the 2026-09-08 security-review gap: zero pattern coverage
    existed for pregnancy/breastfeeding/infant-nutrition questions, a
    distinct health-adjacent, population-specific-advice case."""

    def test_what_should_i_eat_while_pregnant_is_flagged(self) -> None:
        # Named verbatim in the security review.
        assert is_health_adjacent("what should I eat while pregnant") is True

    def test_is_this_safe_for_my_baby_is_flagged(self) -> None:
        # Named verbatim in the security review.
        assert is_health_adjacent("is this safe for my baby") is True

    def test_breastfeeding_question_is_flagged(self) -> None:
        assert is_health_adjacent("can I eat sushi while breastfeeding") is True

    def test_nursing_question_is_flagged(self) -> None:
        assert is_health_adjacent("how many calories do I need while nursing") is True

    def test_infant_nutrition_question_is_flagged(self) -> None:
        assert is_health_adjacent("what nutrients does an infant need") is True

    def test_toddler_feeding_safety_question_is_flagged(self) -> None:
        assert is_health_adjacent("is it safe to feed a toddler this much sugar") is True

    def test_toddler_recipe_request_is_not_flagged(self) -> None:
        # Deliberately NOT flagged -- "recipe for toddlers" is an
        # ordinary catalog/recipe-adjacent question, not a health/safety
        # question, per the security review's own carve-out.
        assert is_health_adjacent("give me a recipe for toddlers") is False


class TestRestrictiveEatingWithoutDisorderWordCoverage:
    """Closes the 2026-09-08 security-review gap: restrictive-eating
    language directly adjacent to the eating-disorder boundary CLAUDE.md
    section 8 calls out by name, phrased without the word "disorder",
    was unflagged. Calibrated (see comments in the classifier module) to
    avoid over-triggering on ordinary single-day logging statements like
    "I skipped breakfast today"."""

    def test_skipping_meals_and_barely_eating_is_flagged(self) -> None:
        # Named verbatim in the security review.
        assert (
            is_health_adjacent("I've been skipping meals and barely eating, is that okay") is True
        )

    def test_not_eating_enough_is_flagged(self) -> None:
        assert is_health_adjacent("I feel like I'm not eating enough lately") is True

    def test_afraid_to_eat_is_flagged(self) -> None:
        assert is_health_adjacent("I've been afraid to eat in front of others") is True

    def test_ordinary_single_day_skip_logging_is_not_flagged(self) -> None:
        # Calibration control: ordinary logging-adjacent phrasing about
        # a single missed meal must NOT be swept up by the
        # restrictive-eating patterns above.
        assert is_health_adjacent("I skipped breakfast today") is False
