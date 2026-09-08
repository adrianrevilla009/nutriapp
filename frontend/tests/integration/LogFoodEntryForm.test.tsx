import { beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { LogFoodEntryForm } from "@/components/features/diary/LogFoodEntryForm";
import {
  productWithNutritionFixture,
  productWithoutNutritionFixture,
} from "../fixtures/catalog.fixtures";
import { foodEntryResponseFixture } from "../fixtures/diary.fixtures";
import { setAccessToken } from "@/lib/session";

function mockAuthenticatedSession() {
  server.use(
    http.post("/api/auth/refresh", () =>
      HttpResponse.json({ access_token: "fixture-access-token", token_type: "bearer" }),
    ),
  );
}

describe("LogFoodEntryForm", () => {
  beforeEach(() => {
    setAccessToken(null);
    mockAuthenticatedSession();
  });

  it("blocks the whole form with a visible message when the product has no nutrition data", () => {
    renderWithProviders(<LogFoodEntryForm product={productWithoutNutritionFixture} />);
    expect(screen.getByText(/no nutrition data on file/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/quantity/i)).not.toBeInTheDocument();
  });

  it("blocks submission client-side for quantity <= 0, making zero network calls", async () => {
    let callCount = 0;
    server.use(
      http.post("/api/diary/food-entries", () => {
        callCount += 1;
        return HttpResponse.json(foodEntryResponseFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<LogFoodEntryForm product={productWithNutritionFixture} />);
    const quantityInput = screen.getByLabelText(/quantity/i);
    await user.clear(quantityInput);
    await user.type(quantityInput, "0");
    await user.click(screen.getByRole("button", { name: /log entry/i }));

    expect(await screen.findByText(/greater than 0/i)).toBeInTheDocument();
    expect(callCount).toBe(0);
  });

  it("happy path: submits the exact LogFoodEntryRequest shape and shows the async-lag notice", async () => {
    let capturedBody: unknown;
    server.use(
      http.post("/api/diary/food-entries", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json(foodEntryResponseFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<LogFoodEntryForm product={productWithNutritionFixture} />);

    const quantityInput = screen.getByLabelText(/quantity/i);
    await user.clear(quantityInput);
    await user.type(quantityInput, "150");
    await user.click(screen.getByRole("button", { name: /log entry/i }));

    expect(await screen.findByText(/may take a moment to update/i)).toBeInTheDocument();
    expect(capturedBody).toMatchObject({
      source: {
        source_type: "catalog_product",
        source_reference_id: productWithNutritionFixture.product_id,
        snapshot: {
          quantity: 150,
          unit: "g",
          macros_per_unit: {
            calories_kcal: productWithNutritionFixture.nutrition_per_100g!.energy_kcal,
            protein_g: productWithNutritionFixture.nutrition_per_100g!.protein_g,
            carbs_g: productWithNutritionFixture.nutrition_per_100g!.carbohydrates_g,
            fat_g: productWithNutritionFixture.nutrition_per_100g!.fat_g,
          },
        },
      },
      meal_slot: "breakfast",
    });
    expect(screen.getByRole("link", { name: /view dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("surfaces a mocked 422 from diary-service inline", async () => {
    server.use(
      http.post("/api/diary/food-entries", () =>
        HttpResponse.json(
          { error: "quantity must be greater than 0.", code: "VALIDATION_ERROR" },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<LogFoodEntryForm product={productWithNutritionFixture} />);
    await user.click(screen.getByRole("button", { name: /log entry/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/quantity must be greater than 0/i);
  });

  it("has no critical/serious axe violations in the blocked (no-nutrition-data) state", async () => {
    const { container } = renderWithProviders(
      <LogFoodEntryForm product={productWithoutNutritionFixture} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no critical/serious axe violations in the happy-path form state", async () => {
    const { container } = renderWithProviders(
      <LogFoodEntryForm product={productWithNutritionFixture} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
