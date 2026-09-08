/**
 * Fixture shaped from
 * services/diary-service/infrastructure/http/schemas/diary_schemas.py's
 * FoodEntryResponse (read verbatim during /implementation-plan's research).
 * Test-plan section 4/8.
 */
import type { FoodEntryResponse } from "@/schemas/diary";

export const foodEntryResponseFixture: FoodEntryResponse = {
  entry_id: "44444444-4444-4444-8444-444444444444",
  user_id: "11111111-1111-4111-8111-111111111111",
  source: {
    source_type: "catalog_product",
    source_reference_id: "22222222-2222-4222-8222-222222222222",
    snapshot: {
      name: "Plain Yogurt",
      brand: "Acme Dairy",
      quantity: 150,
      unit: "g",
      macros_per_unit: {
        calories_kcal: 61,
        protein_g: 3.5,
        carbs_g: 4.7,
        fat_g: 3.3,
      },
    },
  },
  meal_slot: "breakfast",
  occurred_at: "2026-09-08T08:00:00+00:00",
};
