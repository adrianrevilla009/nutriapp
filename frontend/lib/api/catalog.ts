/**
 * Browser-facing catalog client -- calls this app's own
 * app/api/catalog/* Route Handlers (implementation plan resolution 1),
 * which in turn call catalog-service's already-public, unauthenticated
 * search/product-detail endpoints.
 */
import { apiFetch } from "@/lib/api/http-client";
import {
  ProductResponseSchema,
  ProductSearchResponseSchema,
  type ProductResponse,
  type ProductSearchResponse,
} from "@/schemas/catalog";

export interface SearchProductsParams {
  q: string;
  page?: number;
  pageSize?: number;
}

export async function searchProducts({
  q,
  page = 1,
  pageSize = 20,
}: SearchProductsParams): Promise<ProductSearchResponse> {
  const params = new URLSearchParams({
    q,
    page: String(page),
    page_size: String(pageSize),
  });
  const raw = await apiFetch<unknown>(`/api/catalog/search?${params.toString()}`);
  return ProductSearchResponseSchema.parse(raw);
}

export async function getProductById(productId: string): Promise<ProductResponse> {
  const raw = await apiFetch<unknown>(`/api/catalog/products/${encodeURIComponent(productId)}`);
  return ProductResponseSchema.parse(raw);
}
