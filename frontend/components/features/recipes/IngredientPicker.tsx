"use client";

import { useTranslations } from "next-intl";
import { ProductSearchBox } from "@/components/features/catalog/ProductSearchBox";
import type { ProductResponse } from "@/schemas/catalog";
import type { IngredientRowState } from "@/lib/recipe-ingredients";

/**
 * Wraps ProductSearchBox in "select" mode (journey 3) -- selecting a
 * product adds it to the recipe's ingredient list in place; it never
 * navigates away, unlike "log" mode's existing behavior (journeys 1-2,
 * unchanged, regression-tested).
 */
export function IngredientPicker({ onAdd }: { onAdd: (row: IngredientRowState) => void }) {
  const t = useTranslations("recipes");

  function handleSelect(product: ProductResponse) {
    onAdd({
      rowId: crypto.randomUUID(),
      productId: product.product_id,
      productName: product.name ?? t("unnamedProduct"),
      quantityGramsInput: "100",
    });
  }

  return <ProductSearchBox mode="select" onSelect={handleSelect} nested />;
}
