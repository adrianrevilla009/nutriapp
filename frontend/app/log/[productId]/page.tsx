import { notFound } from "next/navigation";
import { CATALOG_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { apiFetch, AppError } from "@/lib/api/http-client";
import { ProductResponseSchema } from "@/schemas/catalog";
import { LogFoodEntryForm, type AiLogContext } from "@/components/features/diary/LogFoodEntryForm";

/**
 * Server component shell: fetches the product detail directly from
 * catalog-service (a server-to-server call, not a browser one -- no CORS
 * concern here even before resolution 1's proxy decision, since this never
 * runs in the browser) and hands it to the client form below.
 *
 * Journey 2: when arriving from the AI photo-detection flow
 * (components/features/recognition/CandidateList.tsx's link), the
 * ai* search params carry the food-recognition analysis context through
 * this otherwise-unauthenticated navigation -- no client-side state
 * survives the /log/photo -> /search -> /log/[productId] hop, it's all in
 * the URL.
 */
export default async function LogFoodEntryPage({
  params,
  searchParams,
}: {
  params: Promise<{ productId: string }>;
  searchParams: Promise<{
    aiAnalysisId?: string;
    aiCandidateName?: string;
    aiPortionMinG?: string;
    aiPortionMaxG?: string;
  }>;
}) {
  const { productId } = await params;
  const sp = await searchParams;

  const aiContext: AiLogContext | undefined =
    sp.aiAnalysisId && sp.aiCandidateName && sp.aiPortionMinG && sp.aiPortionMaxG
      ? {
          analysisId: sp.aiAnalysisId,
          candidateName: sp.aiCandidateName,
          portionRangeMinG: Number(sp.aiPortionMinG),
          portionRangeMaxG: Number(sp.aiPortionMaxG),
        }
      : undefined;

  try {
    const raw = await apiFetch<unknown>(
      `${CATALOG_SERVICE_BASE_URL}/api/v1/catalog/products/${encodeURIComponent(productId)}`,
    );
    const product = ProductResponseSchema.parse(raw);
    return <LogFoodEntryForm product={product} aiContext={aiContext} />;
  } catch (err) {
    if (err instanceof AppError && err.status === 404) {
      notFound();
    }
    throw err;
  }
}
