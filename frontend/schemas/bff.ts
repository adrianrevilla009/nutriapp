/**
 * Zod schemas mirroring
 * services/bff-service/infrastructure/http/schemas/dashboard_schemas.py
 * field-for-field, plus one deliberately STRICTER invariant than the
 * backend's own Pydantic model (see the discriminated-union note below --
 * test-plan section 1).
 */
import { z } from "zod";

const SectionStatusSchema = z.enum(["available", "unavailable"]);
const UnavailableReasonSchema = z.enum(["downstream_error", "not_yet_computed"]);

export const DiarySummarySectionSchema = z.object({
  total_calories_kcal: z.number(),
  total_protein_g: z.number(),
  total_carbs_g: z.number(),
  total_fat_g: z.number(),
  total_water_ml: z.number(),
  fasting_windows_ended: z.number().int(),
});

export const NutrientTotalsSectionSchema = z.object({
  calories_kcal: z.number(),
  protein_g: z.number(),
  carbs_g: z.number(),
  fat_g: z.number(),
  micronutrients: z.record(z.string(), z.number().nullable()).nullable(),
  micronutrients_status: z.string(),
  is_estimated: z.boolean(),
});

export const NutritionTargetSectionSchema = z.object({
  calorie_target_kcal: z.number(),
  protein_g_min: z.number(),
  protein_g_max: z.number(),
  fat_g_min: z.number(),
  carbs_g: z.number(),
  goal_type: z.string(),
});

/**
 * Builds a section-envelope schema that is STRICTER than the backend's own
 * `status`/`reason`/`data` Pydantic model: the real backend never sends
 * `status: "available"` with `data: null` (or `status: "unavailable"` with
 * non-null `data`), but nothing in `dashboard_schemas.py` structurally
 * prevents it. This frontend's rendering logic (components/features/dashboard)
 * depends on the pairing holding, so it is enforced here via
 * `.superRefine`, deliberately adding an invariant the backend doesn't
 * enforce at the type level -- documented per test-plan section 1 as the
 * one place this codebase is stricter than the API it mirrors.
 */
function sectionEnvelope<DataSchema extends z.ZodTypeAny>(dataSchema: DataSchema) {
  return z
    .object({
      status: SectionStatusSchema,
      reason: UnavailableReasonSchema.nullable(),
      data: dataSchema.nullable(),
    })
    .superRefine((value, ctx) => {
      if (value.status === "available" && value.data === null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'status "available" must carry non-null data.',
          path: ["data"],
        });
      }
      if (value.status === "unavailable" && value.data !== null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'status "unavailable" must carry null data.',
          path: ["data"],
        });
      }
      if (value.status === "unavailable" && value.reason === null) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'status "unavailable" must carry a reason.',
          path: ["reason"],
        });
      }
    });
}

export const DiarySummaryEnvelopeSchema = sectionEnvelope(DiarySummarySectionSchema);
export const NutrientTotalsEnvelopeSchema = sectionEnvelope(NutrientTotalsSectionSchema);
export const NutritionTargetEnvelopeSchema = sectionEnvelope(NutritionTargetSectionSchema);

export const DashboardResponseSchema = z.object({
  diary_summary: DiarySummaryEnvelopeSchema,
  nutrient_totals: NutrientTotalsEnvelopeSchema,
  target: NutritionTargetEnvelopeSchema,
});
export type DashboardResponse = z.infer<typeof DashboardResponseSchema>;
export type SectionStatus = z.infer<typeof SectionStatusSchema>;
export type UnavailableReason = z.infer<typeof UnavailableReasonSchema>;
