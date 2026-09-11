import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { RecipeDetailView } from "@/components/features/recipes/RecipeDetailView";
import { draftRecipeFixture, publishedRecipeFixture } from "../fixtures/recipe.fixtures";
import { setAccessToken } from "@/lib/session";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("RecipeDetailView", () => {
  beforeEach(() => {
    push.mockClear();
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("renders a draft recipe's title, status, and nutrient totals, with a Publish action (not Unpublish)", async () => {
    server.use(
      http.get(`/api/recipes/${draftRecipeFixture.recipe_id}`, () =>
        HttpResponse.json(draftRecipeFixture),
      ),
    );
    renderWithProviders(<RecipeDetailView recipeId={draftRecipeFixture.recipe_id} />);

    await screen.findByRole("heading", { name: draftRecipeFixture.title });
    expect(screen.getByText(/^draft$/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^publish$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /unpublish/i })).not.toBeInTheDocument();
    // RecipeNutrientTotals renders both the per-recipe and per-serving tables.
    expect(screen.getByText(/whole recipe/i)).toBeInTheDocument();
    expect(screen.getByText(/per serving/i)).toBeInTheDocument();
  });

  it("renders a published recipe's Unpublish action (not Publish)", async () => {
    server.use(
      http.get(`/api/recipes/${publishedRecipeFixture.recipe_id}`, () =>
        HttpResponse.json(publishedRecipeFixture),
      ),
    );
    renderWithProviders(<RecipeDetailView recipeId={publishedRecipeFixture.recipe_id} />);

    await screen.findByRole("heading", { name: publishedRecipeFixture.title });
    expect(screen.getByText(/^published$/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unpublish/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^publish$/i })).not.toBeInTheDocument();
  });

  it("clicking Unpublish calls the real endpoint", async () => {
    let called = false;
    server.use(
      http.get(`/api/recipes/${publishedRecipeFixture.recipe_id}`, () =>
        HttpResponse.json(publishedRecipeFixture),
      ),
      http.post(`/api/recipes/${publishedRecipeFixture.recipe_id}/unpublish`, () => {
        called = true;
        return HttpResponse.json(draftRecipeFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeDetailView recipeId={publishedRecipeFixture.recipe_id} />);
    await screen.findByRole("heading", { name: publishedRecipeFixture.title });

    await user.click(screen.getByRole("button", { name: /unpublish/i }));
    await vi.waitFor(() => expect(called).toBe(true));
  });

  it("clicking Edit switches to RecipeForm in edit mode", async () => {
    server.use(
      http.get(`/api/recipes/${draftRecipeFixture.recipe_id}`, () =>
        HttpResponse.json(draftRecipeFixture),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeDetailView recipeId={draftRecipeFixture.recipe_id} />);
    await screen.findByRole("heading", { name: draftRecipeFixture.title });

    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(await screen.findByRole("heading", { name: /edit recipe/i })).toBeInTheDocument();
  });

  it("clicking Delete calls the real endpoint and navigates back to /recipes", async () => {
    let called = false;
    server.use(
      http.get(`/api/recipes/${draftRecipeFixture.recipe_id}`, () =>
        HttpResponse.json(draftRecipeFixture),
      ),
      http.delete(`/api/recipes/${draftRecipeFixture.recipe_id}`, () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeDetailView recipeId={draftRecipeFixture.recipe_id} />);
    await screen.findByRole("heading", { name: draftRecipeFixture.title });

    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await vi.waitFor(() => expect(called).toBe(true));
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/recipes"));
  });

  it("has no critical/serious axe violations for a draft recipe", async () => {
    server.use(
      http.get(`/api/recipes/${draftRecipeFixture.recipe_id}`, () =>
        HttpResponse.json(draftRecipeFixture),
      ),
    );
    const { container } = renderWithProviders(
      <RecipeDetailView recipeId={draftRecipeFixture.recipe_id} />,
    );
    await screen.findByRole("heading", { name: draftRecipeFixture.title });
    expect(await axe(container)).toHaveNoViolations();
  });
});
