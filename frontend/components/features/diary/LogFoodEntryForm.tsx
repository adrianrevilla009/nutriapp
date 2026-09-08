"use client";

import { useId, useMemo, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { useLogFoodEntry } from "@/lib/hooks/useLogFoodEntry";
import { productToLogFoodEntryRequest } from "@/lib/diary-mapping";
import type { ProductResponse } from "@/schemas/catalog";
import type { MealSlot } from "@/schemas/diary";
import { TextField } from "@/components/ui/TextField";
import { SelectField } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";

const MEAL_SLOTS: MealSlot[] = ["breakfast", "lunch", "dinner", "snack"];

function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

export function LogFoodEntryForm({ product }: { product: ProductResponse }) {
  const t = useTranslations("log");
  const tCommon = useTranslations("common");
  const quantityErrorId = useId();

  // Upfront check (a dummy quantity is enough to detect the structural
  // "no nutrition data" case) -- this product either can be logged at all,
  // or it can't; §2/§3 of the test plan require this to block the whole
  // form, not just surface at submit time.
  const canLog = useMemo(
    () => productToLogFoodEntryRequest(product, 1, "breakfast", new Date()).ok,
    [product],
  );

  const [quantity, setQuantity] = useState("100");
  const [mealSlot, setMealSlot] = useState<MealSlot>("breakfast");
  const [occurredAt, setOccurredAt] = useState(() => toDatetimeLocalValue(new Date()));
  const [quantityError, setQuantityError] = useState<string | null>(null);

  const mutation = useLogFoodEntry();

  if (!canLog) {
    return <ErrorBanner message={t("noNutritionData")} />;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setQuantityError(null);

    const quantityGrams = Number(quantity);
    if (!Number.isFinite(quantityGrams) || quantityGrams <= 0) {
      setQuantityError(t("quantityInvalid"));
      return; // Blocked client-side -- no network call.
    }

    const mapped = productToLogFoodEntryRequest(
      product,
      quantityGrams,
      mealSlot,
      new Date(occurredAt),
    );
    if (!mapped.ok) {
      // Structurally unreachable given the canLog guard above, but keeps
      // this branch exhaustive/typed rather than asserting past it.
      return;
    }
    mutation.mutate(mapped.request);
  }

  if (mutation.isSuccess) {
    return (
      <div className="notice">
        <h1>{t("successTitle")}</h1>
        <p>{t("successBody")}</p>
        <a href="/dashboard" className="btn btn-primary">
          {t("viewDashboard")}
        </a>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>{t("title", { name: product.name ?? "this product" })}</h1>
      <form onSubmit={handleSubmit} noValidate>
        {mutation.isError ? (
          <ErrorBanner
            message={
              mutation.error instanceof Error ? mutation.error.message : tCommon("genericError")
            }
          />
        ) : null}
        <TextField
          label={t("quantityLabel")}
          type="number"
          min={0}
          step="any"
          inputMode="decimal"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          error={quantityError}
          aria-describedby={quantityError ? quantityErrorId : undefined}
        />
        <SelectField
          label={t("mealSlotLabel")}
          value={mealSlot}
          onChange={(e) => setMealSlot(e.target.value as MealSlot)}
          options={MEAL_SLOTS.map((slot) => ({ value: slot, label: t(`mealSlots.${slot}`) }))}
        />
        <TextField
          label={t("occurredAtLabel")}
          type="datetime-local"
          value={occurredAt}
          onChange={(e) => setOccurredAt(e.target.value)}
        />
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? tCommon("loading") : t("submit")}
        </Button>
      </form>
    </div>
  );
}
