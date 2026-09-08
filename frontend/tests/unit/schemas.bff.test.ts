import { describe, expect, it } from "vitest";
import { DashboardResponseSchema } from "@/schemas/bff";
import {
  allAvailableDashboardFixture,
  allUnavailableDashboardFixture,
  mixedAvailabilityDashboardFixture,
} from "../fixtures/bff.fixtures";

describe("DashboardResponseSchema", () => {
  it("parses the all-available combination", () => {
    expect(DashboardResponseSchema.parse(allAvailableDashboardFixture)).toEqual(
      allAvailableDashboardFixture,
    );
  });

  it("parses the mixed-availability combination (downstream_error + not_yet_computed)", () => {
    expect(DashboardResponseSchema.parse(mixedAvailabilityDashboardFixture)).toEqual(
      mixedAvailabilityDashboardFixture,
    );
  });

  it("parses the all-unavailable combination", () => {
    expect(DashboardResponseSchema.parse(allUnavailableDashboardFixture)).toEqual(
      allUnavailableDashboardFixture,
    );
  });

  it("rejects status: available paired with null data (stricter than the backend's own Pydantic model)", () => {
    const invalid = {
      ...allAvailableDashboardFixture,
      target: { status: "available", reason: null, data: null },
    };
    expect(DashboardResponseSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects status: unavailable paired with non-null data", () => {
    const invalid = {
      ...allAvailableDashboardFixture,
      target: {
        status: "unavailable",
        reason: "downstream_error",
        data: allAvailableDashboardFixture.target.data,
      },
    };
    expect(DashboardResponseSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects status: unavailable with a null reason", () => {
    const invalid = {
      ...allAvailableDashboardFixture,
      target: { status: "unavailable", reason: null, data: null },
    };
    expect(DashboardResponseSchema.safeParse(invalid).success).toBe(false);
  });
});
