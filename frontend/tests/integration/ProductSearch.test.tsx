import { describe, expect, it } from "vitest";
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
});
