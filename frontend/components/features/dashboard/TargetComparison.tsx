import { useTranslations } from "next-intl";
import type { DashboardResponse } from "@/schemas/bff";
import { SectionUnavailable } from "@/components/features/dashboard/SectionUnavailable";

export function TargetComparison({ target }: { target: DashboardResponse["target"] }) {
  const t = useTranslations("dashboard");

  return (
    <section aria-labelledby="target-heading">
      <h2 id="target-heading">{t("target")}</h2>
      {target.status === "unavailable" ? (
        <SectionUnavailable reason={target.reason!} />
      ) : (
        <table>
          <caption className="sr-only">{t("target")}</caption>
          <tbody>
            <tr>
              <th scope="row">{t("calories")}</th>
              <td>{target.data!.calorie_target_kcal} kcal</td>
            </tr>
            <tr>
              <th scope="row">{t("protein")}</th>
              <td>
                {target.data!.protein_g_min}–{target.data!.protein_g_max} g
              </td>
            </tr>
            <tr>
              <th scope="row">{t("fat")}</th>
              <td>{target.data!.fat_g_min} g min</td>
            </tr>
            <tr>
              <th scope="row">{t("carbs")}</th>
              <td>{target.data!.carbs_g} g</td>
            </tr>
          </tbody>
        </table>
      )}
    </section>
  );
}
