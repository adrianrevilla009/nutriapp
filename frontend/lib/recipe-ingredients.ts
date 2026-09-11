/**
 * Pure helpers backing components/features/recipes/RecipeForm.tsx and
 * IngredientPicker.tsx (journey-3 test-plan section 2). Kept separate from
 * any component so quantity-coercion/submit-guard logic is unit-testable
 * without rendering anything.
 */
import type { RecipeIngredientRequest } from "@/schemas/recipe";

export interface IngredientRowState {
  /**
   * A client-only row id (NOT catalog_product_id) -- lets the SAME product
   * be added as a second, separate row.
   *
   * Resolved empirically (journey-3 test-plan "flagged for review" item 1)
   * by reading domain/value_objects/recipe_ingredient.py and
   * domain/entities/recipe.py directly: RecipeIngredient's __post_init__
   * only validates quantity_grams > 0 -- there is no uniqueness check
   * across a Recipe's ingredient tuple, in either the value object or
   * create()/update(). Silently merging two picks of the same product
   * client-side would misrepresent what actually gets submitted (a real
   * choice about quantity math the user never made); adding a second row
   * instead matches the backend's real, permissive invariant rather than
   * inventing a stricter one that doesn't exist server-side.
   */
  rowId: string;
  productId: string;
  productName: string;
  quantityGramsInput: string;
}

/**
 * Parses a row's raw quantity input into a positive number, or null if
 * invalid (empty, non-numeric, zero, negative) -- mirrors
 * RecipeIngredient's own `quantity_grams > 0` invariant client-side, as a
 * fast-fail UX nicety (the backend re-validates regardless, same posture
 * recipe_schemas.py's own header comment documents).
 */
export function parseQuantityGrams(input: string): number | null {
  const value = Number(input);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

/**
 * Frontend-only UX opinion (journey-3 resolution 6): the backend accepts an
 * empty ingredients array (CreateRecipeRequest's `ingredients` has no
 * minimum -- confirmed by reading domain/entities/recipe.py, which enforces
 * no such invariant), but a zero-ingredient recipe has no product value.
 * This guard is enforced here, in the frontend only, never assumed to be a
 * backend contract.
 */
export function canSubmitRecipe(rows: IngredientRowState[]): boolean {
  if (rows.length === 0) return false;
  return rows.every((row) => parseQuantityGrams(row.quantityGramsInput) !== null);
}

export function ingredientRowsToRequest(rows: IngredientRowState[]): RecipeIngredientRequest[] {
  return rows.map((row) => ({
    catalog_product_id: row.productId,
    quantity_grams: parseQuantityGrams(row.quantityGramsInput) ?? 0,
  }));
}
