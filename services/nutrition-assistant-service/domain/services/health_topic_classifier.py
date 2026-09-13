r"""health_topic_classifier -- a PURE, rule-based (keyword/pattern) first
cut for flagging a chat query as health-adjacent, per CLAUDE.md section 8
and rag-conventions SKILL.md's professional-advice boundary.

Deliberately NOT an LLM call: the whole point (implementation plan section
9, resolution 4) is a structural guard that does not depend on the LLM's
own judgement, since the LLM's judgement is exactly what this guard exists
to backstop. This is explicitly flagged in the implementation plan and
test plan as a FIRST CUT with real precision/recall limits, not a solved
problem -- security-agent/architecture-agent review is required before
staging/prod (same posture as analytics-service's deficiency-threshold
sign-off). Do not treat a passing test here as proof the boundary is
airtight; it proves this narrow, enumerable rule set behaves as intended
against the fixed probe set it was written against.

No I/O, no framework import (hexagonal-architecture SKILL.md).

2026-09-08 security review: three concrete false-negative gaps were
found in the original pattern set and closed below (see
`tests/unit/domain/test_health_topic_classifier.py`'s
`TestIndirectCausalPhrasingCoverage`, `TestPregnancyBreastfeedingInfantCoverage`,
and `TestRestrictiveEatingWithoutDisorderWordCoverage` for the exact
probes this was validated against):
1. Indirect causal/symptom phrasing that never used the literal string
   "caused by" (e.g. "could low iron be why I'm so tired") slipped
   through the old `\bcaused?\s+by\b`-style rule entirely.
2. Zero pattern coverage existed for pregnancy/breastfeeding/infant
   nutrition questions -- a distinct health-adjacent,
   population-specific-advice case.
3. Restrictive-eating language adjacent to the eating-disorder boundary
   CLAUDE.md section 8 calls out by name (skipping meals, barely
   eating, not eating enough, afraid to eat) was unflagged whenever it
   avoided the literal word "disorder".
This remains a first-cut, rule-based approximation, not a claim of
completeness -- see `TestKnownPrecisionRecallGap` for cases that still
resist this approach.

2026-09-12 security review (implementation plan addendum, same date):
five further concrete recall gaps were found and closed below (see
`tests/unit/domain/test_health_topic_classifier.py`'s
`TestNamedMedicalConditionsCoverage`, `TestGeneralSafetyAdjectiveParityCoverage`,
`TestPlainSymptomPhrasingCoverage`, `TestSupplementByVitaminOrMineralNameCoverage`,
and `TestMoodMentalHealthAdjacentCoverage` for the exact probes this was
validated against):
1. Named medical conditions used by name (diabetes, thyroid, PCOS, IBS,
   celiac, hypertension/blood pressure, cholesterol) had no coverage --
   only the generic words disease/disorder/anemi[ac] were hardcoded.
2. The general-case safety-adjective pattern omitted safe/unsafe, so
   only the pregnancy/infant/toddler carve-out covered that adjective at
   all, and only for that narrow population case.
3. Plain symptom phrasing (dizzy, headache, fatigue/tired, palpitations)
   combined with "why"/"should I"/"worried" framing, without the literal
   word "symptom" or any existing causal-framing pattern, was unflagged.
4. Supplement questions phrased by vitamin/mineral name rather than the
   literal word "supplement" (e.g. "should I start taking iron pills")
   slipped through.
5. Mood/mental-health-adjacent nutrition questions had no carve-out of
   their own, distinct from phrasing variants of already-covered
   patterns.
Same discipline as before: scoped, non-overtriggering additions, not a
rewrite -- full recall is still not achievable by a keyword approach
(documented, not solved)."""

from __future__ import annotations

import re

