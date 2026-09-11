/**
 * Browser-facing recipe client -- calls this app's own app/api/recipes/**
 * Route Handlers (Route-Handler-proxy pattern), which forward to
 * recipe-service's authenticated CRUD/publish/unpublish/search endpoints
 * (recipe_routes.py/search_routes.py, read verbatim during
 * /implementation-plan). The server ALWAYS computes macro/micro totals
 * itself (recipe_nutrient_calculator.py) -- every function here sends only
 * {title, instructions, servings, ingredients: [{catalog_product_id,
 * quantity_grams}]}, never a totals field (recipe-agent.md's "never
 * caller-supplied macros" rule, verified from the client side too).
 */
import { apiFetch, AppError } from "@/lib/api/http-client";
import {
  RecipeResponseSchema,
  RecipeListResponseSchema,
  type RecipeResponse,
  type RecipeListResponse,
  type RecipeMutationRequest,
} from "@/schemas/recipe";

/**
 * Distinguishable from a generic AppError via `instanceof`, never a
 * string-match on `.code` -- a 402/NOT_ENTITLED response is a first-class,
 * expected UI state (acceptance criterion 4), never folded into the
 * generic error banner (journey-3 test-plan section 2).
 */
export class NotEntitledError extends AppError {
  constructor(message: string) {
    super(message, "NOT_ENTITLED", 402);
    this.name = "NotEntitledError";
  }
}

async function callRecipesApi<TResponse>(
  path: string,
  init: { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: unknown; accessToken: string },
): Promise<TResponse> {
  try {
    return await apiFetch<TResponse>(path, init);
  } catch (err) {
    if (err instanceof AppError && err.code === "NOT_ENTITLED") {
      throw new NotEntitledError(err.message);
    }
    throw err;
  }
}

export async function createRecipe(
  request: RecipeMutationRequest,
  accessToken: string,
): Promise<RecipeResponse> {
  const raw = await callRecipesApi<unknown>("/api/recipes", {
    method: "POST",
    body: request,
    accessToken,
  });
  return RecipeResponseSchema.parse(raw);
}

export async function updateRecipe(
  recipeId: string,
  request: RecipeMutationRequest,
  accessToken: string,
): Promise<RecipeResponse> {
  const raw = await callRecipesApi<unknown>(`/api/recipes/${encodeURIComponent(recipeId)}`, {
    method: "PATCH",
    body: request,
    accessToken,
  });
  return RecipeResponseSchema.parse(raw);
}

export async function getRecipe(recipeId: string, accessToken: string): Promise<RecipeResponse> {
  const raw = await callRecipesApi<unknown>(`/api/recipes/${encodeURIComponent(recipeId)}`, {
    method: "GET",
    accessToken,
  });
  return RecipeResponseSchema.parse(raw);
}

export async function listOwnRecipes(accessToken: string): Promise<RecipeListResponse> {
  const raw = await callRecipesApi<unknown>("/api/recipes?mine=true", {
    method: "GET",
    accessToken,
  });
  return RecipeListResponseSchema.parse(raw);
}

export async function publishRecipe(
  recipeId: string,
  accessToken: string,
): Promise<RecipeResponse> {
  const raw = await callRecipesApi<unknown>(
    `/api/recipes/${encodeURIComponent(recipeId)}/publish`,
    { method: "POST", accessToken },
  );
  return RecipeResponseSchema.parse(raw);
}

export async function unpublishRecipe(
  recipeId: string,
  accessToken: string,
): Promise<RecipeResponse> {
  const raw = await callRecipesApi<unknown>(
    `/api/recipes/${encodeURIComponent(recipeId)}/unpublish`,
    { method: "POST", accessToken },
  );
  return RecipeResponseSchema.parse(raw);
}

export async function deleteRecipe(recipeId: string, accessToken: string): Promise<void> {
  await callRecipesApi<unknown>(`/api/recipes/${encodeURIComponent(recipeId)}`, {
    method: "DELETE",
    accessToken,
  });
}

export async function searchPublishedRecipes(
  q: string,
  accessToken: string,
): Promise<RecipeListResponse> {
  const params = new URLSearchParams({ q });
  const raw = await callRecipesApi<unknown>(`/api/recipes/search?${params.toString()}`, {
    method: "GET",
    accessToken,
  });
  return RecipeListResponseSchema.parse(raw);
}
