import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { RecipeForm } from "@/components/features/recipes/RecipeForm";
import { productWithNutritionFixture } from "../fixtures/catalog.fixtures";
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

function mockCatalogSearch() {
  server.use(
    http.get("/api/catalog/search", () =>
      HttpResponse.json({
        items: [productWithNutritionFixture],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  );
}

async function addIngredientViaPicker(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/search products/i), productWithNutritionFixture.name!);
  await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));
  await user.click(
    await screen.findByRole("button", {
      name: new RegExp(`add ${productWithNutritionFixture.name}`, "i"),
    }),
  );
}

describe("RecipeForm -- create mode", () => {
  beforeEach(() => {
    push.mockClear();
    setAccessToken(null);
    mockAuthenticatedSession();
    mockCatalogSearch();
  });

  it("submit is disabled with an empty ingredient list, with guidance text present", async () => {
    renderWithProviders(<RecipeForm mode="create" />);

    expect(screen.getByRole("button", { name: /save recipe/i })).toBeDisabled();
    expect(screen.getByText(/add at least one ingredient/i)).toBeInTheDocument();
  });

  it("adding an ingredient via IngredientPicker does NOT navigate away (select mode, not log mode)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RecipeForm mode="create" />);

    await addIngredientViaPicker(user);

    // Scoped to the ingredient row's own quantity field label (unique),
    // not a bare product-name text query -- the picker's own search
    // RESULT also renders the product name (still visible, since select
    // mode never navigates away), so a bare text query is ambiguous by
    // design here.
    expect(
      await screen.findByLabelText(
        new RegExp(`quantity of ${productWithNutritionFixture.name}`, "i"),
      ),
    ).toBeInTheDocument();
    // Still on the recipe form -- the title field is still present, proving
    // no navigation occurred (contrast with "log" mode's Link behavior).
    expect(screen.getByLabelText(/^title$/i)).toBeInTheDocument();
  });

  it("valid submit sends the exact request shape -- no totals field, ever", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("/api/recipes", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(draftRecipeFixture, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeForm mode="create" />);

    await user.type(screen.getByLabelText(/^title$/i), "Yogurt Bowl");
    await user.type(screen.getByLabelText(/instructions/i), "Combine in a bowl.");
    await addIngredientViaPicker(user);

    await user.click(screen.getByRole("button", { name: /save recipe/i }));

    await vi.waitFor(() => expect(capturedBody).toBeDefined());
    expect(capturedBody).toEqual({
      title: "Yogurt Bowl",
      instructions: "Combine in a bowl.",
      servings: 1,
      ingredients: [
        { catalog_product_id: productWithNutritionFixture.product_id, quantity_grams: 100 },
      ],
    });
    expect(capturedBody).not.toHaveProperty("computed_totals");
    await vi.waitFor(() =>
      expect(push).toHaveBeenCalledWith(`/recipes/${draftRecipeFixture.recipe_id}`),
    );
  });

  it("has no critical/serious axe violations", async () => {
    const { container } = renderWithProviders(<RecipeForm mode="create" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("RecipeForm -- edit mode on an already-published recipe (journey-3 resolution 7)", () => {
  beforeEach(() => {
    push.mockClear();
    setAccessToken(null);
    mockAuthenticatedSession();
    mockCatalogSearch();
  });

  it("shows the live-edit warning and blocks submit until acknowledged -- zero API calls until then", async () => {
    let called = false;
    server.use(
      http.patch(`/api/recipes/${publishedRecipeFixture.recipe_id}`, () => {
        called = true;
        return HttpResponse.json(publishedRecipeFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeForm mode="edit" recipe={publishedRecipeFixture} />);

    expect(screen.getByText(/already published/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save recipe/i })).toBeDisabled();

    // Still disabled with a valid form but the acknowledgment unchecked.
    await user.click(screen.getByRole("button", { name: /save recipe/i }));
    expect(called).toBe(false);

    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: /save recipe/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /save recipe/i }));
    await vi.waitFor(() => expect(called).toBe(true));
  });

  it("does NOT show the live-edit warning for an unpublished (draft) recipe edit", () => {
    renderWithProviders(<RecipeForm mode="edit" recipe={draftRecipeFixture} />);
    expect(screen.queryByText(/already published/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
