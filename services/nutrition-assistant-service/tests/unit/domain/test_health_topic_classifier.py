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


class TestNamedMedicalConditionsCoverage:
    """Closes the 2026-09-12 security-review gap item 1: named medical
    conditions used by name (diabetes, thyroid, PCOS, IBS, celiac,
    hypertension/blood pressure, cholesterol) had zero coverage --
    previously only the generic words disease/disorder/anemi[ac] were
    hardcoded, so any other condition name bypassed the filter entirely."""

    def test_diabetes_question_is_flagged(self) -> None:
        assert is_health_adjacent("what should a diabetic eat for breakfast") is True

    def test_thyroid_question_is_flagged(self) -> None:
        assert is_health_adjacent("does this affect my thyroid") is True

    def test_pcos_question_is_flagged(self) -> None:
        assert is_health_adjacent("what foods help with PCOS") is True

    def test_ibs_question_is_flagged(self) -> None:
        assert is_health_adjacent("is this okay for someone with IBS") is True

    def test_celiac_question_is_flagged(self) -> None:
        assert is_health_adjacent("is oatmeal safe if I have celiac") is True

    def test_hypertension_question_is_flagged(self) -> None:
        assert is_health_adjacent("what should I eat if I have hypertension") is True

    def test_blood_pressure_question_is_flagged(self) -> None:
        assert is_health_adjacent("does sodium affect blood pressure") is True

    def test_cholesterol_question_is_flagged(self) -> None:
        assert is_health_adjacent("will this raise my cholesterol") is True


class TestGeneralSafetyAdjectiveParityCoverage:
    """Closes the 2026-09-12 security-review gap item 2: pattern 8's
    general-case adjective list (dangerous|serious|normal|healthy|unhealthy)
    deliberately omitted safe/unsafe, so a general safety question like
    "is keto safe for someone with diabetes" wasn't flagged by that
    pattern -- only the pregnancy/infant/toddler carve-out covered
    safe(ty) at all, and only for that narrow population case."""

    def test_is_keto_safe_for_someone_with_diabetes_is_flagged(self) -> None:
        # Named verbatim in the security review.
        assert is_health_adjacent("is keto safe for someone with diabetes") is True

    def test_is_this_diet_safe_form_is_flagged(self) -> None:
        assert is_health_adjacent("is this diet safe") is True

    def test_is_intermittent_fasting_safe_to_try_is_flagged(self) -> None:
        assert is_health_adjacent("is intermittent fasting safe to try") is True

    def test_is_it_unsafe_form_is_flagged(self) -> None:
        assert is_health_adjacent("is it unsafe if I do this every day") is True

    def test_ordinary_is_this_a_good_recipe_is_not_flagged(self) -> None:
        # Calibration control -- "good"/"tasty" are not in the safety
        # adjective list and must not be swept up.
        assert is_health_adjacent("is this a good recipe for dinner") is False


class TestPlainSymptomPhrasingCoverage:
    """Closes the 2026-09-12 security-review gap item 3: plain symptom
    phrasing (dizzy, headache, fatigue/tired, palpitations) combined with
    "why"/"should I"/"worried" framing, without the literal word
    "symptom" or any of the existing causal-framing patterns."""

    def test_why_do_i_keep_getting_headaches_is_flagged(self) -> None:
        assert is_health_adjacent("why do I keep getting headaches") is True

    def test_dizzy_should_i_be_worried_is_flagged(self) -> None:
        assert is_health_adjacent("I've been so dizzy lately, should I be worried") is True

    def test_why_am_i_so_tired_is_flagged(self) -> None:
        assert is_health_adjacent("why am I so tired all the time") is True

    def test_fatigue_worried_is_flagged(self) -> None:
        assert is_health_adjacent("I have constant fatigue and I'm worried about it") is True

    def test_should_i_be_worried_about_palpitations_is_flagged(self) -> None:
        assert is_health_adjacent("should I be worried about these heart palpitations") is True

    def test_plain_headache_statement_without_framing_is_not_flagged(self) -> None:
        # Calibration control: a bare symptom mention with no
        # why/should-I/worried framing stays outside this narrow fix,
        # consistent with TestKnownPrecisionRecallGap's documented
        # limits -- this pass closes the framed cases, not every mention.
        assert is_health_adjacent("I have a headache today") is False


class TestSupplementByVitaminOrMineralNameCoverage:
    """Closes the 2026-09-12 security-review gap item 4: supplement
    questions phrased by vitamin/mineral name rather than the literal
    word "supplement" (e.g. "should I start taking iron pills") slipped
    through the existing `\\bshould\\s+i\\s+take\\b.*\\bsupplement`
    pattern entirely."""

    def test_should_i_start_taking_iron_pills_is_flagged(self) -> None:
        # Named verbatim in the security review.
        assert is_health_adjacent("should I start taking iron pills") is True

    def test_should_i_take_magnesium_is_flagged(self) -> None:
        assert is_health_adjacent("should I take magnesium before bed") is True

    def test_should_i_take_vitamin_d_is_flagged(self) -> None:
        assert is_health_adjacent("should I take vitamin D in the winter") is True

    def test_do_i_need_more_calcium_is_flagged(self) -> None:
        assert is_health_adjacent("do I need more calcium") is True

    def test_do_i_need_extra_zinc_is_flagged(self) -> None:
        assert is_health_adjacent("do I need extra zinc") is True

    def test_iron_rich_foods_question_is_not_flagged(self) -> None:
        # Calibration control -- an ordinary catalog/logging-style
        # question naming a mineral without "should I take"/"do I need"
        # framing must not be swept up.
        assert is_health_adjacent("what are some iron-rich foods for dinner") is False


class TestMoodMentalHealthAdjacentCoverage:
    """Closes the 2026-09-12 security-review gap item 5: a new mood/
    mental-health-adjacent nutrition carve-out, mirroring the existing
    pregnancy carve-out's shape -- bare keywords for terms that are
    rarely ambiguous in a nutrition-logging context (anxiety, depression,
    mental health), and a scoped combo for the genuinely ambiguous term
    "mood" (only flagged alongside food/diet/eating/nutrition wording)."""

    def test_anxiety_question_is_flagged(self) -> None:
        assert is_health_adjacent("can certain foods help with my anxiety") is True

    def test_depression_question_is_flagged(self) -> None:
        assert is_health_adjacent("is there a link between diet and depression") is True

    def test_mental_health_question_is_flagged(self) -> None:
        assert is_health_adjacent("how does nutrition affect mental health") is True

    def test_diet_affects_mood_question_is_flagged(self) -> None:
        assert is_health_adjacent("does my diet affect my mood") is True

    def test_stressed_eating_question_is_flagged(self) -> None:
        assert (
            is_health_adjacent("I've been stressed and eating a lot more, is that normal") is True
        )

    def test_mood_boosting_recipe_request_is_not_flagged(self) -> None:
        # Calibration control -- "mood" alone, without any food/diet/
        # eating/nutrition wording nearby, is an ordinary recipe request
        # (mirrors the pregnancy carve-out's "toddler recipe" control).
        assert is_health_adjacent("give me a mood-boosting recipe") is False
