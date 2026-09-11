import { describe, expect, it } from "vitest";
import {
  canSubmitRecipe,
  ingredientRowsToRequest,
  parseQuantityGrams,
  type IngredientRowState,
} from "@/lib/recipe-ingredients";

function row(overrides: Partial<IngredientRowState> = {}): IngredientRowState {
  return {
    rowId: "row-1",
    productId: "22222222-2222-4222-8222-222222222222",
    productName: "Plain Yogurt",
    quantityGramsInput: "150",
    ...overrides,
  };
}

describe("parseQuantityGrams", () => {
  it("parses a valid positive number string", () => {
    expect(parseQuantityGrams("150")).toBe(150);
  });

  it("rejects an empty string", () => {
    expect(parseQuantityGrams("")).toBeNull();
  });

  it("rejects a non-numeric string", () => {
    expect(parseQuantityGrams("abc")).toBeNull();
  });

  it("rejects zero", () => {
    expect(parseQuantityGrams("0")).toBeNull();
  });

  it("rejects a negative number", () => {
    expect(parseQuantityGrams("-5")).toBeNull();
  });
});

describe("canSubmitRecipe", () => {
  it("returns false for an empty ingredient list", () => {
    expect(canSubmitRecipe([])).toBe(false);
  });

  it("returns true for one valid row", () => {
    expect(canSubmitRecipe([row()])).toBe(true);
  });

  it("returns false when any row has an invalid quantity", () => {
    expect(canSubmitRecipe([row(), row({ rowId: "row-2", quantityGramsInput: "0" })])).toBe(false);
  });

  it("returns true for two rows referencing the SAME product (duplicate selection is allowed, never merged)", () => {
    // Resolved empirically against RecipeIngredient's actual invariants
    // (domain/value_objects/recipe_ingredient.py has no uniqueness check) --
    // documented in lib/recipe-ingredients.ts's IngredientRowState comment.
    const rows = [
      row({ rowId: "row-1" }),
      row({ rowId: "row-2", productId: row().productId, quantityGramsInput: "50" }),
    ];
    expect(canSubmitRecipe(rows)).toBe(true);
    expect(ingredientRowsToRequest(rows)).toHaveLength(2);
  });
});

describe("ingredientRowsToRequest", () => {
  it("maps rows to the exact backend request shape", () => {
    expect(ingredientRowsToRequest([row()])).toEqual([
      { catalog_product_id: "22222222-2222-4222-8222-222222222222", quantity_grams: 150 },
    ]);
  });

  it("maps an invalid-quantity row to 0 rather than throwing (the UI blocks submit before this is ever called on invalid rows)", () => {
    expect(ingredientRowsToRequest([row({ quantityGramsInput: "not-a-number" })])).toEqual([
      { catalog_product_id: "22222222-2222-4222-8222-222222222222", quantity_grams: 0 },
    ]);
  });
});
