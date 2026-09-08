import { expect, test } from "@playwright/test";
import { SEEDED_PRODUCT_NAME, SEEDED_USER_EMAIL, SEEDED_USER_PASSWORD } from "./seed/constants";

/**
 * Full journey 1 (implementation plan section 1 / test-plan section 6):
 * login (starting from a pre-verified seeded user, resolution 2 -- NOT the
 * real register -> email -> verify path) -> search -> log -> dashboard.
 *
 * Prerequisite: `pnpm test:e2e:seed` has been run against the SAME
 * docker-compose stack this spec targets. Requires Docker/docker-compose
 * -- see this repo's frontend implementation plan section 9 for the
 * documented environment caveat if that isn't available.
 */
test.describe("register -> log a food item -> see totals (journey 1)", () => {
  test("logs in, logs a searched product, and sees updated dashboard totals", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email address/i).fill(SEEDED_USER_EMAIL);
    await page.getByLabel(/^password$/i).fill(SEEDED_USER_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/search/);
    await page.getByLabel(/search products/i).fill(SEEDED_PRODUCT_NAME);
    await page.getByRole("button", { name: /find a food to log/i }).click();

    const logLink = page.getByRole("link", { name: new RegExp(`log ${SEEDED_PRODUCT_NAME}`, "i") });
    await expect(logLink).toBeVisible();
    await logLink.click();

    await expect(page).toHaveURL(/\/log\//);
    await page.getByLabel(/quantity/i).fill("150");
    await page.getByRole("button", { name: /log entry/i }).click();
    await expect(page.getByText(/may take a moment to update/i)).toBeVisible();

    await page.getByRole("link", { name: /view dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    // Poll (bounded retries, real condition check) until diary-service's
    // async projection has caught up -- never a fixed sleep (test-plan
    // section 6). Playwright's own `expect(...).toPass()` retries the
    // assertion on an interval until it passes or the timeout elapses.
    await expect(async () => {
      await page.getByRole("button", { name: /refresh/i }).click();
      await expect(page.getByRole("row", { name: /calories/i })).not.toContainText("0 kcal");
    }).toPass({ timeout: 30_000, intervals: [2_000] });
  });

  test("wrong password shows the generic error and does not navigate away from /login", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByLabel(/email address/i).fill(SEEDED_USER_EMAIL);
    await page.getByLabel(/^password$/i).fill("definitely-wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Scoped to .error-banner, not a bare role=alert query -- Next.js
    // itself injects a second role="alert" element (its built-in
    // route-announcer, #__next-route-announcer__, for screen-reader route
    // change announcements) which a bare getByRole("alert") also matches,
    // discovered empirically via a real Playwright run against this exact
    // page.
    await expect(page.locator(".error-banner")).toContainText(
      "Invalid email or password, or your email isn't verified yet.",
    );
    await expect(page).toHaveURL(/\/login/);
  });
});
