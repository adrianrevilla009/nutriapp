import { ProductSearchBox } from "@/components/features/catalog/ProductSearchBox";
import type { AiSearchContext } from "@/lib/ai-search-context";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    aiAnalysisId?: string;
    aiCandidateName?: string;
    aiPortionMinG?: string;
    aiPortionMaxG?: string;
  }>;
}) {
  const sp = await searchParams;

  const aiContext: AiSearchContext | undefined =
    sp.aiAnalysisId && sp.aiCandidateName && sp.aiPortionMinG && sp.aiPortionMaxG
      ? {
          analysisId: sp.aiAnalysisId,
          candidateName: sp.aiCandidateName,
          portionRangeMinG: Number(sp.aiPortionMinG),
          portionRangeMaxG: Number(sp.aiPortionMaxG),
        }
      : undefined;

  return <ProductSearchBox initialQuery={sp.q} aiContext={aiContext} />;
}
