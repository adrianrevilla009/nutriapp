"""health_topic_classifier -- a PURE, rule-based (keyword/pattern) first
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

No I/O, no framework import (hexagonal-architecture SKILL.md)."""

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
    )
)


def is_health_adjacent(query: str) -> bool:
    """True if `query` matches any known health-adjacent pattern. Pure
    function: same input always yields the same output, no state, no I/O."""
    if not query or not query.strip():
        return False
    return any(pattern.search(query) for pattern in _HEALTH_ADJACENT_PATTERNS)
