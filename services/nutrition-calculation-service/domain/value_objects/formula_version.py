"""Formula version -- stamped on every computed NutritionTarget/
NutritionValueRecomputed result for traceability (domain-calculation-
conventions SKILL.md section 1: "every computed result must be
traceable"). Bumped whenever a formula, bound, or activity-factor table
changes (each such change requires an ADR proposal per that skill).

Bumped to "2026.2" for
`plans/nutrition-calculation-service/dri-rda-addendum.md` (Phase 2,
ADR-0024 Proposed): `RecomputeNutritionTargetHandler.handle` now also
resolves real calcium_mg/iron_mg/vitamin_c_mg RDA/DRI minimums via
`domain/services/micronutrient_dri_resolver.py`, changing every adult
user's computed `nutrient_targets_min` output going forward. No bulk
reprocessing job -- matches this service's existing
`NutritionValueRecomputed` seam convention (new value appears at the next
natural recompute trigger, not retroactively).
"""

from __future__ import annotations

CURRENT_FORMULA_VERSION = "2026.2"
