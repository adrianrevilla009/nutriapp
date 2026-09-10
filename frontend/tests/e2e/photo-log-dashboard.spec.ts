import { expect, test, type Route } from "@playwright/test";
import { SEEDED_PRODUCT_NAME, SEEDED_USER_EMAIL, SEEDED_USER_PASSWORD } from "./seed/constants";

/**
 * Journey 2 (photo upload -> AI detection -> logged entry), journey 2
 * test-plan section 6. Prerequisite: `pnpm test:e2e:seed` has been run
 * against the SAME docker-compose stack this spec targets (same seeded
 * user/product journey 1's spec uses -- reused here so the AI candidate's
 * name matches a real, searchable catalog product).
 *
 * food-recognition-service's ClaudeVisionAdapter calls the real Anthropic
 * API -- no fake/stub vision provider exists in that service (confirmed
 * by reading infrastructure/composition_root.py). A live-model call in
 * default CI is both non-deterministic and against
 * media-recognition-conventions SKILL.md's own testing rule ("any live-
 * model integration test is explicitly marked and excluded from the
 * default CI run"). So:
 *
 * - The two "candidate found" cases below intercept ONLY the browser's
 *   call to /api/food-recognition/photos/analyze (via page.route()) with
 *   a fixture-shaped response -- every other call in the journey (/search,
 *   /log/[productId], /dashboard, and their real Route Handler -> real
 *   backend hops) runs against the actual docker-compose stack, same as
 *   journey 1's spec.
 * - The "unavailable" case is NOT intercepted -- it runs fully live
 *   against food-recognition-service. This is deterministic without any
 *   special flag: docker-compose.yml sets no
 *   FOOD_RECOGNITION_SERVICE_ANTHROPIC_API_KEY, so the real Anthropic call
 *   fails with an auth error, which ClaudeVisionAdapter (per its own
 *   `except anthropic.APIStatusError` handling) converts to
 *   VisionRecognitionUnavailableError -> status: "unavailable" --
 *   confirmed by reading that adapter's source, not assumed. If a real
 *   key is ever configured for local/CI compose, this specific case would
 *   need re-visiting (flagged, not silently relied upon forever).
 */

const FIXTURE_ANALYSIS_ID = "55555555-5555-4555-8555-555555555555";

function detectedFixtureResponse() {
  return {
    analysis_id: FIXTURE_ANALYSIS_ID,
    status: "detected",
    candidates: [
      {
        name: SEEDED_PRODUCT_NAME,
        portion_range_min_g: 120,
        portion_range_max_g: 160,
        confidence: 0.82,
      },
      { name: "Greek Yogurt", portion_range_min_g: 100, portion_range_max_g: 140, confidence: 0.3 },
    ],
    model_version: "claude-haiku-4-5-e2e-fixture",
  };
}

