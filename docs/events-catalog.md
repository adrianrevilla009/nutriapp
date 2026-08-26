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

### ProductAdded / ProductUpdated (v1)
- Producer: catalog-service
- Consumers: diary-service (documented future consumer -- deliberately
  **not built** by `diary-service`'s reference implementation plan;
  `FoodEntryLogged`/`MealPlanned`'s `source.snapshot` is a client-supplied,
  point-in-time record of what the user logged, not a live mirror of the
  catalog, so silently reconciling it against a later `ProductUpdated`
  may be the wrong behavior, not merely a deferred one -- see
  `/plans/diary-service/implementation-plan.md` section 9.4), food-recognition-service
  (for barcode/product matching), recipe-service
- Emitted when: a new product is added, or an existing product's data
  changes, via ingestion or manual curation.
- Payload: `{ "product_id": "uuid", "name": "string", "barcode": "string | null",
  "nutrition_per_100g": { "...": "macro/micro fields" }, "source": "string" }`

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
- Producer: food-recognition-service
- Consumers: diary-service (to pre-fill an entry for user confirmation)
- Emitted when: an uploaded food photo or barcode scan has been processed.
- Payload: `{ "detection_id": "uuid", "user_id": "uuid",
  "detected_items": [ { "product_id": "uuid | null", "label": "string",
  "confidence": "number" } ] }`

### NutritionTargetUpdated / NutritionValueRecomputed (v1)
- Producer: nutrition-calculation-service
- Consumers: analytics-service, nutrition-assistant-service
- Emitted when: a user's calculated calorie/macro target or a nutrient
  total changes.
- Payload: `{ "user_id": "uuid", "value": "...", "reason": "string",
  "effective_from": "timestamp" }`

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
