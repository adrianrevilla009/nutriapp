import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { PublishRecipeButton } from "@/components/features/recipes/PublishRecipeButton";
import {
  draftRecipeFixture,
  notEntitledErrorFixture,
  unresolvableIngredientErrorFixture,
  publishedRecipeFixture,
} from "../fixtures/recipe.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

const publishUrl = `/api/recipes/${draftRecipeFixture.recipe_id}/publish`;

describe("PublishRecipeButton", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("clicking Publish alone (without confirming) makes ZERO API calls", async () => {
    let called = false;
    server.use(
      http.post(publishUrl, () => {
        called = true;
        return HttpResponse.json(publishedRecipeFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PublishRecipeButton recipeId={draftRecipeFixture.recipe_id} />);

    await user.click(screen.getByRole("button", { name: /^publish$/i }));

    expect(called).toBe(false);
    // CLAUDE.md section 8: the confirmation copy explicitly names that this
    // makes the recipe visible to OTHER users.
    expect(screen.getByText(/visible to other nutriapp users/i)).toBeInTheDocument();
  });

  it("confirming fires the publish call and flips to published", async () => {
    server.use(http.post(publishUrl, () => HttpResponse.json(publishedRecipeFixture)));
    const user = userEvent.setup();
    renderWithProviders(<PublishRecipeButton recipeId={draftRecipeFixture.recipe_id} />);

    await user.click(screen.getByRole("button", { name: /^publish$/i }));
    await user.click(screen.getByRole("button", { name: /publish recipe/i }));

    await vi.waitFor(() =>
      expect(screen.queryByText(/visible to other nutriapp users/i)).not.toBeInTheDocument(),
    );
  });

  it("cancelling the confirmation makes zero API calls and returns to the initial state", async () => {
    let called = false;
    server.use(
      http.post(publishUrl, () => {
        called = true;
        return HttpResponse.json(publishedRecipeFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<PublishRecipeButton recipeId={draftRecipeFixture.recipe_id} />);

    await user.click(screen.getByRole("button", { name: /^publish$/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(called).toBe(false);
    expect(screen.getByRole("button", { name: /^publish$/i })).toBeInTheDocument();
  });

  it("402/NOT_ENTITLED renders an inline Upgrade-to-Pro CTA -- the generic error banner is ABSENT", async () => {
    server.use(
      http.post(publishUrl, () => HttpResponse.json(notEntitledErrorFixture, { status: 402 })),
    );
    const user = userEvent.setup();
    renderWithProviders(<PublishRecipeButton recipeId={draftRecipeFixture.recipe_id} />);

    await user.click(screen.getByRole("button", { name: /^publish$/i }));
    await user.click(screen.getByRole("button", { name: /publish recipe/i }));

    await screen.findByText(/publishing recipes is a pro feature/i);
    expect(screen.getByRole("link", { name: /upgrade to pro/i })).toHaveAttribute("href", "/pro");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("other error codes still render the generic error banner (contrast test) -- no Upgrade CTA", async () => {
    server.use(
      http.post(publishUrl, () =>
        HttpResponse.json(unresolvableIngredientErrorFixture, { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<PublishRecipeButton recipeId={draftRecipeFixture.recipe_id} />);

    await user.click(screen.getByRole("button", { name: /^publish$/i }));
    await user.click(screen.getByRole("button", { name: /publish recipe/i }));

    await screen.findByRole("alert");
    expect(screen.queryByText(/publishing recipes is a pro feature/i)).not.toBeInTheDocument();
  });
});
