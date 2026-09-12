"""Nutrient-minimum-target map builder.

Generalizes `NutritionTarget`'s already-computed macro minimums
(`MacroTargetRange.protein_g_min`/`fat_g_min`) into a nutrient-keyed shape
(canonical vocabulary matching `NutrientTotalLine`'s macro/micronutrient
field names, `domain/value_objects/nutrient_total_line.py`) so a generic,
nutrient-agnostic downstream consumer (analytics-service's sustained-
deficiency detector, see `docs/events-catalog.md`'s `NutritionTargetUpdated`
entry) can look a minimum up by nutrient key instead of parsing this
service's `macro_targets` structure field-by-field.

No new formula is introduced here -- both values already exist on the
`MacroTargetRange` passed in, themselves derived from Mifflin-St Jeor +
the macro-repartition calculator (`macro_repartition_calculator.py`,
cites `.claude/skills/domain-calculation-conventions/SKILL.md`).

**What this deliberately does NOT cover, and why (checked before writing
this: neither `catalog-service` nor this service stores any RDA/DRI
reference-intake dataset anywhere in the codebase today):**

- `calcium_mg`, `iron_mg`, `vitamin_c_mg` (true micronutrients -- vitamins
  and minerals): no age/sex-adjusted RDA/DRI reference-intake table exists
  anywhere in this codebase to compute a genuine, non-fabricated minimum
  for these. Inventing a clinical threshold here would violate both this
  service's "never invent a value that is not available in upstream data"
  rule (`.claude/agents/nutrition-calculation-agent.md`) and the
  domain-calculation-conventions SKILL.md's "cite the source" requirement
  -- there is no source to cite. This is the actual, current blocker on
  real vitamin/mineral deficiency detection in analytics-service (see
  `services/analytics-service/domain/tracked_nutrients.py`), not an
  oversight in this pass.
- `fiber_g`: a commonly-cited Adequate Intake formula exists in the
  literature (14 g per 1000 kcal, Institute of Medicine Dietary Reference
  Intakes, as adopted by the USDA Dietary Guidelines for Americans) but is
  deliberately NOT implemented here -- adding it would be a *new formula*,
  not an additive field, and per domain-calculation-conventions SKILL.md
  ("any change to these formulas ... is significant enough to warrant an
  ADR") it needs its own human-approved ADR/implementation-plan pass, not
  a silent addition riding along on this schema change.
- `sodium_mg`, `salt_g`, `sugars_g`, `saturated_fat_g`: these are
  upper-limit ("should not exceed") nutrients, not deficiency-relevant
  floors. A "_min" target is the wrong semantic for them regardless of
  whether reference data existed -- they will never appear in this map.

Extending real coverage requires both new authoritative reference data
AND a new ADR for the formula that consumes it; tracked as a known,
explicit gap, not silently worked around.

**Update (Phase 2, `dri-rda-addendum.md`)**: `calcium_mg`, `iron_mg`, and
`vitamin_c_mg` are no longer in that "no source exists" category -- real,
cited NIH ODS/NASEM DRI reference data now exists
(`domain/reference_data/dri_reference_table.py`) and is resolved per-user
by `domain/services/micronutrient_dri_resolver.py`. This module's own
`build_nutrient_targets_min` is unchanged (still exactly protein_g/fat_g,
still zero micronutrient fabrication if called alone); the merge with the
resolver's output happens one layer up, in
`RecomputeNutritionTargetHandler.handle`, since that is the only place
both a `MacroTargetRange` and the user's sex/age are simultaneously in
scope. `fiber_g`/`sodium_mg`/`salt_g`/`sugars_g`/`saturated_fat_g` remain
out of scope for the reasons given above -- unchanged.
"""

from __future__ import annotations

from domain.value_objects.macro_target_range import MacroTargetRange

# Documented for tests/readers -- the nutrients this function is known to
# NOT populate today, and why (see module docstring for the full reasoning
# per nutrient). Not exhaustive of every possible nutrient name, just the
# ones this service's own canonical vocabulary already knows about
# (`domain/value_objects/nutrient_total_line.py`).
#
# `calcium_mg`/`iron_mg`/`vitamin_c_mg` were removed from this set in
# Phase 2 -- they are now resolved by `micronutrient_dri_resolver.py` and
# merged in one layer up (see module docstring "Update" note above). They
# are never populated by *this* function directly.
NOT_YET_COVERED_NUTRIENTS: frozenset[str] = frozenset(
    {
        "fiber_g",
        "sodium_mg",
        "salt_g",
        "sugars_g",
        "saturated_fat_g",
    }
)


def build_nutrient_targets_min(macro_targets: MacroTargetRange) -> dict[str, float]:
    """Returns the canonical-nutrient-name -> minimum-target map this
    service can genuinely and defensibly compute today from macro targets
    alone. Always exactly `{"protein_g": ..., "fat_g": ...}` -- see module
    docstring for what's excluded and why, and for where the micronutrient
    (calcium/iron/vitamin C) entries actually get merged in."""
    return {
        "protein_g": macro_targets.protein_g_min,
        "fat_g": macro_targets.fat_g_min,
    }

