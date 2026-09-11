import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { OwnRecipesView } from "@/components/features/recipes/OwnRecipesView";
import { draftRecipeFixture, publishedRecipeFixture } from "../fixtures/recipe.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("OwnRecipesView", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("renders an empty-state message when there are no own recipes yet", async () => {
    server.use(http.get("/api/recipes", () => HttpResponse.json({ items: [] })));
    renderWithProviders(<OwnRecipesView />);

    expect(await screen.findByText(/haven't created any recipes yet/i)).toBeInTheDocument();
  });

  it("renders draft and published recipes with distinct status text", async () => {
    server.use(
      http.get("/api/recipes", () =>
        HttpResponse.json({ items: [draftRecipeFixture, publishedRecipeFixture] }),
      ),
    );
    renderWithProviders(<OwnRecipesView />);

    await screen.findAllByText(draftRecipeFixture.title);
    const statuses = screen.getAllByText(/^(draft|published)$/i).map((el) => el.textContent);
    expect(statuses).toContain("Draft");
    expect(statuses).toContain("Published");
  });

  it("each recipe links to its own detail page", async () => {
    server.use(http.get("/api/recipes", () => HttpResponse.json({ items: [draftRecipeFixture] })));
    renderWithProviders(<OwnRecipesView />);

    const link = await screen.findByRole("link", {
      name: new RegExp(`view ${draftRecipeFixture.title}`, "i"),
    });
    expect(link).toHaveAttribute("href", `/recipes/${draftRecipeFixture.recipe_id}`);
  });

  it("shows the already-Pro notice only when the alreadyPro prop is set (from the /recipes?alreadyPro=1 redirect)", async () => {
    server.use(http.get("/api/recipes", () => HttpResponse.json({ items: [] })));
    renderWithProviders(<OwnRecipesView alreadyPro />);

    expect(await screen.findByText(/you're already a pro subscriber/i)).toBeInTheDocument();
  });

  it("has no critical/serious axe violations with a populated list", async () => {
    server.use(
      http.get("/api/recipes", () =>
        HttpResponse.json({ items: [draftRecipeFixture, publishedRecipeFixture] }),
      ),
    );
    const { container } = renderWithProviders(<OwnRecipesView />);
    await screen.findAllByText(draftRecipeFixture.title);
    expect(await axe(container)).toHaveNoViolations();
  });
});
