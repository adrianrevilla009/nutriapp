import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { IngredientPicker } from "@/components/features/recipes/IngredientPicker";
import { productWithNutritionFixture } from "../fixtures/catalog.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("IngredientPicker (ProductSearchBox in 'select' mode)", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
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
  });

  it("renders an 'Add' action, not a 'Log' link -- select mode never uses log mode's navigation affordance", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IngredientPicker onAdd={vi.fn()} />);

    await user.type(screen.getByLabelText(/search products/i), productWithNutritionFixture.name!);
    await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));

    const addButton = await screen.findByRole("button", {
      name: new RegExp(`add ${productWithNutritionFixture.name}`, "i"),
    });
    expect(addButton.tagName).toBe("BUTTON");
    expect(screen.queryByRole("link", { name: /^log /i })).not.toBeInTheDocument();
  });

  it("calls onAdd with a fresh rowId/default quantity, and does not navigate (no route change)", async () => {
    const onAdd = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<IngredientPicker onAdd={onAdd} />);

    await user.type(screen.getByLabelText(/search products/i), productWithNutritionFixture.name!);
    await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));
    await user.click(
      await screen.findByRole("button", {
        name: new RegExp(`add ${productWithNutritionFixture.name}`, "i"),
      }),
    );

    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(onAdd).toHaveBeenCalledWith(
      expect.objectContaining({
        productId: productWithNutritionFixture.product_id,
        productName: productWithNutritionFixture.name,
        quantityGramsInput: "100",
      }),
    );
    // Still on the same screen -- the picker itself is still rendered.
    expect(screen.getByLabelText(/search products/i)).toBeInTheDocument();
  });

  it("selecting the SAME product twice calls onAdd twice with two distinct rowIds (adds a second row, never merges -- journey-3 resolution)", async () => {
    const onAdd = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<IngredientPicker onAdd={onAdd} />);

    await user.type(screen.getByLabelText(/search products/i), productWithNutritionFixture.name!);
    await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));
    const addButton = await screen.findByRole("button", {
      name: new RegExp(`add ${productWithNutritionFixture.name}`, "i"),
    });
    await user.click(addButton);
    await user.click(addButton);

    expect(onAdd).toHaveBeenCalledTimes(2);
    const firstRow = onAdd.mock.calls[0]?.[0];
    const secondRow = onAdd.mock.calls[1]?.[0];
    expect(firstRow.rowId).not.toEqual(secondRow.rowId);
    expect(firstRow.productId).toEqual(secondRow.productId);
  });
});
