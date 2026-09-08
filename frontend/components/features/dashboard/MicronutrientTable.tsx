import { useTranslations } from "next-intl";
import type { DashboardResponse } from "@/schemas/bff";
import { SectionUnavailable } from "@/components/features/dashboard/SectionUnavailable";

/**
 * An actual accessible <table>, not a chart-only view -- data-dense
 * nutrient breakdowns must have a non-visual equivalent
 * (accessibility-standards SKILL.md's domain-specific guidance).
 */
export function MicronutrientTable({
  nutrientTotals,
}: {
  nutrientTotals: DashboardResponse["nutrient_totals"];
}) {
  const t = useTranslations("dashboard");

  if (nutrientTotals.status === "unavailable") {
    return (
      <section aria-labelledby="micronutrients-heading">
        <h2 id="micronutrients-heading">{t("micronutrients")}</h2>
        <SectionUnavailable reason={nutrientTotals.reason!} />
      </section>
    );
  }

  const micronutrients = nutrientTotals.data!.micronutrients;
  if (!micronutrients || Object.keys(micronutrients).length === 0) {
    return (
      <section aria-labelledby="micronutrients-heading">
        <h2 id="micronutrients-heading">{t("micronutrients")}</h2>
        <p>{t("micronutrientsUnavailable")}</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="micronutrients-heading">
      <h2 id="micronutrients-heading">{t("micronutrients")}</h2>
      <table>
        <caption className="sr-only">{t("micronutrients")}</caption>
        <thead>
          <tr>
            <th scope="col">Nutrient</th>
            <th scope="col">Amount</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(micronutrients).map(([name, value]) => (
            <tr key={name}>
              <th scope="row">{name}</th>
              <td>{value === null ? "—" : value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
