"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRecipe } from "@/lib/hooks/useRecipe";
import { useUnpublishRecipe } from "@/lib/hooks/useUnpublishRecipe";
import { useDeleteRecipe } from "@/lib/hooks/useDeleteRecipe";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import { RecipeNutrientTotals } from "@/components/features/recipes/RecipeNutrientTotals";
import { PublishRecipeButton } from "@/components/features/recipes/PublishRecipeButton";
import { RecipeForm } from "@/components/features/recipes/RecipeForm";

export function RecipeDetailView({ recipeId }: { recipeId: string }) {
  const t = useTranslations("recipes");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const { data, isLoading, isError } = useRecipe(recipeId);
  const unpublishMutation = useUnpublishRecipe(recipeId);
  const deleteMutation = useDeleteRecipe(recipeId);

  if (isLoading) return <LoadingSkeleton label={tCommon("loading")} />;
  if (isError || !data) return <ErrorBanner message={tCommon("genericError")} />;

  if (editing) {
    return <RecipeForm mode="edit" recipe={data} />;
  }

  return (
    <div className="page">
      <h1>{data.title}</h1>
      <p>{data.is_published ? t("statusPublished") : t("statusDraft")}</p>
      <p>{data.instructions}</p>
      <RecipeNutrientTotals
        perRecipe={data.computed_totals.per_recipe}
        perServing={data.computed_totals.per_serving}
      />
      <Button type="button" variant="secondary" onClick={() => setEditing(true)}>
        {t("editAction")}
      </Button>
      {data.is_published ? (
        <Button
          type="button"
          variant="secondary"
          onClick={() => unpublishMutation.mutate()}
          disabled={unpublishMutation.isPending}
        >
          {t("unpublishAction")}
        </Button>
      ) : (
        <PublishRecipeButton recipeId={data.recipe_id} />
      )}
      <Button
        type="button"
        variant="secondary"
        onClick={() =>
          deleteMutation.mutate(undefined, { onSuccess: () => router.push("/recipes") })
        }
        disabled={deleteMutation.isPending}
      >
        {t("deleteAction")}
      </Button>
    </div>
  );
}
