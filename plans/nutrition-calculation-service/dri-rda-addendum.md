# Implementation Plan Addendum — Real Micronutrient RDA/DRI Minimum Targets

**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Status:** Approved 2026-09-12, by adrianrg1996@gmail.com ("Aprobar como está").
**Related:** ADR-0001 (hexagonal), ADR-0002 (event-driven CRUD exception), `.claude/agents/nutrition-calculation-agent.md`, `.claude/skills/domain-calculation-conventions/SKILL.md` (mandatory), `.claude/skills/external-data-ethics/SKILL.md`, `docs/events-catalog.md`, `docs/testing-strategy.md`, `plans/nutrition-calculation-service/implementation-plan.md` (base plan this addends), `services/analytics-service/domain/tracked_nutrients.py` (the documented gap this work item exists to close, partially). Proposes **ADR-0024** (see §10 below) — to be drafted alongside implementation.

This addendum is appended to, and governed by, the base implementation plan at `plans/nutrition-calculation-service/implementation-plan.md`. It was produced by `nutrition-calculation-agent` as a Stage-2 plan-only research pass (no code written), and is persisted here verbatim now that it has been approved.

---

## 0. Prerequisite discrepancy found during research — resolved

The planning pass found that a prior session's "Phase 1" work (a generic `nutrient_targets_min` field re-exposing `protein_g`/`fat_g` minimums, added to `NutritionTargetUpdated`) did not appear to exist in the main checkout. This was a false alarm: that work exists, uncommitted, in an isolated git worktree (`worktree-agent-a6da2449aa2c6bf74`) that the planning agent's own working directory could not see. It is not lost and does not need to be redone. This addendum's Phase 2 (below) is implemented on top of that same worktree's Phase 1 work, as one combined change, per this addendum's own bundling decision.

## 1. Scope

Add genuine, source-cited RDA/DRI-based minimum targets for a defensible subset of vitamins/minerals to `nutrition-calculation-service`'s `nutrient_targets_min` map (extending the Phase-1 scaffolding above), computed per-user from `profile-service` metrics already available today (sex, age) — with zero fabricated values for anything `profile-service` cannot support (pregnancy/lactation banding).

**In scope (Phase 2, the actual ask):**
- A new pure domain service resolving a user's RDA minimum for **calcium_mg, iron_mg, vitamin_c_mg** — the three vitamin/mineral fields `catalog-service`'s `NutrientPanel` and this service's own `nutrient_vocabulary_translator.py` canonical vocabulary already carry end-to-end.
- A static, versioned, embedded reference dataset for those three nutrients, banded by sex and adult age group, sourced from **US NIH ODS / NASEM Dietary Reference Intakes (DRI)** fact sheets — exact figures and band boundaries must be pulled from the live NIH ODS fact sheets at implementation time (not assumed from this plan), with the exact URL and retrieval date cited per nutrient.
- Wiring that resolver's output into `nutrient_targets_min` alongside the existing `protein_g`/`fat_g` entries.
- Updating `docs/events-catalog.md` and the JSON Schema additively (new optional dict keys, non-breaking, same event version — `NutritionTargetUpdated` stays v1).

**Explicitly deferred (not in this pass):**
- Any other vitamin/mineral (vitamin D, B12, folate, potassium, zinc, magnesium, etc.) — no plumbing exists for them anywhere in the pipeline.
- Sodium/salt minimums — DRI treats these as upper limits, wrong shape for `nutrient_targets_min`.
- Fiber — has a genuine DRI Adequate Intake minimum, but is a separate, fast-follow work item, not bundled here.
- Pregnancy/lactation-adjusted values — `profile-service` tracks no such field today; a genuine cross-service blocker, not a scope choice.
- Age bands below 19 — DRI child/adolescent tables use fundamentally different bands than this service's adult-only Mifflin-St Jeor BMR formula currently assumes. Users under 19 get **no** micronutrient minimum entries (absent, not defaulted) — stricter than the BMR calculator's existing behavior, deliberately, flagged as a follow-on question for `architecture-agent`/product.
- `analytics-service`'s consumer changes to actually *use* the new values for deficiency detection — a separate, distinct work item in a different bounded context.
- `profile-service` reveal-metrics endpoint changes — not needed; `sex`/`age` are already revealed and already piped into `RecomputeNutritionTargetHandler`.

**Acceptance criteria:**
1. `nutrient_targets_min` carries `protein_g`, `fat_g`, `calcium_mg`, `iron_mg`, `vitamin_c_mg` for every adult (age ≥ 19) user, each value traceable to a cited published DRI table entry for that user's resolved sex-band and age-band.
2. No value is fabricated, interpolated, or defaulted across a band boundary the reference table doesn't actually specify.
3. `Sex.OTHER` is handled by the exact same `calculation_sex_constant` mechanism `bmr_calculator.py` already established — explicit selection required, never defaulted.
4. Users under 19 get zero micronutrient entries in `nutrient_targets_min`.
5. Every new domain function cites its source table + retrieval/version date in its docstring, per `domain-calculation-conventions/SKILL.md`.
6. `docs/events-catalog.md` and the JSON Schema are updated additively; `NutritionTargetUpdated` stays `version: 1`.

## 2. Architectural classification

No change: event-driven CRUD (ADR-0002 exception). Domain layer (new pure function/reference table, no I/O), application layer (`RecomputeNutritionTargetHandler` gains one more call using inputs already in scope), no infrastructure changes.

