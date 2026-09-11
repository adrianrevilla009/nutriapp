import Link from "next/link";
import { useTranslations } from "next-intl";
import type { RecipeResponse } from "@/schemas/recipe";

export function RecipeCard({ recipe }: { recipe: RecipeResponse }) {
  const t = useTranslations("recipes");
  return (
    <li className="result-item">
      <div>
        <strong>{recipe.title}</strong>
        <p>{recipe.is_published ? t("statusPublished") : t("statusDraft")}</p>
      </div>
      <Link
        href={`/recipes/${recipe.recipe_id}`}
        className="btn btn-primary"
        aria-label={t("viewAction", { title: recipe.title })}
      >
        {t("viewAction", { title: recipe.title })}
      </Link>
    </li>
  );
}
