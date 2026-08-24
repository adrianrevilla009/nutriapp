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

## Planned Events (to be implemented with each service's first version)

### UserRegistered (v1)
- Producer: identity-service
- Consumers: profile-service (to create the user's profile), diary-service,
  any service that needs to initialize a per-user context
- Emitted when: a new user completes registration.
- Payload: `{ "user_id": "uuid", "email": "string", "registered_at": "timestamp" }`

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

### WeightRecorded / BodyMetricRecorded / GoalSet / GoalUpdated (v1)
- Producer: profile-service
- Consumers: nutrition-calculation-service, analytics-service
- Emitted when: a user records a biometric metric or sets/changes their goal.
- Payload: `{ "user_id": "uuid", "metric": "string", "value": "number",
  "recorded_at": "timestamp" }`

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
