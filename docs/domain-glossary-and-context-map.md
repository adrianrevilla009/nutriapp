# Domain Glossary & Bounded Context Map

Standard DDD artifacts: a shared vocabulary (ubiquitous language) and an
explicit map of how NutriApp's 14 bounded contexts (CLAUDE.md section 2.2)
relate to each other. An agent implementing any service should read this
document first to know the exact meaning of a term before writing a single
entity or event name that uses it.

## 1. Domain Glossary (Ubiquitous Language)

| Term | Definition | Owning bounded context |
|---|---|---|
| User | An individual authenticated principal. NutriApp is single-tenant (ADR-0018) — there is no Tenant/Organization concept above a User. | `identity-service` |
| Food Entry | A single logged instance of food eaten: a product/recipe/photo-detected item, a quantity, a meal slot, and a timestamp. | `diary-service` |
| Water Intake Entry | A single logged instance of water consumed. | `diary-service` |
| Fasting Window | A recorded start/end interval of an intermittent-fasting period. | `diary-service` |
| Meal Plan Entry | A food entry scheduled ahead of time, distinct from an as-eaten Food Entry. | `diary-service` |
| Product | An item in the supermarket product inventory: name, brand, barcode, per-100g nutrition data, dietary/allergen tags. | `catalog-service` |
| Dedup Key | The identity `catalog-service` uses to decide whether an incoming, normalized source record is the same Product as one already catalogued: barcode when present (the sole cross-source key — no fuzzy name+brand matching), otherwise `(source, source_product_id)` scoped to that one source only. | `catalog-service` |
| Ingestion Run | One bounded execution of a `catalog-service` source adapter over a page/batch of records, audited (source, started/finished timestamps, items seen/added/updated/skipped, status) independent of any other source's run — one source's failure never blocks another's. | `catalog-service` |
| Nutrient Total | The computed macro/micronutrient sum for a Food Entry, a meal, or a day. | `nutrition-calculation-service` |
| Nutrition Target | The computed calorie/macro goal for a user, derived from Profile metrics and Goal via the Mifflin-St Jeor formula. | `nutrition-calculation-service` |
| Profile Metric | A single biometric reading (weight, height, age, sex, activity level). | `profile-service` |
| Biometric Consent | A user's explicit, specific grant of consent to collect biometric/health data (CLAUDE.md section 8) — distinct from, and never bundled into, general ToS acceptance. Required before any Profile Metric or Goal can be recorded; recorded as its own event (`BiometricConsentGranted`), not a flag bundled into another record. | `profile-service` |
| Goal | A user's stated objective (lose/maintain/gain weight, target value/date) used as a Nutrition Target input. | `profile-service` |
| Detection | A food-recognition-service result from a photo or barcode scan: an identified item, a confidence range, and (for photos) an estimated nutrient range — always subject to user confirmation before becoming a Food Entry. | `food-recognition-service` |
| Exercise Entry | A manually logged or wearable-synced bout of exercise with a calorie-burn estimate. | `activity-service` |
| Recipe | A user-authored combination of Products with quantities, servings, and a computed per-serving Nutrient Total. | `recipe-service` |
| Publish (a Recipe) | Making a Recipe visible in cross-user Recipe search — a Pro-gated action, distinct from authoring a Recipe for personal use. | `recipe-service` |
| Follow | A one-way connection from one User to another (this User sees that User's public activity). Not an organizational membership — see `docs/multi-tenancy.md`. | `social-service` |
| Subscription | A User's Pro-tier billing state (active/cancelled/past-due) and its renewal cycle. | `billing-service` |
| Entitlement | A derived flag (from Subscription state) that a Pro-gated service checks before serving a Pro feature (recipe publish/search, following, reports, data export). | `billing-service` (issued), consumed by `recipe-service`, `social-service`, `analytics-service` |
| Anomaly | A detected recurring pattern over a rolling window (e.g. a sustained micronutrient deficiency) surfaced to the user or the assistant. | `analytics-service` |

## 2. Bounded Context Map

Document the relationship type between each pair of bounded contexts that
communicate, using standard DDD context-mapping patterns. Not every pair
needs a relationship — only document ones that actually integrate.

| Upstream context | Downstream context | Relationship pattern | Notes |
|---|---|---|---|
| `identity-service` | every other service | **Shared Kernel** (the `user_id` identity concept) via **Open Host Service** (JWT claims validated at Kong) | `identity-service` never changes the token contract without an ADR (`docs/authorization-model.md`) |
| `identity-service` | `profile-service` | **Customer-Supplier** via published events | `profile-service` creates a profile in reaction to `UserRegistered`; it does not call `identity-service` synchronously |
| `notification-service` | `identity-service` | **Conformist**, narrow synchronous exception | `notification-service` (not yet built) calls `POST /internal/v1/auth/tokens/{reference_id}/reveal` once per email-verification/password-reset flow to retrieve a raw secret (identity-service plan §5, "reference+secret" pattern) — never routed through Kong, authenticated via a dedicated `internal-reveal-credential`. This is a deliberate, single-endpoint exception to `identity-service`'s Open Host Service relationship with every other service above, not a general precedent for synchronous calls into `identity-service` |
| `catalog-service` | `diary-service` | **Customer-Supplier** | `diary-service` consumes catalog data as a customer; `catalog-service`'s roadmap is influenced by what `diary-service` needs, but is not obligated to conform |
| `catalog-service` | `recipe-service` | **Customer-Supplier** | Recipe ingredients resolve to real `catalog-service` products |
| `diary-service` | `nutrition-calculation-service` | **Customer-Supplier** via published domain events | `nutrition-calculation-service` reacts to `diary-service`'s events; it does not call back synchronously (CLAUDE.md section 2.2) |
| `profile-service` | `nutrition-calculation-service` | **Customer-Supplier** via published domain events | Metric/goal changes trigger target recomputation |
| `activity-service` | `nutrition-calculation-service` | **Customer-Supplier** via published domain events | Exercise data adjusts TDEE-based targets |
| `food-recognition-service` | `diary-service` | **Anticorruption Layer** | External vision-provider concepts (confidence scores, provider-specific labels) are translated into `diary-service`'s own domain vocabulary at the `food-recognition-service` boundary — `diary-service` never sees a provider-specific type |
| `food-recognition-service` | `catalog-service` | **Customer-Supplier** | Barcode detections are looked up against catalog product data |
| `billing-service` | `recipe-service`, `social-service`, `analytics-service` | **Open Host Service** (entitlement events + a fallback sync check) | Consumers cache the entitlement flag locally per `.claude/skills/saga-conventions/SKILL.md`; a lagging consumer fails safe (not-yet-entitled) |
| `nutrition-assistant-service` | `diary-service`, `profile-service`, `nutrition-calculation-service`, `analytics-service` | **Conformist** | The assistant's retrieval layer conforms to the read models these services already publish, rather than requesting new integration points |
| `analytics-service` | `notification-service` | **Customer-Supplier** via published events | `analytics-service` decides an alert is warranted (`NutrientDeficiencyDetected`); `notification-service` only delivers it |
| Any external third-party API (payment processor, vision/LLM provider, wearable provider) | the owning service | **Anticorruption Layer** | Per `.claude/skills/resilience-patterns/SKILL.md` — the port abstraction (e.g. `RecognitionPort`, `WearableProviderPort`, `PaymentProviderPort`) already enforces this at the code level; this row makes the DDD pattern name explicit |

## 3. How This Interacts with Section 2.2's Service Table

CLAUDE.md section 2.2 lists bounded contexts by their technical shape
(one service, one database). This document adds the *semantic*
relationships between them — which context's model is authoritative for
a shared concept, and which context has to adapt to the other. When the
two disagree (e.g. a service table entry implies two contexts are more
tightly coupled than their actual relationship pattern here suggests),
this document is the tiebreaker for architectural review, since it
reflects deliberate DDD analysis rather than just a service inventory.

## 4. Maintenance

Update this document in the same pull request that introduces a new
bounded context, a new cross-context integration, or a term whose meaning
would otherwise be ambiguous across two services. `architecture-agent`
checks new entity/event names against the glossary during
`/implementation-review` and flags any term used with a meaning that
doesn't match its glossary entry (or any new domain term introduced
without being added here).
