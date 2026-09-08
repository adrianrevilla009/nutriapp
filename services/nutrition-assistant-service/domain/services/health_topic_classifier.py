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
resist this approach."""

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
    )
)


def is_health_adjacent(query: str) -> bool:
    """True if `query` matches any known health-adjacent pattern. Pure
    function: same input always yields the same output, no state, no I/O."""
    if not query or not query.strip():
        return False
    return any(pattern.search(query) for pattern in _HEALTH_ADJACENT_PATTERNS)
