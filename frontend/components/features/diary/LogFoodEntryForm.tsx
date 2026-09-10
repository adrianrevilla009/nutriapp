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

/**
 * Journey 2: when this product was confirmed from an AI photo detection
 * (rather than a plain catalog search), this carries the context needed
 * to log it as ai_detected-sourced and to pre-fill the quantity from the
 * portion-range estimate -- the macros themselves still come from
 * `product`, never from this context (lib/diary-mapping.ts's
 * "never fabricate macros" guard is the same code path either way).
 */
export interface AiLogContext {
  analysisId: string;
  candidateName: string;
  portionRangeMinG: number;
  portionRangeMaxG: number;
}

function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function defaultQuantityFor(aiContext?: AiLogContext): string {
  if (!aiContext) return "100";
  const midpoint = Math.round((aiContext.portionRangeMinG + aiContext.portionRangeMaxG) / 2);
  return String(midpoint);
}

export function LogFoodEntryForm({
  product,
  aiContext,
}: {
  product: ProductResponse;
  aiContext?: AiLogContext;
}) {
  const t = useTranslations("log");
  const tPhotoLog = useTranslations("photoLog");
  const tCommon = useTranslations("common");
  const quantityErrorId = useId();

  const sourceOverride = aiContext
    ? { source_type: "ai_detected" as const, source_reference_id: aiContext.analysisId }
    : undefined;

  // Upfront check (a dummy quantity is enough to detect the structural
  // "no nutrition data" case) -- this product either can be logged at all,
  // or it can't, REGARDLESS of sourceOverride: the same
  // productToLogFoodEntryRequest call, the same guard, whether this is a
  // plain catalog log or an AI-confirmed one (test-plan section 2's
  // "one code path" requirement, enforced here structurally too).
  const canLog = useMemo(
    () => productToLogFoodEntryRequest(product, 1, "breakfast", new Date(), sourceOverride).ok,
    // sourceOverride is derived fresh from aiContext each render; keyed on
    // aiContext (stable per navigation) rather than the object itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [product, aiContext],
  );

  const [quantity, setQuantity] = useState(() => defaultQuantityFor(aiContext));
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
      sourceOverride,
    );
    if (!mapped.ok) {
      // Structurally unreachable given the canLog guard above, but keeps
      // this branch exhaustive/typed rather than asserting past it.
      return;
    }
    mutation.mutate({ request: mapped.request, correlationId: aiContext?.analysisId });
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
      {aiContext ? (
        <p className="notice">
          {tPhotoLog("aiSourceDisclosure", { name: aiContext.candidateName })}
        </p>
      ) : null}
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
          hint={
            aiContext
              ? tPhotoLog("aiPortionHint", {
                  min: aiContext.portionRangeMinG,
                  max: aiContext.portionRangeMaxG,
                })
              : undefined
          }
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
