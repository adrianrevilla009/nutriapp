import { afterEach, describe, expect, it, vi } from "vitest";
import { toLocalDateString, todayLocalDateString } from "@/lib/date";

describe("toLocalDateString / todayLocalDateString", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("formats using the Date object's own local getters", () => {
    const date = new Date(2026, 8, 8); // September 8 2026, local time, month is 0-indexed
    expect(toLocalDateString(date)).toBe("2026-09-08");
  });

  it("pads single-digit month/day", () => {
    const date = new Date(2026, 0, 5); // January 5 2026
    expect(toLocalDateString(date)).toBe("2026-01-05");
  });

  it("uses the LOCAL calendar day even when UTC has already rolled over to the next day", () => {
    // 2026-09-08T23:30 in a UTC-8 timezone is 2026-09-09T07:30 UTC --
    // toISOString() would report the 9th; this helper must still report
    // the LOCAL day, the 8th.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 8, 23, 30, 0));
    const now = new Date();
    // Sanity: this Date's own local getters really do say the 8th,
    // regardless of the test runner's actual host timezone.
    expect(now.getDate()).toBe(8);
    expect(todayLocalDateString(now)).toBe("2026-09-08");
  });

  it("is deterministic for a fixed input", () => {
    const date = new Date(2026, 8, 8, 12, 0, 0);
    expect(toLocalDateString(date)).toBe(toLocalDateString(date));
  });
});
