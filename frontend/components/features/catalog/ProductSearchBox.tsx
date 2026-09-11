"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useSearchProducts } from "@/lib/hooks/useSearchProducts";
import type { AiSearchContext } from "@/lib/ai-search-context";
import type { ProductResponse } from "@/schemas/catalog";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ProductResultList } from "@/components/features/catalog/ProductResultList";

export type { AiSearchContext };

export function ProductSearchBox({
  initialQuery,
  aiContext,
  mode = "log",
  onSelect,
  nested = false,
}: {
  /** Journey 2: pre-fills AND auto-submits the search when arriving from
   * an AI candidate pick (CandidateList's link) -- unset for a plain
   * /search visit, which keeps journey 1's original empty-start
   * behavior unchanged. */
  initialQuery?: string;
  aiContext?: AiSearchContext;
  /** Journey 3: "select" mode is used by IngredientPicker to add a
   * catalog product to a recipe's ingredient list in place, instead of
   * navigating to /log/[productId] -- "log" (default) preserves journeys
   * 1-2's original navigation behavior unchanged (regression-tested). */
  mode?: "log" | "select";
  onSelect?: (product: ProductResponse) => void;
  /** Journey 3: when true, renders WITHOUT its own <form> element -- an
   * accessible `role="search"` <div> plus a plain button instead. Used by
   * IngredientPicker, which is itself nested inside RecipeForm's own
   * <form>: a <form> nested inside another <form> is invalid HTML (jsdom
   * warns loudly about it, and real browsers' form-submission/Enter-key
   * semantics don't behave correctly under it either -- a REAL bug found
   * via this journey's own integration test run, not a hypothetical
   * concern). Default false preserves journeys 1-2's exact existing <form>
   * markup, byte-for-byte, on every other call site. */
  nested?: boolean;
} = {}) {
  const t = useTranslations("search");
  const tPhotoLog = useTranslations("photoLog");
  const tCommon = useTranslations("common");
  const [inputValue, setInputValue] = useState(initialQuery ?? "");
  const [submittedQuery, setSubmittedQuery] = useState(initialQuery ?? "");

  const { data, isLoading, isError, refetch } = useSearchProducts(submittedQuery);

  function runSearch() {
    setSubmittedQuery(inputValue);
  }

  function handleFormSubmit(event: React.FormEvent) {
    event.preventDefault();
    runSearch();
  }

  const searchFields = (
    <>
      <TextField
        label={t("inputLabel")}
        placeholder={t("placeholder")}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
      />
      <Button type={nested ? "button" : "submit"} onClick={nested ? runSearch : undefined}>
        {t("title")}
      </Button>
    </>
  );

  return (
    <div className="page">
      <h1>{t("title")}</h1>
      {aiContext ? (
        <p className="notice">
          {tPhotoLog("searchAiContextBanner", { name: aiContext.candidateName })}
        </p>
      ) : null}
      {nested ? (
        <div role="search">{searchFields}</div>
      ) : (
        <form onSubmit={handleFormSubmit} role="search">
          {searchFields}
        </form>
      )}

      {submittedQuery.trim() === "" ? <p>{t("emptyPrompt")}</p> : null}
      {isLoading ? <LoadingSkeleton label={tCommon("loading")} /> : null}
      {isError ? (
        <div>
          <ErrorBanner message={t("resultsError")} />
          <Button variant="secondary" onClick={() => void refetch()}>
            {tCommon("retry")}
          </Button>
        </div>
      ) : null}
      {data ? (
        <ProductResultList
          products={data.items}
          query={submittedQuery}
          aiContext={aiContext}
          mode={mode}
          onSelect={onSelect}
        />
      ) : null}
    </div>
  );
}
