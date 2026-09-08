/**
 * Zod schemas mirroring
 * services/diary-service/infrastructure/http/schemas/diary_schemas.py and
 * domain/value_objects/{macro_snapshot,food_source,meal_slot}.py
 * field-for-field, scoped to only the food-entry-logging surface journey 1
 * needs (diary-service exposes water/fasting/meal-plan routes too -- out of
 * scope, per the implementation plan).
 */
import { z } from "zod";

// Mirrors domain/value_objects/meal_slot.py's MealSlot enum exactly.
export const MealSlotSchema = z.enum(["breakfast", "lunch", "dinner", "snack"]);
export type MealSlot = z.infer<typeof MealSlotSchema>;

// Mirrors MacroSnapshotSchema -- MacroSnapshot.__post_init__ rejects any
// negative field (domain/value_objects/macro_snapshot.py).
export const MacroSnapshotSchema = z.object({
  calories_kcal: z.number().nonnegative(),
  protein_g: z.number().nonnegative(),
  carbs_g: z.number().nonnegative(),
  fat_g: z.number().nonnegative(),
});
export type MacroSnapshot = z.infer<typeof MacroSnapshotSchema>;

// Mirrors FoodSourceSnapshotSchema -- quantity is `Field(gt=0)` on the
// backend (domain/value_objects/food_source.py delegates to Quantity's
// invariant).
export const FoodSourceSnapshotSchema = z.object({
  name: z.string().min(1),
  brand: z.string().nullable().optional(),
  quantity: z.number().positive(),
  unit: z.string().min(1),
  macros_per_unit: MacroSnapshotSchema,
});
export type FoodSourceSnapshot = z.infer<typeof FoodSourceSnapshotSchema>;

// Mirrors FoodSourceSchema -- source_type is one of catalog_product |
// recipe | ai_detected on the backend (domain SUPPORTED_SOURCE_TYPES);
// this frontend only ever constructs "catalog_product" this pass, but the
// wire schema stays permissive to the full backend-supported set so a
// future feature doesn't need a schema change here.
export const FoodSourceSchema = z.object({
  source_type: z.enum(["catalog_product", "recipe", "ai_detected"]),
  source_reference_id: z.string().min(1),
  snapshot: FoodSourceSnapshotSchema,
});
export type FoodSource = z.infer<typeof FoodSourceSchema>;

// Mirrors LogFoodEntryRequest. occurred_at MUST be an ISO-8601 datetime
// STRING at this boundary (never a `Date` object) -- the mapping helper in
// lib/diary-mapping.ts is responsible for calling `.toISOString()` before
// this schema ever sees the value (test-plan section 1).
export const LogFoodEntryRequestSchema = z.object({
  source: FoodSourceSchema,
  meal_slot: MealSlotSchema,
  // `offset: true` -- FastAPI/Pydantic serializes a timezone-aware
  // datetime with a numeric offset (e.g. "+00:00"), not necessarily a
  // literal "Z" suffix; Zod's default `.datetime()` only accepts "Z".
  occurred_at: z.string().datetime({ offset: true }),
});
export type LogFoodEntryRequest = z.infer<typeof LogFoodEntryRequestSchema>;

// Mirrors FoodEntryResponse.
export const FoodEntryResponseSchema = z.object({
  entry_id: z.string().uuid(),
  user_id: z.string().uuid(),
  source: FoodSourceSchema,
  meal_slot: MealSlotSchema,
  occurred_at: z.string().datetime({ offset: true }),
});
export type FoodEntryResponse = z.infer<typeof FoodEntryResponseSchema>;
