"""Static, versioned embedded RDA/DRI reference table for calcium_mg,
iron_mg, and vitamin_c_mg -- three-nutrient adult-only first pass per
`plans/nutrition-calculation-service/dri-rda-addendum.md` section 5, and
ADR-0024 (Proposed).

**Source**: US NIH Office of Dietary Supplements (ODS) Health Professional
Fact Sheets, which republish the NASEM (National Academies of Sciences,
Engineering, and Medicine; formerly Institute of Medicine) Dietary
Reference Intakes. Public-domain U.S. federal data (addendum section 3);
embedded as a static table rather than a live call because these values
change only on a multi-year NASEM review cycle.

**Retrieval limitation, stated honestly**: the live `ods.od.nih.gov` site
returned HTTP 403 to this agent's automated fetch (likely bot/WAF
blocking of non-browser user agents in this sandboxed environment, not a
content issue). The figures below were retrieved from the Wayback
Machine's archived mirror of each live fact sheet, which itself displays
each page's own "Updated:" byline from ods.od.nih.gov -- i.e. this is the
actual current published fact sheet content, accessed through an
intermediate cache, not a from-memory reconstruction. Every row cites the
exact fact sheet title, canonical URL, its own "Updated:" byline date (as
shown on the live NIH ODS page itself), and the Wayback Machine snapshot
URL/timestamp actually fetched, so this citation is independently
re-verifiable.

Per-nutrient tables, all figures RDA (Recommended Dietary Allowance)
unless noted:

**Calcium** -- "Calcium — Health Professional Fact Sheet", NIH ODS,
page byline "Updated: July 24, 2024".
Canonical URL: https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/
Retrieved via: https://web.archive.org/web/20250101120126/https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/
Table 1 ("Recommended Dietary Allowances (RDAs) for Calcium"), adult rows:
  19-50 years: Male 1,000 mg, Female 1,000 mg
  51-70 years: Male 1,000 mg, Female 1,200 mg
  >70 years:   Male 1,200 mg, Female 1,200 mg

**Iron** -- "Iron — Health Professional Fact Sheet", NIH ODS,
page byline "Updated: October 9, 2024".
Canonical URL: https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
Retrieved via: https://web.archive.org/web/20250103052021/https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
Table 1 ("Recommended Dietary Allowances (RDAs) for Iron"), adult rows:
  19-50 years: Male 8 mg, Female 18 mg (menstrual losses -- see
    "Pregnancy/lactation" gap in the module docstring of
    `domain/services/micronutrient_dri_resolver.py`; a post-menopausal
    lower female figure only applies from 51+)
  51+ years:   Male 8 mg, Female 8 mg

**Vitamin C** -- "Vitamin C — Health Professional Fact Sheet", NIH ODS,
page byline "Updated: March 26, 2021".
Canonical URL: https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/
Retrieved via: https://web.archive.org/web/20250101070601/https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/
Table 1 ("Recommended Dietary Allowances (RDAs) for Vitamin C"), adult row:
  19+ years: Male 90 mg, Female 75 mg (single adult band -- NIH ODS does
    not subdivide the vitamin C RDA further within adulthood; smokers'
    +35 mg/day addendum is NOT applied here -- `profile-service` tracks no
    smoking-status field, so it would be a fabricated adjustment)

**Explicitly not covered by this table (addendum section 1's deferred
list)**: pregnancy/lactation-adjusted values (no `profile-service` field
exists for this), any age band below 19, and any nutrient other than
these three.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.sex import CalculationSexConstant

# Bumped whenever a row's value, band boundary, or source citation changes
# -- surfaced in this service's README.md alongside a "last verified" date
# (ADR-0024's refresh-cadence recommendation).
DRI_TABLE_VERSION = "nih-ods-2024_2021-adult-3nutrient-v1"


@dataclass(frozen=True, slots=True)
class DriBand:
    """One age/sex-banded RDA row for one nutrient. `max_age` is inclusive;
    `None` means "no upper bound" (the oldest published band)."""

    nutrient: str
    min_age: int
    max_age: int | None
    sex_constant: CalculationSexConstant
    value: float
    unit: str


MALE = CalculationSexConstant.MALE
FEMALE = CalculationSexConstant.FEMALE

# Ordered for readability only -- resolution in
# `micronutrient_dri_resolver.py` does an unordered scan, not a
# first-match-wins scan, so row order here is not semantically load-bearing.
DRI_BANDS: tuple[DriBand, ...] = (
    # Calcium (mg) -- Table 1, NIH ODS Calcium fact sheet, see module docstring.
    DriBand(nutrient="calcium_mg", min_age=19, max_age=50, sex_constant=MALE, value=1000.0, unit="mg"),
    DriBand(nutrient="calcium_mg", min_age=19, max_age=50, sex_constant=FEMALE, value=1000.0, unit="mg"),
    DriBand(nutrient="calcium_mg", min_age=51, max_age=70, sex_constant=MALE, value=1000.0, unit="mg"),
    DriBand(nutrient="calcium_mg", min_age=51, max_age=70, sex_constant=FEMALE, value=1200.0, unit="mg"),
    DriBand(nutrient="calcium_mg", min_age=71, max_age=None, sex_constant=MALE, value=1200.0, unit="mg"),
    DriBand(nutrient="calcium_mg", min_age=71, max_age=None, sex_constant=FEMALE, value=1200.0, unit="mg"),
    # Iron (mg) -- Table 1, NIH ODS Iron fact sheet, see module docstring.
    DriBand(nutrient="iron_mg", min_age=19, max_age=50, sex_constant=MALE, value=8.0, unit="mg"),
    DriBand(nutrient="iron_mg", min_age=19, max_age=50, sex_constant=FEMALE, value=18.0, unit="mg"),
    DriBand(nutrient="iron_mg", min_age=51, max_age=None, sex_constant=MALE, value=8.0, unit="mg"),
    DriBand(nutrient="iron_mg", min_age=51, max_age=None, sex_constant=FEMALE, value=8.0, unit="mg"),
    # Vitamin C (mg) -- Table 1, NIH ODS Vitamin C fact sheet, see module docstring.
    DriBand(nutrient="vitamin_c_mg", min_age=19, max_age=None, sex_constant=MALE, value=90.0, unit="mg"),
    DriBand(nutrient="vitamin_c_mg", min_age=19, max_age=None, sex_constant=FEMALE, value=75.0, unit="mg"),
)

# The only nutrients this table is allowed to claim coverage for -- guards
# against a future row being added for a nutrient this table's docstring
# doesn't cite a source for (services/nutrition-calculation-service/CLAUDE.md's
# "never add a nutrient to dri_reference_table.py without a cited
# primary-source value for every band it claims to cover").
COVERED_NUTRIENTS: frozenset[str] = frozenset({"calcium_mg", "iron_mg", "vitamin_c_mg"})
