import { describe, expect, it } from "vitest";
import {
  FoodEntryResponseSchema,
  FoodSourceSnapshotSchema,
  LogFoodEntryRequestSchema,
  MacroSnapshotSchema,
} from "@/schemas/diary";
import { foodEntryResponseFixture } from "../fixtures/diary.fixtures";

describe("MacroSnapshotSchema", () => {
  it("rejects a negative value in any of the four fields", () => {
    const base = { calories_kcal: 1, protein_g: 1, carbs_g: 1, fat_g: 1 };
    for (const field of Object.keys(base) as (keyof typeof base)[]) {
      const withNegative = { ...base, [field]: -1 };
      expect(MacroSnapshotSchema.safeParse(withNegative).success).toBe(false);
    }
  });

  it("accepts all-zero macros", () => {
    expect(
      MacroSnapshotSchema.safeParse({ calories_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 })
        .success,
    ).toBe(true);
  });
});

describe("FoodSourceSnapshotSchema", () => {
  const validMacros = { calories_kcal: 1, protein_g: 1, carbs_g: 1, fat_g: 1 };

  it("rejects quantity <= 0", () => {
    expect(
      FoodSourceSnapshotSchema.safeParse({
        name: "x",
        quantity: 0,
        unit: "g",
        macros_per_unit: validMacros,
      }).success,
    ).toBe(false);
  });

  it("accepts a positive quantity", () => {
    expect(
      FoodSourceSnapshotSchema.safeParse({
        name: "x",
        quantity: 100,
        unit: "g",
        macros_per_unit: validMacros,
      }).success,
    ).toBe(true);
  });
});

describe("LogFoodEntryRequestSchema", () => {
  it("requires an ISO-8601 datetime STRING for occurred_at, not a Date object", () => {
    const withDateObject = {
      source: {
        source_type: "catalog_product",
        source_reference_id: "x",
        snapshot: {
          name: "x",
          quantity: 1,
          unit: "g",
          macros_per_unit: foodEntryResponseFixture.source.snapshot.macros_per_unit,
        },
      },
      meal_slot: "breakfast",
      occurred_at: new Date(),
    };
    expect(LogFoodEntryRequestSchema.safeParse(withDateObject).success).toBe(false);
  });

  it("accepts an ISO-8601 string with a numeric offset", () => {
    const valid = {
      source: {
        source_type: "catalog_product",
        source_reference_id: "x",
        snapshot: {
          name: "x",
          quantity: 1,
          unit: "g",
          macros_per_unit: foodEntryResponseFixture.source.snapshot.macros_per_unit,
        },
      },
      meal_slot: "breakfast",
      occurred_at: "2026-09-08T08:00:00+00:00",
    };
    expect(LogFoodEntryRequestSchema.safeParse(valid).success).toBe(true);
  });
});

describe("FoodEntryResponseSchema", () => {
  it("round-trips the real backend response shape", () => {
    expect(FoodEntryResponseSchema.parse(foodEntryResponseFixture)).toEqual(
      foodEntryResponseFixture,
    );
  });
});
