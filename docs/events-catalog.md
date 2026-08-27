# Domain Events Catalog

This is the single source of truth for every domain event published in
NutriApp. Update this file in the same pull request that introduces
or changes an event. Naming convention: PascalCase, past tense, describing
a fact that happened.

## Format per entry
```
### <EventName> (v<version>)
- Producer: <service>
- Consumers: <service(s), or "none yet">
- Emitted when: <trigger>
- Payload schema:
  {
    "event_id": "uuid",
    "aggregate_id": "uuid",
    "event_type": "<EventName>",
    "version": <int>,
    "occurred_at": "ISO-8601 timestamp",
    "payload": { ... event-specific fields ... },
    "metadata": {
      "correlation_id": "uuid",
      "causation_id": "uuid",
      "user_id": "uuid"
    }
  }
```

---

## Events

Events below are marked `Status: Active` once actually implemented and
covered by a passing contract test; unmarked entries remain planned (not
yet implemented — the owning service doesn't exist yet).

### UserRegistered (v1)
- Status: Active
- Producer: identity-service
- Consumers: profile-service (to create the user's profile), diary-service,
  any service that needs to initialize a per-user context
- Emitted when: a new user completes registration.
- Payload: `{ "user_id": "uuid", "email": "string", "registered_at": "timestamp",
  "email_verification_token_reference_id": "uuid" }`
  — the `email_verification_token_reference_id` field was added additively
  (implementation plan section 5): the raw verification secret never
  travels in this event, only a reference id. `notification-service`
  retrieves the actual secret via a synchronous, once-only internal call,
  `POST /internal/v1/auth/tokens/{reference_id}/reveal` (never routed
  through Kong), wrapped in a circuit breaker on its own side. Additive,
  non-breaking for the existing consumers listed above — confirmed by
  `architecture-agent` per the implementation plan.

### PasswordResetRequested (v1)
- Status: Active
- Producer: identity-service
- Consumers: notification-service (to send the reset email)
- Emitted when: a user requests a password reset for an account that
  exists (no event is published for an unknown email — no
  user-enumeration signal).
- Payload: `{ "user_id": "uuid", "email": "string",
  "reset_token_reference_id": "uuid", "requested_at": "timestamp" }`
  — reference id only, same reference+secret pattern as
  `UserRegistered`'s `email_verification_token_reference_id`. No raw
  secret.

### NewDeviceLoginDetected (v1)
- Status: Active
- Producer: identity-service
- Consumers: notification-service (new-device alert email)
- Emitted when: a login succeeds from a device fingerprint (hash of
  User-Agent + IP) not previously seen for that user. A user's very first
  login is never flagged as "new."
- Payload: `{ "user_id": "uuid", "device_fingerprint_hash": "string",
  "occurred_at": "timestamp", "email": "string" }`. No raw credentials.

### ProductCatalogued (v1)
- Status: Active
- Producer: catalog-service
- Consumers: diary-service (documented future consumer -- deliberately
  **not built** by `diary-service`'s reference implementation plan;
  `FoodEntryLogged`/`MealPlanned`'s `source.snapshot` is a client-supplied,
  point-in-time record of what the user logged, not a live mirror of the
  catalog, so silently reconciling it against a later `ProductUpdated`
  may be the wrong behavior, not merely a deferred one -- see
  `/plans/diary-service/implementation-plan.md` section 9.4), recipe-service
  — neither exists as a live consumer yet, so no live integration breaks;
  this payload shape is their future contract. **Correction (superseding
  the earlier placeholder note that listed food-recognition-service
  here):** food-recognition-service does NOT consume this event.
  Barcode-to-product resolution needs to be synchronous and low-latency
  (a user is waiting on a scan result), so
  `/plans/food-recognition-service/implementation-plan.md` resolves it via
  a direct, circuit-breaker-guarded call to catalog-service's internal
  `GET /internal/v1/catalog/lookup?barcode={barcode}` endpoint instead
  (`/plans/catalog-service/implementation-plan.md` Addendum 2) -- eventual
  consistency via this event was judged the wrong shape for that use
  case, not merely deferred.
- Emitted when: a new product (by dedup key — barcode when present,
  otherwise `(source, source_product_id)`) is first written to
  `products`, regardless of which source triggered it.
- Payload: `{ "product_id": "uuid", "barcode": "string | null",
  "name": "string | null", "brand": "string | null", "category": "string | null",
  "nutrition_per_100g": { "...": "macro/micro fields" } | null,
  "dietary_tags": ["string"], "allergen_tags": ["string"],
  "package_size": { "value": "number", "unit": "string" } | null,
  "sources": ["open_food_facts" | "usda_fdc"], "catalogued_at": "timestamp" }`
  — renamed from an earlier `ProductAdded` placeholder for PascalCase-
  past-tense precision consistent with `UserRegistered`/`WeightRecorded`
  (catalog-service implementation plan section 5): "Added" reads as a raw
  CRUD verb, whereas "Catalogued" names the actual domain fact and fits
  the dedup/merge design's "a second source can complete a record a first
  source started, still a fresh catalog entry from the read side" case.
  See `packages/shared-contracts/schemas/product_catalogued.v1.json`.

### ProductUpdated (v1)
- Status: Active
- Producer: catalog-service
- Consumers: diary-service, recipe-service (same as `ProductCatalogued`,
  neither live yet). Not food-recognition-service -- see
  `ProductCatalogued`'s correction note above.
- Emitted when: an already-catalogued product's data changes on a
  subsequent ingestion pass (the same source re-syncing, or a second
  source's data reconciling into the row per the dedup/conflict-
  resolution rule: barcode is the sole cross-source dedup key; on a
  numeric disagreement, the most-recently-updated source wins on the
  live row, both sources' raw values are retained in `product_sources`).
  Never published with an empty `changed_fields` — that is a no-op
  ingestion pass, not an update.
- Payload: same shape as `ProductCatalogued` plus
  `"changed_fields": ["string"]` (non-empty). See
  `packages/shared-contracts/schemas/product_updated.v1.json`.

### FoodEntryLogged (v1)
- Status: Active
- Producer: diary-service
- Consumers: nutrition-calculation-service, analytics-service (both
  documented, neither exists yet -- no live cross-service contract test
  runs against them, only a payload-shape contract test against this
  entry, per `/plans/diary-service/implementation-plan.md` section 5/6).
- Emitted when: a user logs a food entry against a `catalog-service`
  product reference or (reserved, not yet exercised) a `recipe`/
  `ai_detected` source.
- Aggregate: FoodEntry -- one instance per logged item (`aggregate_id =
  entry_id`).
- Payload: `{ "entry_id": "uuid", "user_id": "uuid",
  "source": { "source_type": "catalog_product|recipe|ai_detected",
  "source_reference_id": "string", "snapshot": { "name": "string",
  "brand": "string | null", "quantity": "number", "unit": "g|ml|serving",
  "macros_per_unit": { "calories_kcal": "number", "protein_g": "number",
  "carbs_g": "number", "fat_g": "number" } } }, "meal_slot":
  "breakfast|lunch|dinner|snack", "occurred_at": "timestamp",
  "planned_from_entry_id": "uuid | null" }` -- `source` is a client-supplied,
  point-in-time snapshot; diary-service makes no synchronous call to
  `catalog-service` to validate it (settled scoping decision, plan
  section 1). `planned_from_entry_id` is an additive, unused
  forward-compatibility seam (plan section 9.3) for a future "log from
  plan" workflow.

### FoodEntryCorrected (v1)
- Status: Active
- Producer: diary-service
- Consumers: nutrition-calculation-service, analytics-service (documented,
  not yet existing).
- Emitted when: a user corrects a previously logged food entry. Never
  mutates the original `FoodEntryLogged` event -- a projector interprets
  the pair (CLAUDE.md: corrections are new events, never edits to history).
- Aggregate: FoodEntry.
- Payload: same shape as `FoodEntryLogged`'s `source`/`meal_slot`/
  `occurred_at` (full replacement of the correctable fields), plus
  `corrected_at`: `{ "entry_id": "uuid", "user_id": "uuid", "source": {...},
  "meal_slot": "string", "occurred_at": "timestamp", "corrected_at": "timestamp" }`

### FoodEntryDeleted (v1)
- Status: Active
- Producer: diary-service
- Consumers: nutrition-calculation-service, analytics-service (documented,
  not yet existing).
- Emitted when: a user deletes a previously logged food entry. Never a
  destructive row delete -- a new event a projector interprets.
- Aggregate: FoodEntry.
- Payload: `{ "entry_id": "uuid", "user_id": "uuid", "deleted_at": "timestamp" }`

### WaterIntakeLogged (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service (documented, not yet existing).
- Emitted when: a user logs water intake.
- Aggregate: WaterIntakeEntry -- one instance per logged item
  (`aggregate_id = intake_id`).
- Payload: `{ "intake_id": "uuid", "user_id": "uuid", "amount_ml": "number",
  "occurred_at": "timestamp" }`

### WaterIntakeRemoved (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service (documented, not yet existing).
- Emitted when: a user removes a previously logged water intake entry.
  Never a destructive row delete.
- Aggregate: WaterIntakeEntry.
- Payload: `{ "intake_id": "uuid", "user_id": "uuid", "removed_at": "timestamp" }`

### FastingWindowStarted (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service, notification-service (reminders) --
  documented, not yet existing.
- Emitted when: a user starts a fasting window. Rejected (no event
  produced) if the user already has an open window --
  `OverlappingFastingWindowError` (plan section 9.2's resolved simple
  open-window check).
- Aggregate: FastingWindow -- one instance **per user**, holding that
  user's set of fasting windows as entities within the aggregate (the one
  aggregate in this service requiring a cross-instance invariant,
  `aggregate_id = user_id`).
- Payload: `{ "window_id": "uuid", "user_id": "uuid", "started_at": "timestamp" }`

### FastingWindowEnded (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service, notification-service (reminders) --
  documented, not yet existing.
- Emitted when: a user ends their open fasting window.
- Aggregate: FastingWindow.
- Payload: `{ "window_id": "uuid", "user_id": "uuid", "ended_at": "timestamp" }`

### MealPlanned (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service (documented, not yet existing).
- Emitted when: a user schedules a planned (future) meal entry -- distinct
  from the as-eaten `FoodEntryLogged` log (weekly meal planning, plan
  section 1).
- Aggregate: MealPlanEntry -- one instance per planned item
  (`aggregate_id = plan_entry_id`).
- Payload: same `source`/`meal_slot` shape as `FoodEntryLogged`, plus
  `planned_for` instead of `occurred_at`: `{ "plan_entry_id": "uuid",
  "user_id": "uuid", "source": {...}, "meal_slot": "string",
  "planned_for": "timestamp" }`

### MealPlanUpdated (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service (documented, not yet existing).
- Emitted when: a user updates a planned meal entry. Never mutates the
  original `MealPlanned` event.
- Aggregate: MealPlanEntry.
- Payload: same shape as `MealPlanned` plus `updated_at`: `{ "plan_entry_id":
  "uuid", "user_id": "uuid", "source": {...}, "meal_slot": "string",
  "planned_for": "timestamp", "updated_at": "timestamp" }`

### MealPlanRemoved (v1)
- Status: Active
- Producer: diary-service
- Consumers: analytics-service (documented, not yet existing).
- Emitted when: a user removes a planned meal entry. Never a destructive
  row delete.
- Aggregate: MealPlanEntry.
- Payload: `{ "plan_entry_id": "uuid", "user_id": "uuid", "removed_at": "timestamp" }`

### ProfileCreated (v1)
- Status: Active
- Producer: profile-service
- Consumers: none yet (internal to profile-service's own event-sourced
  aggregate; not a documented cross-service contract).
- Emitted when: profile-service reactively creates an empty profile
  aggregate for a `user_id`, in response to consuming identity-service's
  `UserRegistered` (v1). No synchronous call back to identity-service.
- Payload: `{ "user_id": "uuid", "created_at": "timestamp" }`

### BiometricConsentGranted (v1)
- Status: Active
- Producer: profile-service
- Consumers: none yet (internal).
- Emitted when: a user grants explicit, specific consent to collect
  biometric/health data (CLAUDE.md section 8) -- required before any
  metric-recording event can be produced for that user.
- Payload: `{ "user_id": "uuid", "granted_at": "timestamp" }`

### WeightRecorded (v1)
- Status: Active
- Producer: profile-service
- Consumers: nutrition-calculation-service, analytics-service (both
  documented, neither exists yet -- no live cross-service contract test
  runs against them, only a payload-shape contract test against this
  entry).
- Emitted when: a user records a weight reading (consent-gated).
- Payload: `{ "user_id": "uuid", "weight_kg": "string (AES-256-GCM
  ciphertext, base64 -- per-user envelope-encrypted, GDPR Article 9
  special-category data, implementation plan Addendum 1)",
  "recorded_at": "timestamp" }`

### BodyMetricRecorded (v1)
- Status: Active
- Producer: profile-service
- Consumers: nutrition-calculation-service, analytics-service (documented,
  not yet existing).
- Emitted when: a user records height, age, sex, or activity level
  (consent-gated).
- Payload: `{ "user_id": "uuid", "metric_type": "height|age|sex|activity_level",
  "value": "string (AES-256-GCM ciphertext, base64 -- per-user
  envelope-encrypted)", "recorded_at": "timestamp" }`

### GoalSet (v1)
- Status: Active
- Producer: profile-service
- Consumers: nutrition-calculation-service, analytics-service (documented,
  not yet existing).
- Emitted when: a user sets their goal for the first time (`set_goal` is
  create-only -- `GoalUpdated` is the only path to change an existing
  goal).
- Payload: `{ "user_id": "uuid", "goal_type": "LOSE|MAINTAIN|GAIN",
  "target_value": "string (AES-256-GCM ciphertext, base64) | null",
  "target_date": "date | null", "set_at": "timestamp" }` -- `target_value`
  is encrypted (health-adjacent data, same reasoning as the metrics
  above); `goal_type`/`target_date` stay in clear, needed for
  `goal_policy` evaluation and query filtering.

### GoalUpdated (v1)
- Status: Active
- Producer: profile-service
- Consumers: nutrition-calculation-service, analytics-service (documented,
  not yet existing).
- Emitted when: a user changes an existing goal.
- Payload: same shape as `GoalSet` plus `previous_goal_type`:
  `{ "user_id": "uuid", "goal_type": "LOSE|MAINTAIN|GAIN",
  "target_value": "string (ciphertext) | null", "target_date": "date | null",
  "set_at": "timestamp", "previous_goal_type": "LOSE|MAINTAIN|GAIN" }`

### FoodPhotoAnalyzed (v1)
- Status: Active
- Producer: food-recognition-service
- Consumers: diary-service (documented, to pre-fill an entry for user
  confirmation; not a live consumer yet -- no live integration breaks from
  this shape, food-recognition-service's implementation plan is this
  payload's first concrete definition, superseding the earlier
  placeholder shape below).
- Emitted when: an uploaded food photo has been analyzed, via the Outbox,
  after **every** analysis attempt -- including failed/unavailable ones
  (an audit trail of the failure itself is a useful signal). Barcode scans
  publish no event (food-recognition-service implementation plan section
  1, acceptance criterion 4 -- either the barcode matched a catalog
  product or it didn't, no ambiguity for a downstream consumer to
  resolve).
- Payload: `{ "analysis_id": "uuid", "candidates": [ { "name": "string",
  "portion_range_min_g": "number", "portion_range_max_g": "number",
  "confidence": "number" } ] (max 3 items), "model_version": "string",
  "status": "detected | uncertain | unavailable" }`. `user_id` is carried
  in the envelope's `metadata.user_id`, not the payload itself. Every
  portion estimate is a genuine range (`min_g < max_g`), never a single
  precise number (media-recognition-conventions SKILL.md). See
  `packages/shared-contracts/schemas/food_photo_analyzed.v1.json`.

### NutritionValueRecomputed (v1)
- Status: Active
- Producer: nutrition-calculation-service
- Consumers: analytics-service, nutrition-assistant-service (documented,
  neither exists yet -- no live cross-service contract test runs against
  them, only a payload-shape contract test against this entry).
- Emitted when: a user's per-entry or per-day nutrient total changes,
  triggered by `FoodEntryLogged`/`FoodEntryCorrected`/`FoodEntryDeleted`
  (diary-service) or (reserved, not built this pass) a formula correction.
  `confidence_range` is always `null` this pass (reserved seam for
  food-recognition-service's AI-estimated confidence range, implementation
  plan section 1).
- Payload: `{ "user_id": "uuid", "scope": "entry | day", "entry_id": "uuid | null",
  "date": "date | null", "macros": { "calories_kcal": "number", "protein_g": "number",
  "carbs_g": "number", "fat_g": "number" }, "micronutrients": { "...": "number | null" } | null,
  "micronutrients_status": "available | partial | unavailable", "is_estimated": "boolean",
  "confidence_range": { "min": "number", "max": "number" } | null, "formula_version": "string",
  "reason": "food_entry_logged | food_entry_corrected | food_entry_deleted | formula_correction",
  "recomputed_at": "timestamp" }`. See
  `packages/shared-contracts/schemas/nutrition_value_recomputed.v1.json`.

### NutritionTargetUpdated (v1)
- Status: Active
- Producer: nutrition-calculation-service
- Consumers: analytics-service, nutrition-assistant-service (documented,
  neither exists yet -- no live cross-service contract test runs against
  them, only a payload-shape contract test against this entry).
- Emitted when: a user's calculated calorie/macro target changes,
  triggered by `WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/`GoalUpdated`
  (profile-service, via the internal reveal endpoint per implementation
  plan Addendum 1 -- these trigger events are never decrypted by
  nutrition-calculation-service itself) or (reserved, not built this pass)
  a formula correction. `activity_adjustment_kcal` is always `null` this
  pass (reserved seam for activity-service).
- Payload: `{ "user_id": "uuid", "bmr_kcal": "number", "tdee_kcal": "number",
  "calorie_target_kcal": "number", "macro_targets": { "protein_g_min": "number",
  "protein_g_max": "number", "fat_g_min": "number", "carbs_g": "number" },
  "goal_type": "LOSE | MAINTAIN | GAIN",
  "activity_level": "SEDENTARY | LIGHT | MODERATE | ACTIVE | VERY_ACTIVE",
  "activity_adjustment_kcal": "number | null", "clamped": "boolean",
  "clamp_reason": "string | null", "formula_version": "string",
  "reason": "weight_recorded | body_metric_recorded | goal_set | goal_updated | formula_correction",
  "effective_from": "timestamp" }`. See
  `packages/shared-contracts/schemas/nutrition_target_updated.v1.json`.

### ExerciseLogged / WearableActivitySynced (v1)
- Producer: activity-service
- Consumers: nutrition-calculation-service, analytics-service
- Emitted when: a user manually logs exercise, or a wearable sync
  completes.

### RecipeCreated / RecipeUpdated / RecipePublished (v1)
- Producer: recipe-service
- Consumers: analytics-service, nutrition-assistant-service
- Emitted when: a user authors, edits, or publishes a recipe (publish is
  Pro-gated — see `SubscriptionStarted`/`EntitlementGranted` below).

### UserFollowed / UserUnfollowed (v1)
- Producer: social-service
- Consumers: notification-service, analytics-service
- Emitted when: a user follows/unfollows another user (Pro-gated).

### SubscriptionStarted / SubscriptionRenewed / SubscriptionCancelled / SubscriptionPaymentFailed / EntitlementGranted / EntitlementRevoked (v1)
- Producer: billing-service
- Consumers: recipe-service, social-service, analytics-service
  (cache the entitlement flag locally per `.claude/skills/saga-conventions/SKILL.md`)
- Emitted when: the corresponding subscription/payment/entitlement
  lifecycle event happens.

### NutrientDeficiencyDetected (v1)
- Producer: analytics-service
- Consumers: nutrition-assistant-service (to proactively surface it),
  notification-service (opt-in alert)
- Emitted when: a recurring nutrient-deficiency pattern or threshold
  breach is detected over a rolling window.
- Payload: `{ "user_id": "uuid", "signal": "string", "window_days": "number",
  "value": "number" }`

---

Add new entries above this line as new events are introduced. Do not remove
entries for deprecated events — mark them `Status: Deprecated` and note the
replacement instead, so historical events already in the store remain
documented.
