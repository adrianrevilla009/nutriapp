/**
 * Fixtures shaped from
 * services/bff-service/infrastructure/http/schemas/dashboard_schemas.py
 * (read verbatim during /implementation-plan's research), covering all
 * three status/reason combinations that actually occur (test-plan
 * section 4).
 */
import type { DashboardResponse } from "@/schemas/bff";

export const allAvailableDashboardFixture: DashboardResponse = {
  diary_summary: {
    status: "available",
    reason: null,
    data: {
      total_calories_kcal: 610,
      total_protein_g: 35,
      total_carbs_g: 47,
      total_fat_g: 33,
      total_water_ml: 1200,
      fasting_windows_ended: 0,
    },
  },
  nutrient_totals: {
    status: "available",
    reason: null,
    data: {
      calories_kcal: 610,
      protein_g: 35,
      carbs_g: 47,
      fat_g: 33,
      micronutrients: { calcium_mg: 121, iron_mg: 0.05 },
      micronutrients_status: "available",
      is_estimated: false,
    },
  },
  target: {
    status: "available",
    reason: null,
    data: {
      calorie_target_kcal: 2000,
      protein_g_min: 90,
      protein_g_max: 150,
      fat_g_min: 55,
      carbs_g: 220,
      goal_type: "maintain",
    },
  },
};

export const mixedAvailabilityDashboardFixture: DashboardResponse = {
  diary_summary: allAvailableDashboardFixture.diary_summary,
  nutrient_totals: {
    status: "unavailable",
    reason: "downstream_error",
    data: null,
  },
  target: {
    status: "unavailable",
    reason: "not_yet_computed",
    data: null,
  },
};

export const allUnavailableDashboardFixture: DashboardResponse = {
  diary_summary: { status: "unavailable", reason: "downstream_error", data: null },
  nutrient_totals: { status: "unavailable", reason: "downstream_error", data: null },
  target: { status: "unavailable", reason: "downstream_error", data: null },
};
