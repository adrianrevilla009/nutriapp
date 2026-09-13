# ADR-0024: Micronutrient RDA/DRI Reference Data Source and Refresh Policy

## Status
Proposed

## Date
2026-09-12

## Context
`nutrition-calculation-service`'s `NutritionTargetUpdated` event carries a
`nutrient_targets_min` map. A prior pass ("Phase 1") added the field
itself, re-exposing the already-computed `protein_g`/`fat_g` macro
minimums under a generic, nutrient-keyed shape, but explicitly did **not**
add any true micronutrient (vitamin/mineral) minimum: no RDA/DRI
reference-intake dataset existed anywhere in this codebase, and inventing
one would have violated this service's "never invent a value that is not
available in upstream data" rule
(`.claude/agents/nutrition-calculation-agent.md`) and the
domain-calculation-conventions skill's "cite the source" requirement.

This is a real, current blocker on genuine vitamin/mineral deficiency
detection in `analytics-service`
(`services/analytics-service/domain/tracked_nutrients.py`) — that
service can only evaluate `protein_g`/`fat_g` against a real target today.

`plans/nutrition-calculation-service/dri-rda-addendum.md` ("Phase 2",
human-approved 2026-09-12) closes part of this gap for a defensible
three-nutrient subset (`calcium_mg`, `iron_mg`, `vitamin_c_mg` — the only
vitamin/mineral fields with both a real DRI *minimum*-shaped value and
existing end-to-end plumbing through `catalog-service`'s `NutrientPanel`
and this service's own canonical nutrient vocabulary). Doing so requires a
decision on **where the reference figures come from** and **how they stay
current**, which is architectural in nature — it fixes a specific external
data source and a specific (lack of) live-integration pattern — not just
an implementation detail, hence this ADR rather than only the addendum.

Forces at play:
- **No fabrication, ever.** Any reference dataset must be traceable to a
  named, dated, publicly verifiable source table — not a plausible-looking
  number.
- **This is not medical/clinical-grade guidance and must never be
  positioned as such** (CLAUDE.md section 8) — the source and its scope
  boundaries need to be documented clearly enough that no downstream
  consumer (`analytics-service`, `nutrition-assistant-service`, or a
  future user-facing screen) is tempted to present it as one.
- **DRI/RDA tables change rarely** (a multi-year NASEM review cycle), so a
  live external API call would add resilience-pattern overhead (circuit
  breaker, retry, timeout, bulkhead per CLAUDE.md section 2.6) for numbers
  that are effectively static between requests — and no stable
  machine-readable API for these tables exists to call anyway.
- **Something in this codebase must own noticing when the source table is
  revised.** An "embed once and forget" static table would silently drift
  from the published truth after the next NASEM/NIH ODS revision cycle,
  with nothing prompting a recheck.

## Decision
Adopt **US NIH Office of Dietary Supplements (ODS) Health Professional
Fact Sheets** (which republish NASEM/Institute-of-Medicine Dietary
Reference Intake tables) as the sole source for this service's
micronutrient RDA/DRI reference data, embedded as a **static, versioned
Python table** (`services/nutrition-calculation-service/domain/reference_data/dri_reference_table.py`)
— not a live external API dependency.

Every row in that table cites, in the module's docstring: the exact fact
sheet title, its canonical `ods.od.nih.gov` URL, the fact sheet's own
"Updated:" byline date as published, and (since the live site returned
HTTP 403 to this agent's automated fetch, most likely bot/WAF blocking
rather than a content issue) the Wayback Machine snapshot URL/timestamp
actually used to retrieve the content shown on that live page. This is
disclosed as a retrieval-path limitation, not presented as an unsourced
guess — the content itself is the fact sheet's own published table, not a
reconstruction from training data.

Adopted figures (adult bands only, ages 19+; see the reference table
module for the full per-row citation):
- **Calcium** (fact sheet updated 2024-07-24): 19–50y 1,000 mg (both
  sexes); 51–70y 1,000 mg male / 1,200 mg female; 71y+ 1,200 mg (both
  sexes).
- **Iron** (fact sheet updated 2024-10-09): 19–50y 8 mg male / 18 mg
  female; 51y+ 8 mg (both sexes).
- **Vitamin C** (fact sheet updated 2021-03-26): 19y+ 90 mg male / 75 mg
  female (single adult band).

**Refresh cadence and ownership**: `nutrition-calculation-agent` (this
service's owning agent) is responsible for an **annual manual verification
check** against the live NIH ODS fact sheets (or their most recent
archived mirror if the live site remains inaccessible to automated
tooling), timed to this service's yearly planning cycle. The reference
table module carries `DRI_TABLE_VERSION`
(`nih-ods-2024_2021-adult-3nutrient-v1` as of this ADR), and this service's
`README.md` surfaces that version string plus a "last verified" date
alongside it. A revision found during that check is itself a formula
change under `.claude/skills/domain-calculation-conventions/SKILL.md`
("any change to these formulas... is significant enough to warrant an ADR
proposal") — it requires a new implementation-plan pass amending or
superseding this ADR, not a silent table edit. This service's own
`CLAUDE.md` "Never do this" list enforces the citation requirement
structurally: no nutrient may be added to the reference table without a
cited primary-source value for every band it claims to cover.

**Explicit non-goal**: this reference data, and every value derived from
it, is informational estimation for a general consumer nutrition-tracking
product — never medical nutrition therapy, a diagnosis, or a substitute
for a qualified dietitian/physician's individualized recommendation
(CLAUDE.md section 8). It deliberately does not cover pregnancy/lactation
adjustment (no `profile-service` field exists for this — a genuine,
unresolved cross-service gap, not a decision this ADR makes) or any age
band below 19 (DRI child/adolescent tables use fundamentally different
bands than this service's adult-only formulas currently assume).

## Considered Alternatives
- **(a) Static, versioned, embedded table sourced from NIH ODS fact
  sheets (chosen).** Public-domain U.S. federal data — no license, no
  DPA, no `docs/vendor-risk-register.md` entry warranted (no vendor
  relationship; nothing is processed on our behalf). Trivially
  unit-testable against the exact published worked values. No resilience
  overhead for values that change on a multi-year cycle. Trade-off:
  requires a deliberate, owned refresh process (addressed above) rather
  than always reflecting the current published table automatically.
- **(b) Live call to a third-party nutrition-data API exposing DRI
  values.** Rejected: no such API is known to exist with a stable,
  authoritative DRI dataset (most nutrition-data APIs cover food
  composition, not reference intakes); would introduce an external
  dependency, a vendor-risk-register entry, and full resilience-pattern
  overhead (circuit breaker, retry, timeout, bulkhead) for data that
  essentially never changes between requests — a poor cost/benefit trade
  for this data's actual volatility.
- **(c) Defer indefinitely until a canonical machine-readable DRI dataset
  exists.** Rejected: leaves `analytics-service`'s deficiency-detection gap
  unaddressed with no bounded timeline, for a defensible three-nutrient
  subset that is genuinely achievable now with proper sourcing.
- **(d) Cover a broader nutrient set immediately (vitamin D, B12, folate,
  potassium, zinc, magnesium, etc.).** Rejected for this pass: no plumbing
  exists anywhere in the pipeline (`catalog-service`'s `NutrientPanel`,
  this service's canonical vocabulary) for those fields yet; bundling
  plumbing work with reference-data sourcing in one change was judged too
  large a single approval unit. Tracked as a future, separate work item.

## Consequences
### Positive
- Closes part of the "no genuine micronutrient minimum exists" gap
  blocking real vitamin/mineral deficiency detection, for the three
  nutrients with existing end-to-end plumbing.
- Zero fabrication: every published figure traces to a specific, dated,
  independently re-verifiable fact sheet citation.
- No new external runtime dependency, resilience pattern, or vendor-risk
  entry — consistent with this being effectively-static reference data.
- Establishes a template (reference table + resolver + per-row citation +
  annual verification) that a future nutrient-coverage expansion can
  follow directly, rather than re-deriving the pattern from scratch.

### Negative / Trade-offs
- **Refresh is manual, not automatic.** If the annual verification check
  is skipped or missed, the embedded table can silently drift from the
  currently published NIH ODS figures with nothing forcing a recheck
  beyond the documented process — an operational discipline dependency,
  not a technical safeguard.
- **Pregnancy/lactation and under-19 users get no micronutrient minimum at
  all**, which is stricter than saying nothing about the limitation — this
  is the correct behavior per the "never default a band" acceptance
  criterion, but it does mean real coverage gaps persist for those
  populations until `profile-service` gains the relevant fields and a
  follow-on plan extends the age-banding.
- **Only three nutrients are covered**; a user reading "RDA support" in
  product copy without also reading the documented gaps could reasonably
  overestimate this feature's actual scope — user-facing copy must state
  the three-nutrient, adult-only, non-clinical scope explicitly, not
  imply broader coverage.
- **`analytics-service` does not yet consume the new keys** — this ADR
  and the addendum it supports change what `nutrition-calculation-service`
  publishes, not what any consumer does with it; the deficiency-detection
  gap this was meant to help close is only closed once a follow-up plan in
  `analytics-service`'s own bounded context lands.

### Follow-up actions
- `analytics-service`'s own agent to plan and implement consumption of
  `calcium_mg`/`iron_mg`/`vitamin_c_mg` from `nutrient_targets_min` for
  deficiency detection (extending `TRACKED_NUTRIENTS` and
  `micronutrient_current_targets`) — a separate, distinct work item in a
  different bounded context, not bundled into this ADR.
- `nutrition-calculation-agent` to perform the first annual verification
  check no later than 2027-09 (12 months from this ADR's date), and
  record the outcome (confirmed unchanged, or a superseding ADR/plan) in
  this service's `README.md` "last verified" note.
- A follow-up plan to extend `profile-service` with a pregnancy/lactation
  field (with its own GDPR Article 9 consent surface, per CLAUDE.md
  section 8) is a prerequisite for ever closing the pregnancy/lactation
  gap — not scheduled by this ADR, only flagged as the actual blocker.
- A follow-up question to `architecture-agent`/product: should
  `bmr_calculator.py`'s existing looser under-19 behavior (applies the
  adult Mifflin-St Jeor formula to any `age > 0`) be tightened to match
  this stricter under-19 exclusion, or should this exclusion be loosened
  to match BMR's existing behavior? Not resolved here.

## References
- `plans/nutrition-calculation-service/dri-rda-addendum.md` (the
  human-approved implementation plan this ADR supports)
- `plans/nutrition-calculation-service/implementation-plan.md` (base plan)
- `services/nutrition-calculation-service/domain/reference_data/dri_reference_table.py`
  (the actual embedded table and full per-row citations)
- `services/nutrition-calculation-service/domain/services/micronutrient_dri_resolver.py`
- `.claude/skills/domain-calculation-conventions/SKILL.md` (cite-the-source
  and recomputation-traceability rules)
- `.claude/skills/external-data-ethics/SKILL.md`
- `services/analytics-service/domain/tracked_nutrients.py` (the documented
  gap this work item exists to partially close)
- CLAUDE.md section 8 (AI/health-adjacent professional-advice boundary;
  GDPR Article 9 special-category data)
- NIH Office of Dietary Supplements Health Professional Fact Sheets:
  - Calcium — https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/
    (retrieved via https://web.archive.org/web/20250101120126/https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/)
  - Iron — https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
    (retrieved via https://web.archive.org/web/20250103052021/https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/)
  - Vitamin C — https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/
    (retrieved via https://web.archive.org/web/20250101070601/https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/)
