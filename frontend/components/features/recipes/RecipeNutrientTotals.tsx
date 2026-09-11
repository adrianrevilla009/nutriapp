import { useTranslations } from "next-intl";
import type { NutrientTotalsResponse } from "@/schemas/recipe";

/**
 * An actual accessible <table>, reusing
 * components/features/dashboard/MicronutrientTable.tsx's established
 * status-aware pattern (accessibility-standards SKILL.md's domain-specific
 * guidance) -- never a chart-only view.
 */
function StatusNote({ status }: { status: NutrientTotalsResponse["macros_status"] }) {
  const t = useTranslations("recipes");
  if (status === "available") return null;
  return <p>{status === "partial" ? t("nutrientsPartial") : t("nutrientsUnavailable")}</p>;
}

function MacroTable({ totals, captionId }: { totals: NutrientTotalsResponse; captionId: string }) {
  const t = useTranslations("recipes");
  return (
    <table>
      <caption className="sr-only" id={captionId}>
        {t("nutrientTotalsCaption")}
      </caption>
      <thead>
        <tr>
          <th scope="col">{t("nutrientColumn")}</th>
          <th scope="col">{t("amountColumn")}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">{t("calories")}</th>
          <td>{totals.macros.calories_kcal}</td>
        </tr>
        <tr>
          <th scope="row">{t("protein")}</th>
          <td>{totals.macros.protein_g}</td>
        </tr>
        <tr>
          <th scope="row">{t("carbs")}</th>
          <td>{totals.macros.carbs_g}</td>
        </tr>
        <tr>
          <th scope="row">{t("fat")}</th>
          <td>{totals.macros.fat_g}</td>
        </tr>
        {totals.micronutrients
          ? Object.entries(totals.micronutrients).map(([name, value]) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{value === null ? "—" : value}</td>
              </tr>
            ))
          : null}
      </tbody>
    </table>
  );
}

export function RecipeNutrientTotals({
  perRecipe,
  perServing,
}: {
  perRecipe: NutrientTotalsResponse;
  perServing: NutrientTotalsResponse;
}) {
  const t = useTranslations("recipes");
  return (
    <div>
      <section aria-labelledby="per-recipe-heading">
        <h2 id="per-recipe-heading">{t("perRecipeHeading")}</h2>
        <StatusNote status={perRecipe.macros_status} />
        <MacroTable totals={perRecipe} captionId="per-recipe-table-caption" />
      </section>
      <section aria-labelledby="per-serving-heading">
        <h2 id="per-serving-heading">{t("perServingHeading")}</h2>
        <StatusNote status={perServing.macros_status} />
        <MacroTable totals={perServing} captionId="per-serving-table-caption" />
      </section>
    </div>
  );
}
