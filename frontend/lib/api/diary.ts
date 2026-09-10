/**
 * Browser-facing diary client -- calls this app's own
 * app/api/diary/food-entries Route Handler (implementation plan
 * resolution 1), which forwards the caller's access token to
 * diary-service's authenticated POST /api/v1/diary/food-entries.
 */
import { apiFetch } from "@/lib/api/http-client";
import {
  FoodEntryResponseSchema,
  type FoodEntryResponse,
  type LogFoodEntryRequest,
} from "@/schemas/diary";

export async function logFoodEntry(
  request: LogFoodEntryRequest,
  accessToken: string,
  correlationId?: string,
): Promise<FoodEntryResponse> {
  const raw = await apiFetch<unknown>("/api/diary/food-entries", {
    method: "POST",
    body: request,
    accessToken,
    // Journey 2 / architecture-agent finding: when this entry originates
    // from an AI photo detection, the caller passes the food-recognition
    // analysis_id here so it flows into FoodEntryLogged's own
    // correlation_id metadata (diary-service's get_correlation_id reads
    // X-Correlation-Id, falling back to a generated UUID) -- traceability
    // back to the FoodPhotoAnalyzed event doesn't rely on
    // source.source_reference_id alone.
    extraHeaders: correlationId ? { "X-Correlation-Id": correlationId } : undefined,
  });
  return FoodEntryResponseSchema.parse(raw);
}
