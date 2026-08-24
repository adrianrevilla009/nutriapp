---
description: How to document and test NutriApp's core nutrition-calculation logic (macro/micronutrient totals, TDEE/goal targets) — mandatory reading before touching nutrition-calculation-service.
---

# Domain Calculation Conventions

NutriApp's core business logic whose correctness matters more than the
rest of the codebase is its nutrition math: nutrient totals and
calorie/macro targets. This skill defines *how* such logic must be
documented, versioned, and tested (section 1), and *what* the actual
formulas are (section 2).

## 1. General Rules (domain-agnostic — keep these)

- **Cite the source.** Every formula must reference where it came from
  (a named method, a regulation, a published standard, or an explicit
  internal decision) directly in the docstring of the implementing
  function. If a different method is ever needed for a specific case,
  document that choice as an ADR before implementing it — never fork
  silently.
- **Traceability.** Every computed result must be traceable: store which
  formula version and which inputs produced it. This is a natural fit for
  an event-sourced model if the owning service uses one — see
  `.claude/skills/cqrs-event-sourcing/SKILL.md`.
- **No false precision.** If a result is an estimate, present it as such
  (a range, a margin, or explicit "estimate" framing) — never a single
  precise number implying certainty the calculation doesn't have.
- **Never silently reinterpreted as professional advice.** If the domain
  borders on medical, legal, or financial advice, every user-facing
  result must be framed as informational, not a diagnosis/professional
  recommendation, unless the product is explicitly built and licensed to
  provide that.
- **Test against known reference values.** Every formula implementation
  must have unit tests against independently verifiable reference values
  (published examples, regulatory worked examples, or a second
  independent implementation), to catch regressions. Mutation testing is
  recommended for this module specifically — see `docs/testing-strategy.md`
  section 4.
- **Recomputation is explicit, never a silent in-place update.** A stored
  computed value is recomputed (producing a new versioned event, not a
  silent write) when its inputs change *or* when a bug fix corrects the
  formula itself — in which case, document the correction and consider
  whether historical computed values should be reprocessed.

## 2. NutriApp's Calculations

### Nutrient Totals (per diary entry / per day)
Owned by `nutrition-calculation-service`, triggered by `FoodEntryLogged`
(and its corrections) from `diary-service`.
- **Source data**: per-100g macro/micronutrient values from
  `catalog-service` (for a matched product) or from
  `food-recognition-service`'s AI-estimated values (for a photo-detected
  item without a catalog match).
- **Formula**: `nutrient_amount = (per_100g_value / 100) x quantity_grams`,
  summed across all entries in the requested window (meal, day).
- **Uncertainty handling**: when the source is an AI estimate, carry its
  confidence range through into the total rather than collapsing it to a
  single point value — the totals view must be able to show "approximate"
  when any contributing entry is estimate-sourced.

### Goal-Setting Engine: BMR / TDEE / Targets
Owned by `nutrition-calculation-service`, triggered by `WeightRecorded` /
`BodyMetricRecorded` / `GoalSet` / `GoalUpdated` from `profile-service`,
and by `ExerciseLogged` / `WearableActivitySynced` from `activity-service`.

**BMR — Mifflin-St Jeor** (cite: Mifflin MD et al., "A new predictive
equation for resting energy expenditure in healthy individuals",
Am J Clin Nutr, 1990):
- Men: `(10 x weight_kg) + (6.25 x height_cm) - (5 x age) + 5`
- Women: `(10 x weight_kg) + (6.25 x height_cm) - (5 x age) - 161`

**TDEE**: `BMR x activity_factor`, where `activity_factor` ranges from
1.2 (sedentary) to 1.9 (extremely active) based on the user's stated
activity level in `profile-service`, adjusted upward by logged/synced
exercise calories from `activity-service` when available (never double
counted against the baseline activity factor — document which one a given
user's calculation used).

**Calorie target**: `TDEE +/- goal_adjustment`, where `goal_adjustment` is
a documented, bounded value per goal type (lose/maintain/gain) — bounds
exist to prevent generating an unsafe target (e.g. a deficit large enough
to imply a rate of loss beyond generally-recognized safe limits); a target
outside the safe bound is clamped and the user is informed why, not
silently honored.

**Macronutrient repartition** (applied to the calorie target):
- Protein: 1.6-2.2 g/kg of body weight (a range, not a point value) for
  body-composition goals.
- Fat: minimum 20% of total calories.
- Carbohydrates: the remainder after protein and fat are fixed.

Any change to these formulas, bounds, or activity-factor table is
significant enough to warrant an ADR proposal via `/adr` — this is exactly
the kind of "computed value changed for everyone" event this skill's
recomputation rule (section 1) exists to make traceable.
