/**
 * Zod schemas mirroring
 * services/recipe-service/infrastructure/http/schemas/recipe_schemas.py
 * field-for-field (journey 3, /plans/frontend/journey-3-implementation-plan.md
 * section 4).
 */
import { z } from "zod";

// Mirrors RecipeIngredientRequest: {catalog_product_id: UUID, quantity_grams: float > 0}
export const RecipeIngredientRequestSchema = z.object({
  catalog_product_id: z.string().uuid(),
  quantity_grams: z.number().positive(),
});
export type RecipeIngredientRequest = z.infer<typeof RecipeIngredientRequestSchema>;

// Mirrors CreateRecipeRequest / UpdateRecipeRequest -- backend-side these
// are two Pydantic classes with an IDENTICAL shape (recipe_schemas.py), so
// one schema covers both request bodies here.
//
// `ingredients` allows an EMPTY array at the schema level -- confirmed by
// reading domain/entities/recipe.py: neither create() nor update() enforces
// a minimum-ingredient count, and CreateRecipeRequest's own
// `Field(default_factory=list)` allows zero. The >=1-ingredient UI guard is
// a frontend-only opinion (lib/recipe-ingredients.ts's canSubmitRecipe),
// never encoded here as if it were a backend contract.
export const RecipeMutationRequestSchema = z.object({
  title: z.string().min(1).max(255),
  instructions: z.string().min(1),
  servings: z.number().int().positive(),
  ingredients: z.array(RecipeIngredientRequestSchema),
});
export type RecipeMutationRequest = z.infer<typeof RecipeMutationRequestSchema>;
export type CreateRecipeRequest = RecipeMutationRequest;
export type UpdateRecipeRequest = RecipeMutationRequest;

// Mirrors the three-state status literal recipe_nutrient_calculator.py
// computes for BOTH macros_status and micronutrients_status independently
// (reviewer-agent finding per that module's own docstring: "macros_status
// mirrors micronutrients_status exactly").
export const NutrientStatusSchema = z.enum(["available", "partial", "unavailable"]);
export type NutrientStatus = z.infer<typeof NutrientStatusSchema>;

// Mirrors MacroAmountsResponse
export const MacroAmountsResponseSchema = z.object({
  calories_kcal: z.number(),
  protein_g: z.number(),
  carbs_g: z.number(),
  fat_g: z.number(),
});
export type MacroAmountsResponse = z.infer<typeof MacroAmountsResponseSchema>;

// Mirrors NutrientTotalsResponse
export const NutrientTotalsResponseSchema = z.object({
  macros: MacroAmountsResponseSchema,
  macros_status: NutrientStatusSchema,
  micronutrients: z.record(z.string(), z.number().nullable()).nullable(),
  micronutrients_status: NutrientStatusSchema,
});
export type NutrientTotalsResponse = z.infer<typeof NutrientTotalsResponseSchema>;

// Mirrors RecipeNutrientTotalsResponse: {per_recipe, per_serving}
export const RecipeNutrientTotalsResponseSchema = z.object({
  per_recipe: NutrientTotalsResponseSchema,
  per_serving: NutrientTotalsResponseSchema,
});
export type RecipeNutrientTotalsResponse = z.infer<typeof RecipeNutrientTotalsResponseSchema>;

// Mirrors RecipeIngredientResponse
export const RecipeIngredientResponseSchema = z.object({
  catalog_product_id: z.string().uuid(),
  quantity_grams: z.number(),
});
export type RecipeIngredientResponse = z.infer<typeof RecipeIngredientResponseSchema>;

// Mirrors RecipeResponse
export const RecipeResponseSchema = z.object({
  recipe_id: z.string().uuid(),
  user_id: z.string().uuid(),
  title: z.string(),
  instructions: z.string(),
  servings: z.number().int(),
  ingredients: z.array(RecipeIngredientResponseSchema),
  computed_totals: RecipeNutrientTotalsResponseSchema,
  is_published: z.boolean(),
  unpublished_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type RecipeResponse = z.infer<typeof RecipeResponseSchema>;

// Mirrors RecipeListResponse
export const RecipeListResponseSchema = z.object({
  items: z.array(RecipeResponseSchema),
});
export type RecipeListResponse = z.infer<typeof RecipeListResponseSchema>;
