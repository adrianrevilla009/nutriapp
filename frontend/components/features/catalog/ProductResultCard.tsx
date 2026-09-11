import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ProductResponse } from "@/schemas/catalog";
import type { AiSearchContext } from "@/lib/ai-search-context";

function logHref(productId: string, aiContext?: AiSearchContext): string {
  if (!aiContext) return `/log/${productId}`;
  const params = new URLSearchParams({
    aiAnalysisId: aiContext.analysisId,
    aiCandidateName: aiContext.candidateName,
    aiPortionMinG: String(aiContext.portionRangeMinG),
    aiPortionMaxG: String(aiContext.portionRangeMaxG),
  });
  return `/log/${productId}?${params.toString()}`;
}

export function ProductResultCard({
  product,
  aiContext,
}: {
  product: ProductResponse;
  aiContext?: AiSearchContext;
}) {
  const t = useTranslations("search");
  const name = product.name ?? "Unnamed product";
  const panel = product.nutrition_per_100g;

  return (
    <li className="result-item">
      <div>
        <strong>{name}</strong>
        {product.brand ? <span> — {product.brand}</span> : null}
        {panel ? (
          <p>
            {t("perHundredGrams", {
              calories: panel.energy_kcal ?? "—",
              protein: panel.protein_g ?? "—",
              carbs: panel.carbohydrates_g ?? "—",
              fat: panel.fat_g ?? "—",
            })}
          </p>
        ) : null}
      </div>
      <Link
        href={logHref(product.product_id, aiContext)}
        className="btn btn-primary"
        aria-label={t("logAction", { name })}
      >
        {t("logAction", { name })}
      </Link>
    </li>
  );
}
