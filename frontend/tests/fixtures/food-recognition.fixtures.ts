/**
 * Fixtures shaped from
 * services/food-recognition-service/infrastructure/http/schemas/recognition_schemas.py
 * (read verbatim during /implementation-plan's research). Journey 2
 * test-plan section 4/8.
 */
import type { AnalyzePhotoResponse } from "@/schemas/food-recognition";

export const analyzePhotoDetectedFixture: AnalyzePhotoResponse = {
  analysis_id: "55555555-5555-4555-8555-555555555555",
  status: "detected",
  candidates: [
    { name: "Plain Yogurt", portion_range_min_g: 120, portion_range_max_g: 160, confidence: 0.82 },
    { name: "Greek Yogurt", portion_range_min_g: 100, portion_range_max_g: 140, confidence: 0.41 },
    { name: "Fruit Yogurt", portion_range_min_g: 90, portion_range_max_g: 130, confidence: 0.22 },
  ],
  model_version: "claude-haiku-4-5-fixture",
};

export const analyzePhotoUncertainFixture: AnalyzePhotoResponse = {
  analysis_id: "66666666-6666-4666-8666-666666666666",
  status: "uncertain",
  candidates: [
    { name: "Mixed Salad", portion_range_min_g: 80, portion_range_max_g: 200, confidence: 0.35 },
  ],
  model_version: "claude-haiku-4-5-fixture",
};

export const analyzePhotoUnavailableFixture: AnalyzePhotoResponse = {
  analysis_id: "77777777-7777-4777-8777-777777777777",
  status: "unavailable",
  candidates: [],
  model_version: "claude-haiku-4-5-fixture",
};
