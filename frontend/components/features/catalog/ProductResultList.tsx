import { useTranslations } from "next-intl";
import type { ProductResponse } from "@/schemas/catalog";
import type { AiSearchContext } from "@/lib/ai-search-context";
import { ProductResultCard } from "@/components/features/catalog/ProductResultCard";

export function ProductResultList({
  products,
  query,
  aiContext,
}: {
  products: ProductResponse[];
  query: string;
  aiContext?: AiSearchContext;
}) {
  const t = useTranslations("search");

  if (products.length === 0) {
    return <p>{t("noResults", { query })}</p>;
  }

  return (
    <ul className="result-list" aria-label={t("title")}>
      {products.map((product) => (
        <ProductResultCard key={product.product_id} product={product} aiContext={aiContext} />
      ))}
    </ul>
  );
}
