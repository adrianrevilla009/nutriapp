import { useTranslations } from "next-intl";
import type { DashboardResponse } from "@/schemas/bff";
import { SectionUnavailable } from "@/components/features/dashboard/SectionUnavailable";

export function MacroTotalsCard({
  diarySummary,
  nutrientTotals,
}: {
  diarySummary: DashboardResponse["diary_summary"];
  nutrientTotals: DashboardResponse["nutrient_totals"];
}) {
  const t = useTranslations("dashboard");

  return (
    <section aria-labelledby="macro-totals-heading">
      <h2 id="macro-totals-heading">{t("nutrientTotals")}</h2>
      {nutrientTotals.status === "unavailable" ? (
        <SectionUnavailable reason={nutrientTotals.reason!} />
      ) : (
        <table>
          <caption className="sr-only">{t("nutrientTotals")}</caption>
          <tbody>
            <tr>
              <th scope="row">{t("calories")}</th>
              <td>{nutrientTotals.data!.calories_kcal} kcal</td>
            </tr>
            <tr>
              <th scope="row">{t("protein")}</th>
              <td>{nutrientTotals.data!.protein_g} g</td>
            </tr>
            <tr>
              <th scope="row">{t("carbs")}</th>
              <td>{nutrientTotals.data!.carbs_g} g</td>
            </tr>
            <tr>
              <th scope="row">{t("fat")}</th>
              <td>{nutrientTotals.data!.fat_g} g</td>
            </tr>
          </tbody>
        </table>
      )}

      <h2>{t("diarySummary")}</h2>
      {diarySummary.status === "unavailable" ? (
        <SectionUnavailable reason={diarySummary.reason!} />
      ) : (
        <table>
          <caption className="sr-only">{t("diarySummary")}</caption>
          <tbody>
            <tr>
              <th scope="row">{t("water")}</th>
              <td>{diarySummary.data!.total_water_ml} ml</td>
            </tr>
          </tbody>
        </table>
      )}
    </section>
  );
}
