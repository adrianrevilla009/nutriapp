"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useSearchProducts } from "@/lib/hooks/useSearchProducts";
import type { AiSearchContext } from "@/lib/ai-search-context";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ProductResultList } from "@/components/features/catalog/ProductResultList";

export type { AiSearchContext };

export function ProductSearchBox({
  initialQuery,
  aiContext,
}: {
  /** Journey 2: pre-fills AND auto-submits the search when arriving from
   * an AI candidate pick (CandidateList's link) -- unset for a plain
   * /search visit, which keeps journey 1's original empty-start
   * behavior unchanged. */
  initialQuery?: string;
  aiContext?: AiSearchContext;
} = {}) {
  const t = useTranslations("search");
  const tPhotoLog = useTranslations("photoLog");
  const tCommon = useTranslations("common");
  const [inputValue, setInputValue] = useState(initialQuery ?? "");
  const [submittedQuery, setSubmittedQuery] = useState(initialQuery ?? "");

  const { data, isLoading, isError, refetch } = useSearchProducts(submittedQuery);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmittedQuery(inputValue);
  }

  return (
    <div className="page">
      <h1>{t("title")}</h1>
      {aiContext ? (
        <p className="notice">
          {tPhotoLog("searchAiContextBanner", { name: aiContext.candidateName })}
        </p>
      ) : null}
      <form onSubmit={handleSubmit} role="search">
        <TextField
          label={t("inputLabel")}
          placeholder={t("placeholder")}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
        />
        <Button type="submit">{t("title")}</Button>
      </form>

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
        <ProductResultList products={data.items} query={submittedQuery} aiContext={aiContext} />
      ) : null}
    </div>
  );
}
