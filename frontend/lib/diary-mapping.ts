/**
 * Pure mapping helper backing components/features/diary/LogFoodEntryForm.tsx
 * (test-plan section 2). Converts a searched catalog product + user-entered
 * quantity into diary-service's LogFoodEntryRequest shape.
 *
 * Grounded semantics (implementation plan section 4,
 * nutrition-calculation-service/domain/services/nutrient_total_calculator.py):
 * `macros_per_unit` is treated system-wide as PER-100g values, and
 * `quantity`/`unit` is the amount consumed -- this helper fixes `unit: "g"`
 * (no serving-size UI this pass) and copies the product's `nutrition_per_100g`
 * into `macros_per_unit` completely unchanged.
 */
import type { ProductResponse } from "@/schemas/catalog";
import type { LogFoodEntryRequest, MealSlot } from "@/schemas/diary";

export type MapProductToLogRequestResult =
  | { ok: true; request: LogFoodEntryRequest }
  | { ok: false; reason: "no_nutrition_data" };

/**
 * Journey 2 addition: when a food entry originates from an AI photo
 * detection (rather than a plain catalog search), source_type/
 * source_reference_id are overridden to "ai_detected"/the food-recognition
 * analysis_id -- everything else (the "never fabricate macros" guard
 * below, snapshot.name/brand/macros_per_unit from the matched product)
 * is UNCHANGED and shared by both call shapes. This is the one code path
 * both journey 1's catalog flow and journey 2's AI-confirm flow go
 * through -- there is no parallel mapping function that could silently
 * drift out of sync with this one's fabrication guard.
 */
export interface FoodSourceOverride {
  source_type: "ai_detected";
  source_reference_id: string;
}

export function productToLogFoodEntryRequest(
  product: ProductResponse,
  quantityGrams: number,
  mealSlot: MealSlot,
  occurredAt: Date,
  sourceOverride?: FoodSourceOverride,
): MapProductToLogRequestResult {
  // A real, allowed backend shape (product_schemas.py's
  // `nutrition_per_100g: NutrientPanelResponse | None`) -- never fabricate
  // or zero-fill macros when it's absent; the caller must surface this as
  // a blocking state (test-plan section 2/3).
  if (product.nutrition_per_100g === null) {
    return { ok: false, reason: "no_nutrition_data" };
  }
  const panel = product.nutrition_per_100g;
  // A product's nutrient panel fields are independently nullable even when
  // the panel itself exists; the four macro fields diary-service actually
  // requires must all be present, or this product can't be logged either --
  // same "never fabricate/zero-fill" rule applies field-by-field.
  if (
    panel.energy_kcal === null ||
    panel.protein_g === null ||
    panel.carbohydrates_g === null ||
    panel.fat_g === null
  ) {
    return { ok: false, reason: "no_nutrition_data" };
  }

  const request: LogFoodEntryRequest = {
    source: {
      source_type: sourceOverride?.source_type ?? "catalog_product",
      source_reference_id: sourceOverride?.source_reference_id ?? product.product_id,
      snapshot: {
        name: product.name ?? "Unnamed product",
        brand: product.brand ?? null,
        quantity: quantityGrams,
        unit: "g",
        macros_per_unit: {
          calories_kcal: panel.energy_kcal,
          protein_g: panel.protein_g,
          carbs_g: panel.carbohydrates_g,
          fat_g: panel.fat_g,
        },
      },
    },
    meal_slot: mealSlot,
    occurred_at: occurredAt.toISOString(),
  };
  return { ok: true, request };
}
