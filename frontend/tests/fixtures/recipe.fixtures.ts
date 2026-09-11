/**
 * Fixtures shaped from
 * services/recipe-service/infrastructure/http/schemas/recipe_schemas.py and
 * infrastructure/http/error_mapping.py (read verbatim during
 * /implementation-plan's research). journey-3 test-plan section 4/8.
 */
import type { NutrientTotalsResponse, RecipeResponse } from "@/schemas/recipe";

const availableMacroTotals: NutrientTotalsResponse = {
  macros: { calories_kcal: 610, protein_g: 35, carbs_g: 47, fat_g: 33 },
  macros_status: "available",
  micronutrients: { calcium_mg: 121, iron_mg: 0.5 },
  micronutrients_status: "available",
};

const perServingAvailableTotals: NutrientTotalsResponse = {
  macros: { calories_kcal: 305, protein_g: 17.5, carbs_g: 23.5, fat_g: 16.5 },
  macros_status: "available",
  micronutrients: { calcium_mg: 60.5, iron_mg: 0.25 },
  micronutrients_status: "available",
};

export const draftRecipeFixture: RecipeResponse = {
  recipe_id: "44444444-4444-4444-8444-444444444444",
  user_id: "11111111-1111-4111-8111-111111111111",
  title: "Yogurt Bowl",
  instructions: "Combine yogurt and toppings in a bowl.",
  servings: 2,
  ingredients: [
    { catalog_product_id: "22222222-2222-4222-8222-222222222222", quantity_grams: 200 },
  ],
  computed_totals: { per_recipe: availableMacroTotals, per_serving: perServingAvailableTotals },
  is_published: false,
  unpublished_at: null,
  created_at: "2026-09-10T08:00:00+00:00",
  updated_at: "2026-09-10T08:00:00+00:00",
};

export const publishedRecipeFixture: RecipeResponse = {
  ...draftRecipeFixture,
  recipe_id: "55555555-5555-4555-8555-555555555555",
  is_published: true,
  unpublished_at: null,
};

// A missing-panel ingredient's macro contribution is documented as ZERO,
// never invented (recipe_nutrient_calculator.py's own docstring) -- status
// downgrades to "partial"/"unavailable" as the honest signal instead.
export const partialTotalsRecipeFixture: RecipeResponse = {
  ...draftRecipeFixture,
  recipe_id: "66666666-6666-4666-8666-666666666666",
  computed_totals: {
    per_recipe: {
      ...availableMacroTotals,
      macros_status: "partial",
      micronutrients_status: "partial",
    },
    per_serving: {
      ...perServingAvailableTotals,
      macros_status: "partial",
      micronutrients_status: "partial",
    },
  },
};

export const notEntitledErrorFixture = {
  error: "User is not entitled to publish recipes.",
  code: "NOT_ENTITLED",
};

export const unresolvableIngredientErrorFixture = {
  error: "catalog_product_id does not resolve to a real catalog-service product.",
  code: "UNRESOLVABLE_INGREDIENT",
};