## 3. Data source (approved)

**US NIH ODS / NASEM Dietary Reference Intakes (DRI/RDA tables)**, embedded as a static, versioned Python table — not a live API dependency. Rationale (full detail in the research report this addendum summarizes): public-domain U.S. federal data, no license/DPA, no `vendor-risk-register.md` entry warranted (no vendor relationship — nothing processed on our behalf), DRI values change on a multi-year NASEM review cycle so a live call adds resilience-pattern overhead for numbers that essentially never change between requests, no stable machine-readable API exists for these tables anyway, and a static table is trivially unit-testable against published worked values. Attribution (source URL + retrieval date) is cited in the reference-table module's docstring.

## 4. Formula/domain-model design

New pure function `domain/services/micronutrient_dri_resolver.py::resolve_micronutrient_dri_minimums(sex, age, calculation_sex_constant) -> dict[str, float]`, colocated with `bmr_calculator.py`, zero framework dependencies. `Sex.OTHER` handling mirrors `bmr_calculator.py` exactly (explicit constant required, never defaulted). Age banding modeled as ordered `(min_age, max_age_or_none, sex_constant, nutrient, value, source_citation)` reference rows, verified against live NIH ODS fact sheets at implementation time. Ages < 19 get no entries (absent, not defaulted). Wired into `RecomputeNutritionTargetHandler.handle`, merged into `build_nutrient_targets_min`'s output. `formula_version` (`CURRENT_FORMULA_VERSION`) is bumped since this changes computed output for every user going forward — no bulk reprocessing job, matches this service's existing `NutritionValueRecomputed` seam convention.

## 5. Micronutrient scope boundary

3-nutrient first pass: calcium_mg, iron_mg, vitamin_c_mg — the only vitamin/mineral fields with (a) real DRI *minimum*-shaped guidance and (b) existing end-to-end plumbing in `catalog-service`'s `NutrientPanel`. Sodium/sugars/saturated fat structurally excluded (DRI defines maximums, not minimums, for these). Fiber deferred as a separate fast-follow (real DRI Adequate Intake minimum exists but it's not a vitamin/mineral).

## 6. Files to create or modify

See the full research report's file list (domain: `reference_data/dri_reference_table.py`, `services/micronutrient_dri_resolver.py`, finish `services/nutrient_target_min_builder.py`; application: `commands/recompute_nutrition_target.py`; events/schema/docs: `events/nutrition_target_updated.py`, shared-contracts schema + Python model, `docs/events-catalog.md`, `docs/domain-glossary-and-context-map.md`; service `README.md`/`CLAUDE.md`; tests across unit/domain, unit/application, contract/events).

## 7. Cross-service impact

No code change required in `profile-service` or `catalog-service`. `analytics-service` is not changed by this addendum — its own separate follow-up plan is needed to consume the new keys (extend `TRACKED_NUTRIENTS`, project into `micronutrient_current_targets`). `architecture-agent` review recommended (and separately requested, see below) on the additive-JSON-Schema-compatibility question given `macro_targets`'s existing `additionalProperties: false` pattern.

## 8. Test plan reference

Reference-value tests against exact published NIH ODS/NASEM worked values at real age-band boundaries (19, 51, 71); `Sex.OTHER` deferral test; under-19 boundary test (18 vs 19); `nutrient_target_min_builder.py` merged-dict assertions; `dri_reference_table.py` self-consistency tests (no overlapping/missing bands, no negative values, every row cited); idempotency-replay stability of the new keys; mutation testing on the resolver/table (band-boundary logic is correctness-sensitive); contract test proving an *old-shaped* payload (without `nutrient_targets_min`) still validates against the updated schema, proving backward compatibility rather than assuming it.

## 9. Risks and open questions

1. Exact DRI numbers/band boundaries must be pulled from live NIH ODS fact sheets at implementation time, not assumed from this plan.
2. Static embedded table defensibility long-term — recommend the proposed ADR own an explicit refresh-trigger/ownership decision (e.g. an annual manual-check reminder, `DRI_TABLE_VERSION` + "last verified" date surfaced in the README) rather than "embed once and forget."
3. Pregnancy/lactation banding is a real, unresolved cross-service gap (`profile-service` has no such field; pregnancy status is likely GDPR Article 9 special-category data requiring its own consent surface) — flagged, not silently shipped under an "RDA support" banner without this caveat visible to `security-agent`/product.
4. Under-19 strictness is inconsistent with the already-shipped BMR calculator's looser behavior (applies the adult formula to any `age > 0`) — a real design tension, not resolved here; follow-up question to `architecture-agent`/product on whether BMR should be tightened to match.
5. JSON Schema additive-compatibility mechanics need `architecture-agent` sign-off before/alongside implementation given the existing `additionalProperties: false` pattern on `macro_targets`.

## 10. ADR-0024 (approved to propose)

**Title**: "Micronutrient RDA/DRI reference data source and refresh policy." Scope: source selection (§3), refresh cadence/ownership, and the explicit non-goal of ever treating this as medical/clinical-grade guidance (CLAUDE.md §8 cross-reference). To be drafted via `/adr` alongside implementation, status `Proposed` until reviewed and accepted.

## 11. Resilience/caching/migration needs

None — no new circuit breaker, cache namespace, external call, or migration.
