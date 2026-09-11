/**
 * Zod schemas mirroring
 * services/food-recognition-service/infrastructure/http/schemas/recognition_schemas.py's
 * AnalyzePhotoResponse/FoodCandidateResponse field-for-field (journey 2
 * implementation plan section 4).
 */
import { z } from "zod";

// Mirrors AnalysisStatus (domain/value_objects/analysis_status.py's
// Literal["detected", "uncertain", "unavailable"]).
export const AnalysisStatusSchema = z.enum(["detected", "uncertain", "unavailable"]);
export type AnalysisStatus = z.infer<typeof AnalysisStatusSchema>;

// Mirrors FoodCandidateResponse.
//
// DELIBERATELY STRICTER THAN THE BACKEND (documented, same precedent
// schemas/bff.ts's envelope check already set in journey 1): the backend's
// own FoodCandidateResponse Pydantic model enforces no ordering between
// portion_range_min_g/max_g -- that invariant lives server-side in the
// PortionRangeGrams domain value object, not re-asserted in the HTTP
// response schema. This schema re-asserts min <= max defensively because
// CandidateList (components/features/recognition/CandidateList.tsx)
// renders this range directly as user-facing text ("approx. NN-NN g"),
// and an inverted range would be confusing/misleading copy, not just an
// internal inconsistency worth silently tolerating.
export const FoodCandidateSchema = z
  .object({
    name: z.string().min(1),
    portion_range_min_g: z.number().nonnegative(),
    portion_range_max_g: z.number().nonnegative(),
    confidence: z.number().min(0).max(1),
  })
  .refine((candidate) => candidate.portion_range_min_g <= candidate.portion_range_max_g, {
    message: "portion_range_min_g must be <= portion_range_max_g",
    path: ["portion_range_min_g"],
  });
export type FoodCandidate = z.infer<typeof FoodCandidateSchema>;

// Mirrors AnalyzePhotoResponse. `candidates` never exceeds 3
// (application/commands/analyze_food_photo.py's MAX_CANDIDATES) -- enforced
// here too as a belt-and-suspenders check on the same backend invariant,
// not a frontend-invented rule.
export const AnalyzePhotoResponseSchema = z.object({
  analysis_id: z.string().uuid(),
  status: AnalysisStatusSchema,
  candidates: z.array(FoodCandidateSchema).max(3),
  model_version: z.string().min(1),
});
export type AnalyzePhotoResponse = z.infer<typeof AnalyzePhotoResponseSchema>;
