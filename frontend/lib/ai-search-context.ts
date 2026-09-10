/**
 * Journey 2: carries a chosen AI photo-detection candidate's context
 * through the /log/photo -> /search -> /log/[productId] navigation, via
 * URL search params (no client-side state needs to survive the hop).
 * Shared by ProductSearchBox/ProductResultList/ProductResultCard and the
 * /search page shell.
 */
export interface AiSearchContext {
  analysisId: string;
  candidateName: string;
  portionRangeMinG: number;
  portionRangeMaxG: number;
}
