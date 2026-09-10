import { describe, expect, it } from "vitest";
import {
  AnalysisStatusSchema,
  AnalyzePhotoResponseSchema,
  FoodCandidateSchema,
} from "@/schemas/food-recognition";
import {
  analyzePhotoDetectedFixture,
  analyzePhotoUncertainFixture,
  analyzePhotoUnavailableFixture,
} from "../fixtures/food-recognition.fixtures";

describe("AnalysisStatusSchema", () => {
  it("accepts exactly detected/uncertain/unavailable", () => {
    expect(AnalysisStatusSchema.safeParse("detected").success).toBe(true);
    expect(AnalysisStatusSchema.safeParse("uncertain").success).toBe(true);
    expect(AnalysisStatusSchema.safeParse("unavailable").success).toBe(true);
  });

  it("rejects any other string", () => {
    expect(AnalysisStatusSchema.safeParse("confirmed").success).toBe(false);
  });
});

describe("FoodCandidateSchema", () => {
  const valid = {
    name: "Plain Yogurt",
    portion_range_min_g: 120,
    portion_range_max_g: 160,
    confidence: 0.7,
  };

  it("parses a valid candidate", () => {
    expect(FoodCandidateSchema.safeParse(valid).success).toBe(true);
  });

  it("rejects confidence outside [0, 1]", () => {
    expect(FoodCandidateSchema.safeParse({ ...valid, confidence: 1.5 }).success).toBe(false);
    expect(FoodCandidateSchema.safeParse({ ...valid, confidence: -0.1 }).success).toBe(false);
  });

  it("rejects a negative portion range", () => {
    expect(FoodCandidateSchema.safeParse({ ...valid, portion_range_min_g: -5 }).success).toBe(
      false,
    );
    expect(FoodCandidateSchema.safeParse({ ...valid, portion_range_max_g: -5 }).success).toBe(
      false,
    );
  });

  it("rejects an inverted portion range (deliberately stricter than the backend)", () => {
    const inverted = { ...valid, portion_range_min_g: 200, portion_range_max_g: 100 };
    expect(FoodCandidateSchema.safeParse(inverted).success).toBe(false);
  });
});

describe("AnalyzePhotoResponseSchema", () => {
  it("parses a detected fixture with 1-3 candidates, at least one >= 0.6 confidence", () => {
    const result = AnalyzePhotoResponseSchema.safeParse(analyzePhotoDetectedFixture);
    expect(result.success).toBe(true);
    expect(analyzePhotoDetectedFixture.candidates.some((c) => c.confidence >= 0.6)).toBe(true);
  });

  it("parses an uncertain fixture where every candidate is below 0.6 confidence", () => {
    const result = AnalyzePhotoResponseSchema.safeParse(analyzePhotoUncertainFixture);
    expect(result.success).toBe(true);
    expect(analyzePhotoUncertainFixture.candidates.every((c) => c.confidence < 0.6)).toBe(true);
  });

  it("parses an unavailable fixture with an empty candidates array", () => {
    const result = AnalyzePhotoResponseSchema.safeParse(analyzePhotoUnavailableFixture);
    expect(result.success).toBe(true);
    expect(analyzePhotoUnavailableFixture.candidates).toEqual([]);
  });

  it("rejects a response with more than 3 candidates", () => {
    const tooMany = {
      ...analyzePhotoDetectedFixture,
      candidates: [
        ...analyzePhotoDetectedFixture.candidates,
        { name: "Fourth", portion_range_min_g: 1, portion_range_max_g: 2, confidence: 0.1 },
      ],
    };
    expect(AnalyzePhotoResponseSchema.safeParse(tooMany).success).toBe(false);
  });

  it("requires a UUID analysis_id and a non-empty model_version", () => {
    expect(
      AnalyzePhotoResponseSchema.safeParse({
        ...analyzePhotoDetectedFixture,
        analysis_id: "not-a-uuid",
      }).success,
    ).toBe(false);
    expect(
      AnalyzePhotoResponseSchema.safeParse({ ...analyzePhotoDetectedFixture, model_version: "" })
        .success,
    ).toBe(false);
  });
});
