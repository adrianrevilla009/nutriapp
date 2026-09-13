"""The nutrient keys this service can evaluate for a sustained-deficiency
breach today.

**Original known gap (partially closed 2026-09-12 -- see below):** the
implementation plan's section 9 addendum, resolution 2, approved scoping
deficiency detection to "only nutrients where `nutrition-calculation-service`
already publishes a `target_min` via `NutritionTargetUpdated`". At original
implementation time, that event's actual payload had no micronutrient
`target_min` field at all -- only `macro_targets.protein_g_min`/`fat_g_min`
were genuinely `_min`-shaped target values. Only `protein_g`/`fat_g` had
real, non-null target AND value data flowing through this mechanism.

**2026-09-12 addendum -- calcium/iron/vitamin C target-min consumption
added (`/plans/analytics-service/implementation-plan.md`'s addendum of the
same date):** `nutrition-calculation-service` now additionally publishes
real, cited NIH ODS DRI/RDA minimums for `calcium_mg`, `iron_mg`, and
`vitamin_c_mg` via `NutritionTargetUpdated`'s `nutrient_targets_min` map,
for adult users (age >= 19) with a resolved sex constant only -- absent,
never defaulted/fabricated, otherwise. `HandleNutritionTargetUpdatedHandler`
now stores these 3 the same way `protein_g`/`fat_g` already were. This is
the addendum's full, explicit scope -- no other nutrient is added here (its
own stated non-goal).

**Distinct, still-open gap discovered while doing this addendum (flagged,
not silently patched):** `detect_and_record_deficiency`/`evaluate_breach`/
`HandleNutritionValueRecomputedHandler`'s iteration logic is confirmed
nutrient-agnostic and needed NO change (proven by a `calcium_mg`-keyed test
in `tests/unit/application/test_handle_nutrition_value_recomputed.py`).
However, the CURRENT VALUE side for these 3 nutrients is not wired: the
real `NutritionValueRecomputed` payload carries micronutrient values in a
separate `micronutrients` dict, not in `macros`, and
`nutrition_calculation_events_consumer.py`'s dispatch for that event only
ever forwards `payload["macros"]`. So even though a real `target_min` now
flows for `calcium_mg`/`iron_mg`/`vitamin_c_mg`, no real daily *value* for
them is ever upserted into `micronutrient_window` today -- deficiency
detection for these three is therefore still NOT functionally live
end-to-end. Wiring `payload["micronutrients"]` into that other consumer
path is a distinct, not-yet-planned follow-up, out of scope for this
addendum (see its own explicit non-goal) -- tracked here rather than
silently worked around.

Every other micronutrient (`vitamin_d_mcg`, `vitamin_b12_mcg`, `folate_mcg`,
`potassium_mg`, `zinc_mg`, `magnesium_mg`, etc.) remains fully uncovered --
no target-min AND no value plumbing exists for any of them; this is a
documented absence of upstream data/wiring, not an oversight.

Extending coverage further requires both (a) a
`nutrition-calculation-service` DRI/RDA table addition for that nutrient
(a decision that service's own agent/ADR-0024 owns) and (b) wiring the
value side here -- neither is silently assumed by adding a key to this
frozenset."""

from __future__ import annotations

TRACKED_NUTRIENTS: frozenset[str] = frozenset(
    {"protein_g", "fat_g", "calcium_mg", "iron_mg", "vitamin_c_mg"}
)
