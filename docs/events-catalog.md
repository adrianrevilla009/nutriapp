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
- Consumers: diary-service, food-recognition-service (for barcode/product
  matching), recipe-service
- Emitted when: a new product is added, or an existing product's data
  changes, via ingestion or manual curation.
- Payload: `{ "product_id": "uuid", "name": "string", "barcode": "string | null",
  "nutrition_per_100g": { "...": "macro/micro fields" }, "source": "string" }`

### FoodEntryLogged / FoodEntryCorrected / FoodEntryDeleted (v1)
- Producer: diary-service
- Consumers: nutrition-calculation-service, analytics-service,
  nutrition-assistant-service (for retrieval indexing)
- Emitted when: a user logs, corrects, or deletes a food entry.
- Payload: `{ "entry_id": "uuid", "user_id": "uuid", "product_id": "uuid | null",
  "detection_id": "uuid | null", "quantity_grams": "number", "meal_slot": "string",
  "occurred_at": "timestamp" }`

### WaterIntakeLogged / FastingWindowStarted / FastingWindowEnded / MealPlanned (v1)
- Producer: diary-service
- Consumers: analytics-service, notification-service (reminders)
- Emitted when: the corresponding diary action happens.

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
