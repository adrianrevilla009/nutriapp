"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useOwnRecipes } from "@/lib/hooks/useOwnRecipes";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { RecipeList } from "@/components/features/recipes/RecipeList";

export function OwnRecipesView({ alreadyPro = false }: { alreadyPro?: boolean }) {
  const t = useTranslations("recipes");
  const tCommon = useTranslations("common");
  const { data, isLoading, isError } = useOwnRecipes();

  return (
    <div className="page">
      <h1>{t("ownListHeading")}</h1>
      {alreadyPro ? <p className="notice">{t("alreadyProNotice")}</p> : null}
      <Link href="/recipes/new" className="btn btn-primary">
        {t("newRecipeAction")}
      </Link>
      {isLoading ? <LoadingSkeleton label={tCommon("loading")} /> : null}
      {isError ? <ErrorBanner message={tCommon("genericError")} /> : null}
      {data ? <RecipeList recipes={data.items} /> : null}
    </div>
  );
}
