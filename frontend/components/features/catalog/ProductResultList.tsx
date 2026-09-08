import { useTranslations } from "next-intl";
import type { ProductResponse } from "@/schemas/catalog";
import { ProductResultCard } from "@/components/features/catalog/ProductResultCard";

export function ProductResultList({
  products,
  query,
}: {
  products: ProductResponse[];
  query: string;
}) {
  const t = useTranslations("search");

  if (products.length === 0) {
    return <p>{t("noResults", { query })}</p>;
  }

  return (
    <ul className="result-list" aria-label={t("title")}>
      {products.map((product) => (
        <ProductResultCard key={product.product_id} product={product} />
      ))}
    </ul>
  );
}
