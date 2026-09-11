import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "jest-axe";
import { server } from "../msw-server";
import { renderWithProviders } from "./test-utils";
import { ProductSearchBox } from "@/components/features/catalog/ProductSearchBox";
import {
  emptyProductSearchResponseFixture,
  productSearchResponseFixture,
  productWithNutritionFixture,
} from "../fixtures/catalog.fixtures";

async function search(query: string) {
  const user = userEvent.setup();
  renderWithProviders(<ProductSearchBox />);
  await user.type(screen.getByLabelText(/search products/i), query);
  await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));
  return user;
}

describe("ProductSearchBox / ProductResultList", () => {
  it("shows guidance text (not an error) before any query is submitted", () => {
    renderWithProviders(<ProductSearchBox />);
    expect(screen.getByText(/search by product name/i)).toBeInTheDocument();
  });

  it("renders populated results with name/brand/nutrition snippet", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    await search("yogurt");

    expect(await screen.findByText(productWithNutritionFixture.name!)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(productWithNutritionFixture.brand!))).toBeInTheDocument();
    expect(screen.getByText(/per 100 g/i)).toBeInTheDocument();
  });

  it("shows an explicit 'no products found' message for a zero-result query", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(emptyProductSearchResponseFixture)),
    );
    await search("xyznotfound");

    expect(await screen.findByText(/no products found for "xyznotfound"/i)).toBeInTheDocument();
  });

  it("each result's Log action is an accessible link naming the product", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    await search("yogurt");

    const link = await screen.findByRole("link", {
      name: new RegExp(`log ${productWithNutritionFixture.name}`, "i"),
    });
    expect(link).toHaveAttribute("href", `/log/${productWithNutritionFixture.product_id}`);
  });

  it("shows a retry affordance on a network failure, never a silent blank list", async () => {
    server.use(http.get("/api/catalog/search", () => HttpResponse.error()));
    await search("yogurt");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("the result list is a semantic list (role=list/listitem)", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    await search("yogurt");

    await screen.findByRole("listitem");
    expect(screen.getAllByRole("listitem")).toHaveLength(productSearchResponseFixture.items.length);
  });

  it("has no critical/serious axe violations with populated results", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    const user = userEvent.setup();
    const { container } = renderWithProviders(<ProductSearchBox />);
    await user.type(screen.getByLabelText(/search products/i), "yogurt");
    await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));
    await screen.findByRole("listitem");

    expect(await axe(container)).toHaveNoViolations();
  });

  // Journey 2: initialQuery/aiContext.
  const aiContext = {
    analysisId: "55555555-5555-4555-8555-555555555555",
    candidateName: "Plain Yogurt",
    portionRangeMinG: 120,
    portionRangeMaxG: 160,
  };

  it("with no initialQuery (a plain /search visit), starts empty -- REGRESSION for journey 1's original behavior", () => {
    renderWithProviders(<ProductSearchBox />);
    expect(screen.getByLabelText(/search products/i)).toHaveValue("");
    expect(screen.getByText(/search by product name/i)).toBeInTheDocument();
  });

  it("with initialQuery, pre-fills AND auto-submits the search on first render", async () => {
    let capturedQuery: string | null = null;
    server.use(
      http.get("/api/catalog/search", ({ request }) => {
        capturedQuery = new URL(request.url).searchParams.get("q");
        return HttpResponse.json(productSearchResponseFixture);
      }),
    );
    renderWithProviders(<ProductSearchBox initialQuery="yogurt" />);

    expect(screen.getByLabelText(/search products/i)).toHaveValue("yogurt");
    await screen.findByText(productWithNutritionFixture.name!);
    expect(capturedQuery).toBe("yogurt");
  });

  it("with aiContext, renders a banner naming the matched candidate", () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(emptyProductSearchResponseFixture)),
    );
    renderWithProviders(<ProductSearchBox initialQuery="yogurt" aiContext={aiContext} />);
    expect(screen.getByText(/matching your photo detection/i)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(aiContext.candidateName))).toBeInTheDocument();
  });

  it("without aiContext, renders no banner -- REGRESSION for journey 1's plain search", () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(emptyProductSearchResponseFixture)),
    );
    renderWithProviders(<ProductSearchBox initialQuery="yogurt" />);
    expect(screen.queryByText(/matching your photo detection/i)).not.toBeInTheDocument();
  });

  it("with aiContext, each result's Log link carries the AI query params", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    renderWithProviders(<ProductSearchBox initialQuery="yogurt" aiContext={aiContext} />);
    const link = await screen.findByRole("link", {
      name: new RegExp(`log ${productWithNutritionFixture.name}`, "i"),
    });
    const href = link.getAttribute("href")!;
    expect(href).toContain(`/log/${productWithNutritionFixture.product_id}`);
    expect(href).toContain(`aiAnalysisId=${aiContext.analysisId}`);
    expect(href).toContain(`aiPortionMinG=${aiContext.portionRangeMinG}`);
    expect(href).toContain(`aiPortionMaxG=${aiContext.portionRangeMaxG}`);
  });

  it("without aiContext, each result's Log link is the bare /log/{id} href -- REGRESSION for journey 1", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    await search("yogurt");
    const link = await screen.findByRole("link", {
      name: new RegExp(`log ${productWithNutritionFixture.name}`, "i"),
    });
    expect(link).toHaveAttribute("href", `/log/${productWithNutritionFixture.product_id}`);
  });

  // Journey 3: the "log"/"select" mode prop.
  it("with no mode prop specified, defaults to 'log' -- REGRESSION for journeys 1-2 (no behavior change from adding the prop)", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    await search("yogurt");
    expect(
      await screen.findByRole("link", {
        name: new RegExp(`log ${productWithNutritionFixture.name}`, "i"),
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: new RegExp(`add ${productWithNutritionFixture.name}`, "i"),
      }),
    ).not.toBeInTheDocument();
  });

  it("with mode='select', renders an 'Add' BUTTON instead of a 'Log' link, and calls onSelect rather than navigating", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<ProductSearchBox mode="select" onSelect={onSelect} />);
    await user.type(screen.getByLabelText(/search products/i), "yogurt");
    await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));

    const addButton = await screen.findByRole("button", {
      name: new RegExp(`add ${productWithNutritionFixture.name}`, "i"),
    });
    expect(
      screen.queryByRole("link", {
        name: new RegExp(`log ${productWithNutritionFixture.name}`, "i"),
      }),
    ).not.toBeInTheDocument();

    await user.click(addButton);
    expect(onSelect).toHaveBeenCalledWith(productWithNutritionFixture);
  });

  it("with nested=true, renders NO <form> element (avoids an invalid nested-<form> bug when embedded in RecipeForm's own <form>) -- search still works via the button's onClick", async () => {
    server.use(
      http.get("/api/catalog/search", () => HttpResponse.json(productSearchResponseFixture)),
    );
    const user = userEvent.setup();
    const { container } = renderWithProviders(<ProductSearchBox mode="select" nested />);

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByRole("search")).toBeInTheDocument();

    await user.type(screen.getByLabelText(/search products/i), "yogurt");
    await user.click(screen.getByRole("button", { name: /^find a food to log$/i }));
    expect(await screen.findByText(productWithNutritionFixture.name!)).toBeInTheDocument();
  });

  it("with nested=false (default), still renders a real <form> -- REGRESSION for every other call site", () => {
    const { container } = renderWithProviders(<ProductSearchBox />);
    expect(container.querySelector("form")).not.toBeNull();
  });
});
