# Product Requirements

This document is the product-requirements input `DOMAIN-SETUP.md` section
1 says this template intentionally contains zero of — it exists so an
agent proposing an `/implementation-plan` has a concrete feature list and
phasing to plan against, alongside CLAUDE.md's architectural rules.

## 1. Feature List and Bounded-Context Ownership

| # | Feature | Owning service(s) | Pro-gated? |
|---|---|---|---|
| 1 | Login and registration | `identity-service` | No |
| 2 | Product inventory (scraped from supermarket APIs) with search, dietary/allergen filters | `catalog-service` | No |
| 3 | User details panel: personal data, biometric metrics, evolution graphs, change password, goal-setting engine (auto-calculated calorie/macro targets) | `identity-service` (auth/password), `profile-service` (metrics/evolution/goals), `nutrition-calculation-service` (target computation) | No |
| 4 | Food logging against inventory products or recognized items | `diary-service` | No |
| 5 | Water intake logging | `diary-service` | No |
| 6 | Intermittent fasting window tracking | `diary-service` | No |
| 7 | Weekly meal planning | `diary-service` | No |
| 8 | Macro and micronutrient calculation | `nutrition-calculation-service` | No |
| 9 | Photo upload with AI food detection for nutrient calculation | `food-recognition-service` | No |
| 10 | Barcode product detection | `food-recognition-service` | No |
| 11 | Exercise logging and wearable sync (Apple Health, Google Fit, Fitbit, Garmin) | `activity-service` | No (logging); no Pro gate decided for this feature itself |
| 12 | Sharing and exporting data | `analytics-service` | **Yes** |
| 13 | Generating reports | `analytics-service` | **Yes** |
| 14 | Connecting with other people | `social-service` | **Yes** |
| 15 | Recipe definition (with macros/micros) and publishing | `recipe-service` | **Yes** (publishing only — private authoring is free) |
| 16 | Searching other users' published recipes | `recipe-service` | **Yes** |
| 17 | Pro subscription management and payment processing | `billing-service` | N/A — this *is* the gate |
| 18 | Meal/water/fasting reminders, nutrient-deficiency alerts, transactional email | `notification-service` | No |
| 19 | Conversational AI assistant grounded in the user's own data | `nutrition-assistant-service` | **Yes** |
| 20 | Frontend screen aggregation | `bff-service` | N/A (infrastructure, not a feature) |

Features 5-7 and 11 were added after competitive research (MyFitnessPal,
Cronometer, YAZIO, Lifesum) surfaced them as near-universal in serious
nutrition-tracking products; features 1-4, 8-10, and 12-16 were specified
directly by the product owner.

## 2. Phasing

Phasing is a **recommendation for implementation order**, not a hard
architectural constraint — every service above is specified now (has an
agent, and is listed in CLAUDE.md section 2.2), so `/implementation-plan`
can target any of them regardless of phase. The split exists to sequence
a solo/small-team build toward a usable product before the monetization
surface.

**Phase 1 (MVP — core loop, no monetization):**
`identity-service`, `profile-service`, `catalog-service`, `diary-service`,
`nutrition-calculation-service`, `food-recognition-service`,
`notification-service`, `bff-service`.

Ships: register, browse/search the catalog, log food/water/fasting/planned
meals, see computed nutrient totals and goal targets, log via photo or
barcode, get reminders.

**Phase 2 (Pro / growth):**
`billing-service`, `recipe-service`, `social-service`, `activity-service`,
`analytics-service` (full reporting — its trend/anomaly read-model
consumption can start in Phase 1 for `notification-service`'s alerts, but
report generation and export are Phase 2), `nutrition-assistant-service`.

Ships: the paid tier and everything it gates, exercise/wearable tracking,
and the AI assistant.

Per `CLAUDE.md` section 14, this is still the specification phase — no
application code exists for either phase yet. `identity-service` remains
the first service to run `/implementation-plan` against, as the least
domain-specific reference implementation (`DOMAIN-SETUP.md` section 7).

## 3. Critical User Journeys

See CLAUDE.md section 3 — restated here for product-requirements
traceability:
1. Register -> log a food item from catalog search -> see macro/micro
   totals.
2. Upload a food photo -> AI detects the item -> logged with computed
   nutrients.
3. Upgrade to Pro -> publish a recipe -> another user finds it in recipe
   search.

## 4. Ownership

Updated in the same change that adds, removes, or re-scopes a feature or
a phase assignment. `architecture-agent` checks that a new
`/implementation-plan` traces back to a row in section 1.
