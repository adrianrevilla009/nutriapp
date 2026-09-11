"use client";

import { useId, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCreateRecipe } from "@/lib/hooks/useCreateRecipe";
import { useUpdateRecipe } from "@/lib/hooks/useUpdateRecipe";
import {
  canSubmitRecipe,
  ingredientRowsToRequest,
  type IngredientRowState,
} from "@/lib/recipe-ingredients";
import type { RecipeResponse } from "@/schemas/recipe";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { IngredientPicker } from "@/components/features/recipes/IngredientPicker";
import { IngredientRow } from "@/components/features/recipes/IngredientRow";

function initialRowsFrom(recipe?: RecipeResponse): IngredientRowState[] {
  if (!recipe) return [];
  return recipe.ingredients.map((ingredient) => ({
    rowId: crypto.randomUUID(),
    productId: ingredient.catalog_product_id,
    // RecipeIngredient's own docstring: this service never stores a
    // denormalized copy of the product's name -- only catalog_product_id +
    // quantity_grams. A pre-existing row therefore has no name to show
    // until the user re-touches it via IngredientPicker; shown as the raw
    // id rather than inventing a display name the backend never sent.
    productName: ingredient.catalog_product_id,
    quantityGramsInput: String(ingredient.quantity_grams),
  }));
}

export function RecipeForm({ mode, recipe }: { mode: "create" | "edit"; recipe?: RecipeResponse }) {
  const t = useTranslations("recipes");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const guidanceId = useId();
  const liveEditHeadingId = useId();

  const [title, setTitle] = useState(recipe?.title ?? "");
  const [instructions, setInstructions] = useState(recipe?.instructions ?? "");
  const [servings, setServings] = useState(String(recipe?.servings ?? 1));
  const [rows, setRows] = useState<IngredientRowState[]>(() => initialRowsFrom(recipe));
  const [servingsError, setServingsError] = useState<string | null>(null);
  // journey-3 resolution 7 (structural finding, not a backend block):
  // UpdateRecipeHandler has no is_published check -- editing an
  // already-published recipe is unblocked and takes effect immediately in
  // cross-user search (Recipe.update()'s own docstring: "an
  // already-published recipe stays published with its (recomputed)
  // totals"). This checkbox is the ONLY mitigation this plan builds: a
  // pre-submit acknowledgment gate, deliberately never a stronger
  // backend-enforced guard this frontend can't actually provide.
  const [acknowledgedLiveEdit, setAcknowledgedLiveEdit] = useState(false);

  const createMutation = useCreateRecipe();
  const updateMutation = useUpdateRecipe(recipe?.recipe_id ?? "");
  const mutation = mode === "create" ? createMutation : updateMutation;

  const needsLiveEditWarning = mode === "edit" && recipe?.is_published === true;
  const ingredientsValid = canSubmitRecipe(rows);
  const canSubmit = ingredientsValid && title.trim().length > 0 && instructions.trim().length > 0;
  const submitBlockedByLiveEdit = needsLiveEditWarning && !acknowledgedLiveEdit;

  function addRow(row: IngredientRowState) {
    setRows((prev) => [...prev, row]);
  }
  function updateRowQuantity(rowId: string, value: string) {
    setRows((prev) =>
      prev.map((r) => (r.rowId === rowId ? { ...r, quantityGramsInput: value } : r)),
    );
  }
  function removeRow(rowId: string) {
    setRows((prev) => prev.filter((r) => r.rowId !== rowId));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setServingsError(null);

    const servingsNumber = Number(servings);
    if (!Number.isInteger(servingsNumber) || servingsNumber <= 0) {
      setServingsError(t("servingsInvalid"));
      return; // Blocked client-side -- no network call.
    }
    if (!canSubmit) return; // Blocked client-side -- no network call.
    if (submitBlockedByLiveEdit) return; // Blocked client-side -- no network call.

    const request = {
      title: title.trim(),
      instructions: instructions.trim(),
      servings: servingsNumber,
      ingredients: ingredientRowsToRequest(rows),
    };

    mutation.mutate(request, {
      onSuccess: (saved) => {
        router.push(`/recipes/${saved.recipe_id}`);
      },
    });
  }

  return (
    <div className="page">
      <h1>{mode === "create" ? t("newRecipeTitle") : t("editRecipeTitle")}</h1>
      {mutation.isError ? (
        <ErrorBanner
          message={
            mutation.error instanceof Error ? mutation.error.message : tCommon("genericError")
          }
        />
      ) : null}
      <form onSubmit={handleSubmit} noValidate>
        <TextField
          label={t("titleLabel")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <TextField
          label={t("instructionsLabel")}
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
        <TextField
          label={t("servingsLabel")}
          type="number"
          min={1}
          step={1}
          value={servings}
          onChange={(e) => setServings(e.target.value)}
          error={servingsError}
        />

        <h2>{t("ingredientsHeading")}</h2>
        {rows.length === 0 ? (
          <p id={guidanceId}>{t("ingredientsEmptyGuidance")}</p>
        ) : (
          <ul aria-describedby={guidanceId}>
            {rows.map((row) => (
              <IngredientRow
                key={row.rowId}
                row={row}
                onQuantityChange={updateRowQuantity}
                onRemove={removeRow}
              />
            ))}
          </ul>
        )}
        <IngredientPicker onAdd={addRow} />

        {needsLiveEditWarning ? (
          <div className="notice" role="group" aria-labelledby={liveEditHeadingId}>
            <p id={liveEditHeadingId}>{t("liveEditWarning")}</p>
            <label>
              <input
                type="checkbox"
                checked={acknowledgedLiveEdit}
                onChange={(e) => setAcknowledgedLiveEdit(e.target.checked)}
              />
              {t("liveEditAcknowledge")}
            </label>
          </div>
        ) : null}

        <Button
          type="submit"
          disabled={!canSubmit || mutation.isPending || submitBlockedByLiveEdit}
          aria-describedby={rows.length === 0 ? guidanceId : undefined}
        >
          {mutation.isPending ? tCommon("loading") : t("saveAction")}
        </Button>
      </form>
    </div>
  );
}
