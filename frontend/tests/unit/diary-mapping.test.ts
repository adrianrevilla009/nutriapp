import { describe, expect, it } from "vitest";
import { productToLogFoodEntryRequest } from "@/lib/diary-mapping";
import {
  productWithNutritionFixture,
  productWithoutNutritionFixture,
} from "../fixtures/catalog.fixtures";

const occurredAt = new Date("2026-09-08T08:00:00.000Z");

describe("productToLogFoodEntryRequest", () => {
  it("copies nutrition_per_100g into macros_per_unit unchanged", () => {
    const result = productToLogFoodEntryRequest(
      productWithNutritionFixture,
      150,
      "breakfast",
      occurredAt,
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.source.snapshot.macros_per_unit).toEqual({
      calories_kcal: productWithNutritionFixture.nutrition_per_100g!.energy_kcal,
      protein_g: productWithNutritionFixture.nutrition_per_100g!.protein_g,
      carbs_g: productWithNutritionFixture.nutrition_per_100g!.carbohydrates_g,
      fat_g: productWithNutritionFixture.nutrition_per_100g!.fat_g,
    });
  });

  it("fixes unit to 'g' and sets source_type/source_reference_id from the product", () => {
    const result = productToLogFoodEntryRequest(
      productWithNutritionFixture,
      150,
      "lunch",
      occurredAt,
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.source.snapshot.unit).toBe("g");
    expect(result.request.source.source_type).toBe("catalog_product");
    expect(result.request.source.source_reference_id).toBe(productWithNutritionFixture.product_id);
    expect(result.request.source.snapshot.quantity).toBe(150);
    expect(result.request.meal_slot).toBe("lunch");
  });

  it("serializes occurred_at as an ISO string, not a Date object", () => {
    const result = productToLogFoodEntryRequest(
      productWithNutritionFixture,
      150,
      "breakfast",
      occurredAt,
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(typeof result.request.occurred_at).toBe("string");
    expect(result.request.occurred_at).toBe(occurredAt.toISOString());
  });

  it("returns {ok: false, reason: 'no_nutrition_data'} when nutrition_per_100g is null, never fabricating macros", () => {
    const result = productToLogFoodEntryRequest(
      productWithoutNutritionFixture,
      150,
      "breakfast",
      occurredAt,
    );
    expect(result).toEqual({ ok: false, reason: "no_nutrition_data" });
  });

  it("returns not-ok when the panel exists but a required macro field is null", () => {
    const partiallyNull = {
      ...productWithNutritionFixture,
      nutrition_per_100g: {
        ...productWithNutritionFixture.nutrition_per_100g!,
        protein_g: null,
      },
    };
    const result = productToLogFoodEntryRequest(partiallyNull, 150, "breakfast", occurredAt);
    expect(result).toEqual({ ok: false, reason: "no_nutrition_data" });
  });
});
