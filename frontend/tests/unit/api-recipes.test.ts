import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { AppError } from "@/lib/api/http-client";
import {
  NotEntitledError,
  createRecipe,
  deleteRecipe,
  publishRecipe,
  searchPublishedRecipes,
} from "@/lib/api/recipes";
import {
  draftRecipeFixture,
  notEntitledErrorFixture,
  unresolvableIngredientErrorFixture,
} from "../fixtures/recipe.fixtures";

const validRequest = {
  title: "Yogurt Bowl",
  instructions: "Combine yogurt and toppings in a bowl.",
  servings: 2,
  ingredients: [
    { catalog_product_id: "22222222-2222-4222-8222-222222222222", quantity_grams: 200 },
  ],
};

describe("createRecipe", () => {
  it("posts the exact request shape -- structurally proving no totals field is ever sent", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("/api/recipes", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(draftRecipeFixture, { status: 201 });
      }),
    );
    await createRecipe(validRequest, "fixture-token");
    expect(capturedBody).toEqual(validRequest);
    expect(capturedBody).not.toHaveProperty("computed_totals");
  });
});

describe("publishRecipe -- 402/NOT_ENTITLED distinguishability", () => {
  it("maps a 402 NOT_ENTITLED into a distinguishable NotEntitledError, not a generic AppError", async () => {
    server.use(
      http.post(`/api/recipes/${draftRecipeFixture.recipe_id}/publish`, () =>
        HttpResponse.json(notEntitledErrorFixture, { status: 402 }),
      ),
    );
    const error = await publishRecipe(draftRecipeFixture.recipe_id, "fixture-token").catch(
      (e) => e,
    );
    expect(error).toBeInstanceOf(NotEntitledError);
    expect(error).toBeInstanceOf(AppError);
  });

  it("maps every other error code to the generic AppError, not NotEntitledError (contrast test)", async () => {
    server.use(
      http.post(`/api/recipes/${draftRecipeFixture.recipe_id}/publish`, () =>
        HttpResponse.json(unresolvableIngredientErrorFixture, { status: 422 }),
      ),
    );
    const error = await publishRecipe(draftRecipeFixture.recipe_id, "fixture-token").catch(
      (e) => e,
    );
    expect(error).not.toBeInstanceOf(NotEntitledError);
    expect(error).toBeInstanceOf(AppError);
  });
});

describe("searchPublishedRecipes -- 402/NOT_ENTITLED distinguishability", () => {
  it("maps a 402 NOT_ENTITLED into a distinguishable NotEntitledError for the searching user too", async () => {
    server.use(
      http.get("/api/recipes/search", () =>
        HttpResponse.json(
          { error: "User is not entitled to search recipes.", code: "NOT_ENTITLED" },
          { status: 402 },
        ),
      ),
    );
    const error = await searchPublishedRecipes("yogurt", "fixture-token").catch((e) => e);
    expect(error).toBeInstanceOf(NotEntitledError);
  });
});

describe("deleteRecipe", () => {
  it("resolves without throwing on a successful delete", async () => {
    server.use(
      http.delete(
        `/api/recipes/${draftRecipeFixture.recipe_id}`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    await expect(
      deleteRecipe(draftRecipeFixture.recipe_id, "fixture-token"),
    ).resolves.toBeUndefined();
  });
});
