import { describe, expect, it } from "vitest";
import {
  NutrientStatusSchema,
  RecipeIngredientRequestSchema,
  RecipeListResponseSchema,
  RecipeMutationRequestSchema,
  RecipeResponseSchema,
} from "@/schemas/recipe";
import { draftRecipeFixture, publishedRecipeFixture } from "../fixtures/recipe.fixtures";

describe("RecipeIngredientRequestSchema", () => {
  it("parses a valid ingredient line", () => {
    const ingredient = {
      catalog_product_id: "22222222-2222-4222-8222-222222222222",
      quantity_grams: 150,
    };
    expect(RecipeIngredientRequestSchema.parse(ingredient)).toEqual(ingredient);
  });

  it("rejects quantity_grams of 0", () => {
    expect(() =>
      RecipeIngredientRequestSchema.parse({
        catalog_product_id: "22222222-2222-4222-8222-222222222222",
        quantity_grams: 0,
      }),
    ).toThrow();
  });

  it("rejects a negative quantity_grams", () => {
    expect(() =>
      RecipeIngredientRequestSchema.parse({
        catalog_product_id: "22222222-2222-4222-8222-222222222222",
        quantity_grams: -5,
      }),
    ).toThrow();
  });
});

describe("RecipeMutationRequestSchema", () => {
  it("parses a request with ingredients", () => {
    const request = {
      title: "Yogurt Bowl",
      instructions: "Combine yogurt and toppings in a bowl.",
      servings: 2,
      ingredients: [
        { catalog_product_id: "22222222-2222-4222-8222-222222222222", quantity_grams: 200 },
      ],
    };
    expect(RecipeMutationRequestSchema.parse(request)).toEqual(request);
  });

  // The backend has NO minimum-ingredient invariant (confirmed by reading
  // domain/entities/recipe.py directly) -- this schema deliberately does
  // not add one either; the >=1 UI guard lives in
  // lib/recipe-ingredients.ts's canSubmitRecipe instead.
  it("allows an empty ingredients array at the schema level", () => {
    const request = {
      title: "Empty Recipe",
      instructions: "Nothing yet.",
      servings: 1,
      ingredients: [],
    };
    expect(() => RecipeMutationRequestSchema.parse(request)).not.toThrow();
  });

  it("rejects a non-positive servings value", () => {
    expect(() =>
      RecipeMutationRequestSchema.parse({
        title: "x",
        instructions: "x",
        servings: 0,
        ingredients: [],
      }),
    ).toThrow();
  });

  it("rejects an empty title", () => {
    expect(() =>
      RecipeMutationRequestSchema.parse({
        title: "",
        instructions: "x",
        servings: 1,
        ingredients: [],
      }),
    ).toThrow();
  });
});

describe("NutrientStatusSchema", () => {
  it("accepts available/partial/unavailable", () => {
    expect(NutrientStatusSchema.parse("available")).toBe("available");
    expect(NutrientStatusSchema.parse("partial")).toBe("partial");
    expect(NutrientStatusSchema.parse("unavailable")).toBe("unavailable");
  });

  it("rejects any other string", () => {
    expect(() => NutrientStatusSchema.parse("complete")).toThrow();
  });
});

describe("RecipeResponseSchema", () => {
  it("parses a draft recipe", () => {
    expect(RecipeResponseSchema.parse(draftRecipeFixture)).toEqual(draftRecipeFixture);
  });

  it("parses a published recipe (unpublished_at null)", () => {
    expect(RecipeResponseSchema.parse(publishedRecipeFixture)).toEqual(publishedRecipeFixture);
  });

  it("parses a recipe with a real unpublished_at timestamp", () => {
    const unpublished = {
      ...draftRecipeFixture,
      is_published: false,
      unpublished_at: "2026-09-11T09:00:00+00:00",
    };
    expect(() => RecipeResponseSchema.parse(unpublished)).not.toThrow();
  });

  it("parses a recipe whose micronutrients are null (unavailable status)", () => {
    const noMicros = {
      ...draftRecipeFixture,
      computed_totals: {
        per_recipe: {
          ...draftRecipeFixture.computed_totals.per_recipe,
          micronutrients: null,
          micronutrients_status: "unavailable" as const,
        },
        per_serving: {
          ...draftRecipeFixture.computed_totals.per_serving,
          micronutrients: null,
          micronutrients_status: "unavailable" as const,
        },
      },
    };
    expect(() => RecipeResponseSchema.parse(noMicros)).not.toThrow();
  });
});

describe("RecipeListResponseSchema", () => {
  it("parses an empty list", () => {
    expect(RecipeListResponseSchema.parse({ items: [] })).toEqual({ items: [] });
  });

  it("parses a populated list", () => {
    const list = { items: [draftRecipeFixture, publishedRecipeFixture] };
    expect(RecipeListResponseSchema.parse(list)).toEqual(list);
  });
});
