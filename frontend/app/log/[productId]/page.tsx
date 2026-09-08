import { notFound } from "next/navigation";
import { CATALOG_SERVICE_BASE_URL } from "@/lib/server/backend-config";
import { apiFetch, AppError } from "@/lib/api/http-client";
import { ProductResponseSchema } from "@/schemas/catalog";
import { LogFoodEntryForm } from "@/components/features/diary/LogFoodEntryForm";

/**
 * Server component shell: fetches the product detail directly from
 * catalog-service (a server-to-server call, not a browser one -- no CORS
 * concern here even before resolution 1's proxy decision, since this never
 * runs in the browser) and hands it to the client form below.
 */
export default async function LogFoodEntryPage({
  params,
}: {
  params: Promise<{ productId: string }>;
}) {
  const { productId } = await params;

  try {
    const raw = await apiFetch<unknown>(
      `${CATALOG_SERVICE_BASE_URL}/api/v1/catalog/products/${encodeURIComponent(productId)}`,
    );
    const product = ProductResponseSchema.parse(raw);
    return <LogFoodEntryForm product={product} />;
  } catch (err) {
    if (err instanceof AppError && err.status === 404) {
      notFound();
    }
    throw err;
  }
}
