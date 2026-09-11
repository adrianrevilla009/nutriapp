"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useSearchRecipes } from "@/lib/hooks/useSearchRecipes";
import { NotEntitledError } from "@/lib/api/recipes";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { RecipeSearchResultList } from "@/components/features/recipes/RecipeSearchResultList";

export function RecipeSearchBox() {
  const t = useTranslations("recipes");
  const tCommon = useTranslations("common");
  const [inputValue, setInputValue] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const { data, isLoading, isError, error, refetch } = useSearchRecipes(submittedQuery);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (inputValue.trim().length === 0) return; // Blocked client-side -- no query fired.
    setSubmittedQuery(inputValue);
  }

  // Distinguishable via `instanceof`, never a string-match -- three-way
  // non-conflation with empty-results and a genuine 5xx (test-plan
  // section 3).
  const isNotEntitled = error instanceof NotEntitledError;
  const isOtherError = isError && !isNotEntitled;

  return (
    <div className="page">
      <h1>{t("searchTitle")}</h1>
      <form onSubmit={handleSubmit} role="search">
        <TextField
          label={t("searchInputLabel")}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
        />
        <Button type="submit">{t("searchTitle")}</Button>
      </form>

      {submittedQuery.trim() === "" ? <p>{t("searchEmptyPrompt")}</p> : null}
      {isLoading ? <LoadingSkeleton label={tCommon("loading")} /> : null}
      {isNotEntitled ? (
        <div className="notice">
          <p>{t("searchNotEntitled")}</p>
          <Link href="/pro" className="btn btn-primary">
            {t("upgradeAction")}
          </Link>
        </div>
      ) : null}
      {isOtherError ? (
        <div>
          <ErrorBanner message={t("searchError")} />
          <Button variant="secondary" onClick={() => void refetch()}>
            {tCommon("retry")}
          </Button>
        </div>
      ) : null}
      {data ? <RecipeSearchResultList recipes={data.items} query={submittedQuery} /> : null}
    </div>
  );
}
