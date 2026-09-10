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

  // Journey 2: the sourceOverride branch (AI-detected logging).
  const aiSourceOverride = {
    source_type: "ai_detected" as const,
    source_reference_id: "55555555-5555-4555-8555-555555555555",
  };

  it("with sourceOverride, sets source_type/source_reference_id from the override, not the product", () => {
    const result = productToLogFoodEntryRequest(
      productWithNutritionFixture,
      150,
      "breakfast",
      occurredAt,
      aiSourceOverride,
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.source.source_type).toBe("ai_detected");
    expect(result.request.source.source_reference_id).toBe(aiSourceOverride.source_reference_id);
  });

  it("with sourceOverride, snapshot.name/brand/macros_per_unit still come from the matched product, never fabricated", () => {
    const result = productToLogFoodEntryRequest(
      productWithNutritionFixture,
      150,
      "breakfast",
      occurredAt,
      aiSourceOverride,
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.source.snapshot.name).toBe(productWithNutritionFixture.name);
    expect(result.request.source.snapshot.brand).toBe(productWithNutritionFixture.brand);
    expect(result.request.source.snapshot.macros_per_unit).toEqual({
      calories_kcal: productWithNutritionFixture.nutrition_per_100g!.energy_kcal,
      protein_g: productWithNutritionFixture.nutrition_per_100g!.protein_g,
      carbs_g: productWithNutritionFixture.nutrition_per_100g!.carbohydrates_g,
      fat_g: productWithNutritionFixture.nutrition_per_100g!.fat_g,
    });
  });

  // The single most important test in this journey's plan (test-plan
  // section 2): the "never fabricate macros" guard is ONE code path,
  // identical whether sourceOverride is set or not -- run as one
  // parameterized case against both branches with the same assertion
  // body, so they cannot silently drift apart from each other later.
  it.each([
    { label: "without sourceOverride (catalog_product)", sourceOverride: undefined },
    { label: "with sourceOverride (ai_detected)", sourceOverride: aiSourceOverride },
  ])("blocks on a product with no nutrition data identically $label", ({ sourceOverride }) => {
    const result = productToLogFoodEntryRequest(
      productWithoutNutritionFixture,
      150,
      "breakfast",
      occurredAt,
      sourceOverride,
    );
    expect(result).toEqual({ ok: false, reason: "no_nutrition_data" });
  });

  it("quantity/unit are unchanged regardless of sourceOverride", () => {
    const result = productToLogFoodEntryRequest(
      productWithNutritionFixture,
      200,
      "dinner",
      occurredAt,
      aiSourceOverride,
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.request.source.snapshot.quantity).toBe(200);
    expect(result.request.source.snapshot.unit).toBe("g");
    expect(result.request.meal_slot).toBe("dinner");
  });
});
