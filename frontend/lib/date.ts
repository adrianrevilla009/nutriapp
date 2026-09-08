/**
 * Local-date formatting helper backing /dashboard's default date
 * (test-plan section 2). "Today" must be the user's LOCAL calendar day,
 * never UTC's -- a user at 11pm local time whose UTC day has already
 * rolled over must still see their own local "today".
 */

/** Formats a Date as YYYY-MM-DD using ITS OWN local getters, never
 * `toISOString()` (which is UTC-based and would silently shift the date
 * near midnight for any non-UTC timezone). */
export function toLocalDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function todayLocalDateString(now: Date = new Date()): string {
  return toLocalDateString(now);
}
