import { useTranslations } from "next-intl";
import type { RecipeResponse } from "@/schemas/recipe";
import { RecipeCard } from "@/components/features/recipes/RecipeCard";

export function RecipeList({ recipes }: { recipes: RecipeResponse[] }) {
  const t = useTranslations("recipes");
  if (recipes.length === 0) {
    return <p>{t("ownListEmpty")}</p>;
  }
  return (
    <ul className="result-list" aria-label={t("ownListHeading")}>
      {recipes.map((recipe) => (
        <RecipeCard key={recipe.recipe_id} recipe={recipe} />
      ))}
    </ul>
  );
}
