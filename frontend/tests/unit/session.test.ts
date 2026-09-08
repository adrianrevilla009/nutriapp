import { describe, expect, it } from "vitest";
import {
  ACCESS_TOKEN_LIFETIME_SECONDS,
  REFRESH_MARGIN_SECONDS,
  computeRefreshDueAt,
} from "@/lib/session";

describe("computeRefreshDueAt", () => {
  it("schedules a refresh safely before actual expiry (margin applied)", () => {
    const issuedAt = new Date("2026-09-08T08:00:00.000Z");
    const dueAt = computeRefreshDueAt(issuedAt);
    const expectedMs =
      issuedAt.getTime() + (ACCESS_TOKEN_LIFETIME_SECONDS - REFRESH_MARGIN_SECONDS) * 1000;
    expect(dueAt.getTime()).toBe(expectedMs);
    expect(dueAt.getTime()).toBeLessThan(issuedAt.getTime() + ACCESS_TOKEN_LIFETIME_SECONDS * 1000);
  });

  it("is deterministic for a fixed clock input", () => {
    const issuedAt = new Date("2026-09-08T08:00:00.000Z");
    expect(computeRefreshDueAt(issuedAt).getTime()).toBe(computeRefreshDueAt(issuedAt).getTime());
  });
});
