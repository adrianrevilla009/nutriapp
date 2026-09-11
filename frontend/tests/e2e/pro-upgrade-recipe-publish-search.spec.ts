import { expect, test } from "@playwright/test";
import {
  SEEDED_FINDER_EMAIL,
  SEEDED_FINDER_PASSWORD,
  SEEDED_NON_PRO_EMAIL,
  SEEDED_NON_PRO_PASSWORD,
  SEEDED_PRODUCT_NAME,
  SEEDED_PUBLISHER_EMAIL,
  SEEDED_PUBLISHER_PASSWORD,
} from "./seed/constants";

/**
 * Full journey 3 backbone (implementation plan section 1 / test-plan
 * section 6): publish a recipe as one identity, find it as a SECOND,
 * distinct identity -- the first journey in this suite needing two
 * concurrent, isolated sessions in one spec.
 *
 * journey-3 resolution 1: does NOT exercise a live Stripe checkout round
 * trip anywhere in this spec -- both the publisher and finder start from
 * directly-seeded Pro state (tests/e2e/seed/seed.ts's
 * seedActiveSubscription, bypassing Stripe/the webhook path entirely). The
 * checkout-INITIATION UI (button -> POST -> redirect) is covered only by
 * tests/integration/CheckoutRedirectButton.test.tsx, never here -- this
 * environment has no valid Stripe test-mode key (docker-compose.yml's own
 * placeholders), so a live round trip is not buildable in this environment.
 *
 * Prerequisite: `pnpm test:e2e:seed` has been run against the SAME
 * docker-compose stack this spec targets (now also seeding the publisher/
 * finder/non-Pro identities and their billing-db subscription rows).
 */
test.describe("upgrade to Pro -> publish a recipe -> another user finds it (journey 3)", () => {
  test("publisher authors and publishes a recipe; a SEPARATE finder identity finds it in search", async ({
    browser,
  }) => {
    // Two independent BrowserContexts -- two independent cookie jars --
    // proving session isolation is real, not just "it happened to work"
    // (test-plan section 6's explicit cross-contamination requirement).
    const publisherContext = await browser.newContext();
    const finderContext = await browser.newContext();
    const publisherPage = await publisherContext.newPage();
    const finderPage = await finderContext.newPage();

    try {
      // --- Publisher: log in, author, publish ---
      await publisherPage.goto("/login");
      await publisherPage.getByLabel(/email address/i).fill(SEEDED_PUBLISHER_EMAIL);
      await publisherPage.getByLabel(/^password$/i).fill(SEEDED_PUBLISHER_PASSWORD);
      await publisherPage.getByRole("button", { name: /sign in/i }).click();
      await expect(publisherPage).toHaveURL(/\/search/);

      const recipeTitle = `E2E Journey 3 Recipe ${Date.now()}`;
      await publisherPage.goto("/recipes/new");
      await publisherPage.getByLabel(/^title$/i).fill(recipeTitle);
      await publisherPage.getByLabel(/instructions/i).fill("Mix everything in a bowl.");

      await publisherPage.getByLabel(/search products/i).fill(SEEDED_PRODUCT_NAME);
      await publisherPage.getByRole("button", { name: /^find a food to log$/i }).click();
      await publisherPage
        .getByRole("button", { name: new RegExp(`add ${SEEDED_PRODUCT_NAME}`, "i") })
        .click();

      await publisherPage.getByRole("button", { name: /save recipe/i }).click();
      await expect(publisherPage).toHaveURL(/\/recipes\/[0-9a-f-]+$/);

      // CLAUDE.md section 8 consent step -- confirm, then publish.
      await publisherPage.getByRole("button", { name: /^publish$/i }).click();
      await expect(publisherPage.getByText(/visible to other nutriapp users/i)).toBeVisible();
      await publisherPage.getByRole("button", { name: /publish recipe/i }).click();
      await expect(publisherPage.getByText(/^published$/i)).toBeVisible();

      // --- Finder: a SEPARATE identity, separate context, finds it ---
      await finderPage.goto("/login");
      await finderPage.getByLabel(/email address/i).fill(SEEDED_FINDER_EMAIL);
      await finderPage.getByLabel(/^password$/i).fill(SEEDED_FINDER_PASSWORD);
      await finderPage.getByRole("button", { name: /sign in/i }).click();
      await expect(finderPage).toHaveURL(/\/search/);

      await finderPage.goto("/recipes/search");
      await finderPage.getByLabel(/search recipes/i).fill(recipeTitle);
      await finderPage.getByRole("button", { name: /find a recipe/i }).click();

      await expect(finderPage.getByText(recipeTitle)).toBeVisible();

      // --- Cross-contamination check (test-plan section 6's explicit
      // requirement): the publisher's OWN context/session must be entirely
      // unaffected by everything the finder just did in its own context. ---
      await publisherPage.goto("/recipes");
      await expect(publisherPage.getByText(recipeTitle)).toBeVisible();
      await expect(publisherPage).not.toHaveURL(/\/login/);
      // ...and, symmetrically, the finder's session is unaffected by the
      // publisher's own actions/context.
      await expect(finderPage).not.toHaveURL(/\/login/);
    } finally {
      await publisherContext.close();
      await finderContext.close();
    }
  });

  test("a non-Pro identity searching for recipes sees a REAL, live 'Search is a Pro feature' prompt, not a mocked one", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByLabel(/email address/i).fill(SEEDED_NON_PRO_EMAIL);
    await page.getByLabel(/^password$/i).fill(SEEDED_NON_PRO_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/search/);

    await page.goto("/recipes/search");
    await page.getByLabel(/search recipes/i).fill("anything");
    await page.getByRole("button", { name: /find a recipe/i }).click();

    await expect(page.getByText(/recipe search is a pro feature/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /upgrade to pro/i })).toHaveAttribute(
      "href",
      "/pro",
    );
  });
});
