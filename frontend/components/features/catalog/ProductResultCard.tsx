import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ProductResponse } from "@/schemas/catalog";

export function ProductResultCard({ product }: { product: ProductResponse }) {
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
        href={`/log/${product.product_id}`}
        className="btn btn-primary"
        aria-label={t("logAction", { name })}
      >
        {t("logAction", { name })}
      </Link>
    </li>
  );
}
