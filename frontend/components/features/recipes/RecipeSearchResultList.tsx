import { useTranslations } from "next-intl";
import type { RecipeResponse } from "@/schemas/recipe";

export function RecipeSearchResultList({
  recipes,
  query,
}: {
  recipes: RecipeResponse[];
  query: string;
}) {
  const t = useTranslations("recipes");
  if (recipes.length === 0) {
    return <p>{t("searchNoResults", { query })}</p>;
  }
  return (
    <ul className="result-list" aria-label={t("searchTitle")}>
      {recipes.map((recipe) => (
        <li key={recipe.recipe_id} className="result-item">
          <strong>{recipe.title}</strong>
          <p>
            {t("perServingSummary", {
              servings: recipe.servings,
              calories: recipe.computed_totals.per_serving.macros.calories_kcal,
              protein: recipe.computed_totals.per_serving.macros.protein_g,
              carbs: recipe.computed_totals.per_serving.macros.carbs_g,
              fat: recipe.computed_totals.per_serving.macros.fat_g,
            })}
          </p>
        </li>
      ))}
    </ul>
  );
}
