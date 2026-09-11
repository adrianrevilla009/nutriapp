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

  // Journey 2: AI-context (ai_detected) mode.
  const aiContext = {
    analysisId: "55555555-5555-4555-8555-555555555555",
    candidateName: "Plain Yogurt Photo Match",
    portionRangeMinG: 120,
    portionRangeMaxG: 160,
  };

  it("with aiContext: catalog-only regression -- no aiContext still behaves exactly as journey 1 (default quantity 100, no banner)", () => {
    renderWithProviders(<LogFoodEntryForm product={productWithNutritionFixture} />);
    expect(screen.getByLabelText(/quantity/i)).toHaveValue(100);
    expect(screen.queryByText(/identified from your photo/i)).not.toBeInTheDocument();
  });

  it("with aiContext: pre-fills quantity from the portion-range midpoint, not the default 100", () => {
    renderWithProviders(
      <LogFoodEntryForm product={productWithNutritionFixture} aiContext={aiContext} />,
    );
    expect(screen.getByLabelText(/quantity/i)).toHaveValue(140); // midpoint of 120-160
  });

  it("with aiContext: shows the AI-sourced disclosure banner naming the candidate", () => {
    renderWithProviders(
      <LogFoodEntryForm product={productWithNutritionFixture} aiContext={aiContext} />,
    );
    expect(screen.getByText(/identified from your photo/i)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(aiContext.candidateName))).toBeInTheDocument();
  });

  it("with aiContext: also blocks on a product with no nutrition data -- the SAME guard as the catalog path", () => {
    renderWithProviders(
      <LogFoodEntryForm product={productWithoutNutritionFixture} aiContext={aiContext} />,
    );
    expect(screen.getByText(/no nutrition data on file/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/quantity/i)).not.toBeInTheDocument();
  });

  it("with aiContext: submits source.source_type=ai_detected, source_reference_id=analysisId, and macros from the MATCHED PRODUCT (never fabricated)", async () => {
    let capturedBody: unknown;
    let capturedCorrelationId: string | null = null;
    server.use(
      http.post("/api/diary/food-entries", async ({ request }) => {
        capturedBody = await request.json();
        capturedCorrelationId = request.headers.get("X-Correlation-Id");
        return HttpResponse.json(foodEntryResponseFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(
      <LogFoodEntryForm product={productWithNutritionFixture} aiContext={aiContext} />,
    );
    await user.click(screen.getByRole("button", { name: /log entry/i }));

    expect(await screen.findByText(/may take a moment to update/i)).toBeInTheDocument();
    expect(capturedBody).toMatchObject({
      source: {
        source_type: "ai_detected",
        source_reference_id: aiContext.analysisId,
        snapshot: {
          name: productWithNutritionFixture.name,
          quantity: 140,
          unit: "g",
          macros_per_unit: {
            calories_kcal: productWithNutritionFixture.nutrition_per_100g!.energy_kcal,
            protein_g: productWithNutritionFixture.nutrition_per_100g!.protein_g,
            carbs_g: productWithNutritionFixture.nutrition_per_100g!.carbohydrates_g,
            fat_g: productWithNutritionFixture.nutrition_per_100g!.fat_g,
          },
        },
      },
    });
    expect(capturedCorrelationId).toBe(aiContext.analysisId);
  });

  it("without aiContext, no X-Correlation-Id header is sent -- REGRESSION for journey 1", async () => {
    let capturedCorrelationId: string | null | undefined = "not-set";
    server.use(
      http.post("/api/diary/food-entries", ({ request }) => {
        capturedCorrelationId = request.headers.get("X-Correlation-Id");
        return HttpResponse.json(foodEntryResponseFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<LogFoodEntryForm product={productWithNutritionFixture} />);
    await user.click(screen.getByRole("button", { name: /log entry/i }));

    await screen.findByText(/may take a moment to update/i);
    expect(capturedCorrelationId).toBeNull();
  });

  it("has no critical/serious axe violations in the AI-context form state", async () => {
    const { container } = renderWithProviders(
      <LogFoodEntryForm product={productWithNutritionFixture} aiContext={aiContext} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
