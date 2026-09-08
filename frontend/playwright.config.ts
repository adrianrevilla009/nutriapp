import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against a full `docker-compose up` stack (implementation plan
 * section 7 / test-plan section 6) -- NOT started by this config itself.
 * baseURL defaults to the frontend's own docker-compose port (3000); the
 * seed step under tests/e2e/seed/ must run before this suite (a
 * pre-verified user + at least one catalog product), per resolution 2.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
