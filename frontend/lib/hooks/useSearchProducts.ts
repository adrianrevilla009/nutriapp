"use client";

import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "@/lib/api/catalog";

/**
 * Catalog search doesn't need a token at all -- catalog-service's search
 * endpoint is unauthenticated at the API level (search_routes.py carries
 * no get_authenticated_user_id dependency); implementation plan section 4.
 */
export function useSearchProducts(query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: ["catalog", "search", trimmed],
    queryFn: () => searchProducts({ q: trimmed }),
    enabled: trimmed.length > 0,
    // Catalog data changes far less often than diary/dashboard data --
    // docs/frontend-architecture.md section 2's "staleTime tuned per data
    // volatility" guidance.
    staleTime: 5 * 60 * 1000,
  });
}
