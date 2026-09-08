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
): Promise<FoodEntryResponse> {
  const raw = await apiFetch<unknown>("/api/diary/food-entries", {
    method: "POST",
    body: request,
    accessToken,
  });
  return FoodEntryResponseSchema.parse(raw);
}
