import { describe, expect, it } from "vitest";
import { ProductResponseSchema, ProductSearchResponseSchema } from "@/schemas/catalog";
import {
  emptyProductSearchResponseFixture,
  productSearchResponseFixture,
  productWithNutritionFixture,
  productWithoutNutritionFixture,
} from "../fixtures/catalog.fixtures";

describe("ProductResponseSchema", () => {
  it("parses a fully-populated product", () => {
    expect(ProductResponseSchema.parse(productWithNutritionFixture)).toEqual(
      productWithNutritionFixture,
    );
  });

  it("parses a product with every optional field null", () => {
    expect(ProductResponseSchema.parse(productWithoutNutritionFixture)).toEqual(
      productWithoutNutritionFixture,
    );
  });

  it("accepts a nutrient panel with only some fields populated", () => {
    const partial = {
      ...productWithNutritionFixture,
      nutrition_per_100g: {
        ...productWithNutritionFixture.nutrition_per_100g!,
        fiber_g: null,
        vitamin_c_mg: null,
      },
    };
    expect(() => ProductResponseSchema.parse(partial)).not.toThrow();
  });
});

describe("ProductSearchResponseSchema", () => {
  it("parses a populated search page", () => {
    expect(ProductSearchResponseSchema.parse(productSearchResponseFixture)).toEqual(
      productSearchResponseFixture,
    );
  });

  it("parses an empty result page (total: 0)", () => {
    expect(ProductSearchResponseSchema.parse(emptyProductSearchResponseFixture)).toEqual(
      emptyProductSearchResponseFixture,
    );
  });
});