async function interceptAnalyze(page: import("@playwright/test").Page, body: unknown) {
  await page.route("**/api/food-recognition/photos/analyze", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

async function loginAndGoToPhotoUpload(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel(/email address/i).fill(SEEDED_USER_EMAIL);
  await page.getByLabel(/^password$/i).fill(SEEDED_USER_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/search/);

  await page.goto("/log/photo");
  await page.getByLabel(/photo of your food/i).setInputFiles({
    name: "meal.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xdb, 0x00, 0x00, 0x00]),
  });
}

test.describe("upload a food photo -> AI detection -> logged entry (journey 2)", () => {
  test("candidate found: pick a candidate, confirm via search, log it as ai_detected, see it on the dashboard", async ({
    page,
  }) => {
    await interceptAnalyze(page, detectedFixtureResponse());
    await loginAndGoToPhotoUpload(page);
    await page.getByRole("button", { name: /analyze photo/i }).click();

    await expect(page.getByRole("heading", { level: 2 })).toContainText(/possible match/i);
    const useThisLink = page
      .getByRole("listitem")
      .filter({ hasText: SEEDED_PRODUCT_NAME })
      .getByRole("link", { name: /use this/i });
    await expect(useThisLink).toBeVisible();
    await useThisLink.click();

    // Landed on /search, pre-filled and auto-submitted with the
    // candidate's name -- the banner names it, and the seeded product
    // (a real catalog-service row) appears in real results.
    await expect(page).toHaveURL(/\/search\?/);
    await expect(page.getByText(/matching your photo detection/i)).toBeVisible();
    const logLink = page.getByRole("link", { name: new RegExp(`log ${SEEDED_PRODUCT_NAME}`, "i") });
    await expect(logLink).toBeVisible();
    await logLink.click();

    // /log/[productId]?aiAnalysisId=... -- the AI-sourced banner and the
    // portion-range-midpoint-prefilled quantity (120-160 -> 140).
    await expect(page).toHaveURL(/\/log\/.*aiAnalysisId=/);
    await expect(page.getByText(/identified from your photo/i)).toBeVisible();
    await expect(page.getByLabel(/quantity/i)).toHaveValue("140");

    await page.getByRole("button", { name: /log entry/i }).click();
    await expect(page.getByText(/may take a moment to update/i)).toBeVisible();

    await page.getByRole("link", { name: /view dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(async () => {
      await page.getByRole("button", { name: /refresh/i }).click();
      await expect(page.getByRole("row", { name: /calories/i })).not.toContainText("0 kcal");
    }).toPass({ timeout: 30_000, intervals: [2_000] });
  });

  test("none of these: rejects every candidate and completes the existing manual catalog path", async ({
    page,
  }) => {
    await interceptAnalyze(page, detectedFixtureResponse());
    await loginAndGoToPhotoUpload(page);
    await page.getByRole("button", { name: /analyze photo/i }).click();
    await expect(page.getByRole("heading", { level: 2 })).toContainText(/possible match/i);

    await page.getByRole("link", { name: /search manually/i }).click();

    // Plain /search, no AI params/banner -- the manual escape hatch works
    // regardless of what the (intercepted) analysis returned.
    await expect(page).toHaveURL("/search");
    await expect(page.getByText(/matching your photo detection/i)).not.toBeVisible();

    await page.getByLabel(/search products/i).fill(SEEDED_PRODUCT_NAME);
    await page.getByRole("button", { name: /find a food to log/i }).click();
    const logLink = page.getByRole("link", { name: new RegExp(`log ${SEEDED_PRODUCT_NAME}`, "i") });
    await expect(logLink).toBeVisible();
    await logLink.click();

    // No AI context on this path -- plain catalog_product logging.
    await expect(page).toHaveURL(/\/log\/(?!.*aiAnalysisId)/);
    await expect(page.getByText(/identified from your photo/i)).not.toBeVisible();
    await page.getByLabel(/quantity/i).fill("150");
    await page.getByRole("button", { name: /log entry/i }).click();
    await expect(page.getByText(/may take a moment to update/i)).toBeVisible();
  });

  test("unavailable (genuinely live, no interception): honest fallback state, with a working manual-search link", async ({
    page,
  }) => {
    await loginAndGoToPhotoUpload(page);
    await page.getByRole("button", { name: /analyze photo/i }).click();

    // Real network hop to food-recognition-service -- no ANTHROPIC key is
    // configured in docker-compose.yml, so this is deterministic (see
    // this file's header comment), but the vision call's own retry/
    // circuit-breaker budget means this can take a few seconds longer
    // than the intercepted cases.
    await expect(page.getByRole("heading", { level: 2 })).toContainText(/couldn't analyze/i, {
      timeout: 15_000,
    });
    await expect(page.getByRole("alert")).not.toBeVisible();

    const manualLink = page.getByRole("link", { name: /search manually/i });
    await expect(manualLink).toBeVisible();
    await manualLink.click();
    await expect(page).toHaveURL("/search");
  });
});