# Deliberately broad rather than narrow -- a false positive (an
# unnecessary disclaimer on a benign question) is judged the lesser harm
# than a false negative (a health-adjacent question slipping through
# unflagged), given CLAUDE.md section 8's zero-tolerance framing.
_HEALTH_ADJACENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bdeficien(t|cy|cies)\b",
        r"\bdiagnos(e|is|ed)\b",
        r"\bmedical\s+condition\b",
        r"\bdisease\b",
        r"\bdisorder(ed)?\b",
        r"\bsymptoms?\b",
        r"\bshould\s+i\s+take\b.*\bsupplement",
        r"\bis\s+(this|my|it)\s+(dangerous|serious|normal|healthy|unhealthy)\b",
        r"\bcaused?\s+by\b.*\b(deficien|low|lack\s+of)\b",
        r"\bam\s+i\s+(deficient|anemic|malnourished)\b",
        r"\banemi[ac]\b",
        r"\bvitamin\s+\w+\s+deficien",
        r"\beating\s+disorder\b",
        r"\bdo\s+i\s+have\b",
        # --- 2026-09-08 gap 1: indirect causal/symptom phrasing that
        # doesn't use the literal string "caused by". "could X be why"
        # and "is X the reason/problem/cause" are common ways users
        # phrase a deficiency/symptom-causation question without ever
        # saying "caused by".
        r"\bcould\s+.{0,60}?\bbe\s+why\b",
        r"\bis\s+(my|the|this|it|that)\s+.{0,40}?\b(reason|problem|cause)\b",
        # --- 2026-09-08 gap 2: pregnancy/breastfeeding/infant nutrition
        # -- a distinct population-specific-advice case with no prior
        # coverage at all. Bare keywords are used for terms that are
        # rarely ambiguous in a nutrition-logging context ("pregnant",
        # "breastfeeding", "nursing", "infant", "my baby"); "toddler"
        # and "safe"/"baby"/"infant" combinations are scoped to
        # feeding/safety-adjacent language specifically so an ordinary
        # "recipe for toddlers" request is NOT swept up.
        r"\bpregnan(t|cy)\b",
        r"\bbreast\s*feed(ing)?\b",
        r"\bnursing\b",
        r"\bmy\s+baby\b",
        r"\binfant\b",
        r"\btoddler\b.{0,40}\b(eat(ing)?|feed(ing)?|nutrition|diet|safe(ty)?)\b",
        r"\bsafe(ty)?\b.{0,40}\b(baby|infant|toddler)\b",
        # --- 2026-09-08 gap 3: restrictive-eating phrasing that avoids
        # the word "disorder", directly adjacent to the eating-disorder
        # boundary CLAUDE.md section 8 calls out by name. Calibrated to
        # ongoing-pattern language ("skipping meals" plural/continuous,
        # "barely eating", "not eating enough", "afraid to eat") rather
        # than a single past-tense instance, so an ordinary logging
        # statement like "I skipped breakfast today" is deliberately
        # NOT matched -- that calibration line is inherently the
        # hardest judgment call in this module; see the test file's
        # `TestRestrictiveEatingWithoutDisorderWordCoverage` for the
        # explicit control case.
        r"\bskipping\s+meals\b",
        r"\bbarely\s+eating\b",
        r"\bnot\s+eating\s+enough\b",
        r"\bafraid\s+to\s+eat\b",
        # --- 2026-09-12 gap 1: named medical conditions used by name --
        # previously only the generic words disease/disorder/anemi[ac]
        # were hardcoded, so any specific condition name bypassed the
        # filter entirely. Bare keywords are used since these condition
        # names are rarely ambiguous in a nutrition-logging context.
        r"\bdiabet(es|ic)\b",
        r"\bthyroid\b",
        r"\bpcos\b",
        r"\bibs\b",
        r"\b(ce|coe)liac\b",
        r"\bhypertension\b",
        r"\bblood\s+pressure\b",
        r"\bcholesterol\b",
        # --- 2026-09-12 gap 2: general safety-adjective parity. The
        # pregnancy/infant/toddler carve-out already covered safe(ty),
        # but the general case (any subject, not just "this"/"my"/"it")
        # did not. The second pattern generalizes the subject to any
        # short noun phrase ("is keto safe...", "is intermittent fasting
        # safe...") -- scoped to the safe/unsafe adjectives specifically
        # (not the full dangerous/serious/normal/healthy/unhealthy list)
        # to keep the broadened-subject case narrow.
        r"\bis\s+(this|my|it|that)\s+(dangerous|serious|normal|healthy|unhealthy|safe|unsafe)\b",
        r"\bis\s+\w+(?:\s+\w+){0,3}\s+(safe|unsafe)\b",
        # --- 2026-09-12 gap 3: plain symptom phrasing (dizzy, headache,
        # fatigue/tired, palpitations) without the literal word "symptom"
        # or an existing causal-framing pattern. Calibrated to require
        # "why"/"should I"/"worried" framing alongside the symptom word
        # (in either order, within a bounded distance) so a bare
        # unframed mention (e.g. "I have a headache today") is NOT swept
        # up -- consistent with `TestKnownPrecisionRecallGap`'s
        # documented limits on unframed statements.
        (
            r"\b(dizzy|dizziness|headaches?|fatigued?|tired|palpitations?)\b"
            r".{0,40}\b(why|should\s+i|worried)\b"
        ),
        (
            r"\b(why|should\s+i|worried)\b"
            r".{0,40}\b(dizzy|dizziness|headaches?|fatigued?|tired|palpitations?)\b"
        ),
        # --- 2026-09-12 gap 4: supplement questions phrased by vitamin/
        # mineral name rather than the literal word "supplement" (e.g.
        # "should I start taking iron pills"). Scoped to "should I
        # (start) tak(e/ing)" / "do I need (more/extra)" framing so an
        # ordinary catalog-style mention of a mineral (e.g. "iron-rich
        # foods") is NOT swept up.
        (
            r"\bshould\s+i\s+(start\s+)?tak(e|ing)\b.{0,30}"
            r"\b(iron|calcium|magnesium|zinc|potassium|iodine|folate|biotin|selenium|"
            r"vitamin\s*\w*|omega-?3)\b"
        ),
        (
            r"\bdo\s+i\s+need\s+(more|extra)?\s*"
            r"\b(iron|calcium|magnesium|zinc|potassium|iodine|folate|biotin|selenium|"
            r"vitamin\s*\w*|omega-?3)\b"
        ),
        # --- 2026-09-12 gap 5: mood/mental-health-adjacent nutrition, a
        # distinct carve-out mirroring the pregnancy carve-out's shape --
        # bare keywords for terms rarely ambiguous in this context
        # (anxiety, depression, mental health), and a scoped combo for
        # the genuinely ambiguous term "mood" (only flagged alongside
        # food/diet/eating/nutrition wording, so an ordinary "mood-
        # boosting recipe" request is NOT swept up).
        r"\banxi(ety|ous)\b",
        r"\bdepress(ion|ed)\b",
        r"\bmental\s+health\b",
        r"\bmood\b.{0,40}\b(food|diet|eating|nutrition)\b",
        r"\b(food|diet|eating|nutrition)\b.{0,40}\bmood\b",
        r"\bstress(ed)?\b.{0,40}\b(eating|diet|food)\b",
    )
)


def is_health_adjacent(query: str) -> bool:
    """True if `query` matches any known health-adjacent pattern. Pure
    function: same input always yields the same output, no state, no I/O."""
    if not query or not query.strip():
        return False
    return any(pattern.search(query) for pattern in _HEALTH_ADJACENT_PATTERNS)
