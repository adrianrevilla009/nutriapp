import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { RecipeSearchBox } from "@/components/features/recipes/RecipeSearchBox";
import { publishedRecipeFixture, notEntitledErrorFixture } from "../fixtures/recipe.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("RecipeSearchBox", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("renders search results with title/servings/macro summary", async () => {
    server.use(
      http.get("/api/recipes/search", () => HttpResponse.json({ items: [publishedRecipeFixture] })),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeSearchBox />);

    await user.type(screen.getByLabelText(/search recipes/i), publishedRecipeFixture.title);
    await user.click(screen.getByRole("button", { name: /find a recipe/i }));

    await screen.findByText(publishedRecipeFixture.title);
    expect(screen.getByText(/serves 2/i)).toBeInTheDocument();
  });

  it("402/NOT_ENTITLED renders a distinct 'Search is a Pro feature' CTA -- not empty-results, not a generic error", async () => {
    server.use(
      http.get("/api/recipes/search", () =>
        HttpResponse.json(notEntitledErrorFixture, { status: 402 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeSearchBox />);

    await user.type(screen.getByLabelText(/search recipes/i), "yogurt");
    await user.click(screen.getByRole("button", { name: /find a recipe/i }));

    await screen.findByText(/recipe search is a pro feature/i);
    expect(screen.getByRole("link", { name: /upgrade to pro/i })).toHaveAttribute("href", "/pro");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/no published recipes found/i)).not.toBeInTheDocument();
  });

  it("a genuine 5xx renders the generic error banner, distinct from the NOT_ENTITLED CTA", async () => {
    server.use(
      http.get("/api/recipes/search", () =>
        HttpResponse.json({ error: "boom", code: "INTERNAL_ERROR" }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeSearchBox />);

    await user.type(screen.getByLabelText(/search recipes/i), "yogurt");
    await user.click(screen.getByRole("button", { name: /find a recipe/i }));

    await screen.findByRole("alert");
    expect(screen.queryByText(/recipe search is a pro feature/i)).not.toBeInTheDocument();
  });

  it("blocks submission of an empty query -- no request fires", async () => {
    let called = false;
    server.use(
      http.get("/api/recipes/search", () => {
        called = true;
        return HttpResponse.json({ items: [] });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RecipeSearchBox />);

    await user.click(screen.getByRole("button", { name: /find a recipe/i }));

    expect(called).toBe(false);
    expect(screen.getByText(/search by recipe title/i)).toBeInTheDocument();
  });

  it("has no critical/serious axe violations with populated results", async () => {
    server.use(
      http.get("/api/recipes/search", () => HttpResponse.json({ items: [publishedRecipeFixture] })),
    );
    const user = userEvent.setup();
    const { container } = renderWithProviders(<RecipeSearchBox />);
    await user.type(screen.getByLabelText(/search recipes/i), publishedRecipeFixture.title);
    await user.click(screen.getByRole("button", { name: /find a recipe/i }));
    await screen.findByText(publishedRecipeFixture.title);

    expect(await axe(container)).toHaveNoViolations();
  });
});
