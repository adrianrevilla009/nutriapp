"""The nutrient keys this service can evaluate for a sustained-deficiency
breach today.

**Known gap, discovered during implementation (flagged for
architecture-agent/security-agent review, not silently worked around):**
the implementation plan's section 9 addendum, resolution 2, approved
scoping deficiency detection to "only nutrients where
`nutrition-calculation-service` already publishes a `target_min` via
`NutritionTargetUpdated`". Re-reading that event's actual documented
payload (docs/events-catalog.md) while implementing this: it has no
micronutrient `target_min` field at all -- only `macro_targets.protein_g_min`
and `macro_targets.fat_g_min` are genuinely `_min`-shaped target values in
the schema as it exists today. There is no live path today from
`NutritionValueRecomputed`'s `micronutrients` dict (vitamins/minerals) to
any published target for those nutrients -- true micronutrient deficiency
detection is therefore NOT functionally live in this pass, despite the
domain/application-layer mechanism being generically nutrient-agnostic
and fully testable. Only `protein_g`/`fat_g` (from `NutritionValueRecomputed`'s
always-present `macros` field, evaluated against `NutritionTargetUpdated`'s
`macro_targets.protein_g_min`/`fat_g_min`) have real, non-null data flowing
through this mechanism today. Extending real micronutrient coverage
requires a `NutritionTargetUpdated` v2 payload addition in
`nutrition-calculation-service` -- out of scope for this plan, same
"reopening an already-merged service's formula surface" caution
`docs/events-catalog.md` already applies to `ExerciseLogged`."""

from __future__ import annotations

TRACKED_NUTRIENTS: frozenset[str] = frozenset({"protein_g", "fat_g"})
