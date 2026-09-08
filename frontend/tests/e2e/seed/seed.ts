/**
 * E2E test-only seed script (implementation plan resolution 2 / test-plan
 * section 6, flagged as genuinely NEW test infrastructure in test-plan's
 * "Flagged for review" item 3 -- this is not a reuse of anything existing).
 *
 * Inserts directly into identity-db and catalog-db (bypassing both
 * services' HTTP APIs) so the Playwright E2E spec can start from a
 * pre-verified user without depending on a real email-catcher (no
 * `ses-fake` container exists in docker-compose.yml today -- implementation
 * plan section 9 resolution 2).
 *
 * Run via `pnpm test:e2e:seed` BEFORE `pnpm test:e2e`, against a running
 * `docker-compose up` stack. Connects to identity-db (port 5432) and
 * catalog-db (port 5435) using the same default credentials
 * docker-compose.yml documents.
 *
 * SCHEMA COUPLING WARNING (test-plan "Flagged for review" item 3): this
 * script writes directly to identity-service's `users` table
 * (infrastructure/persistence/models.py) and catalog-service's `products`
 * table (infrastructure/persistence/models.py). If either service's
 * schema changes, this script must be updated in the same PR -- there is
 * no contract test enforcing that today, unlike the HTTP/event contracts
 * this frontend otherwise mirrors (schemas/*.ts). Revisit with qa-agent if
 * this drifts.
 *
 * Requires `argon2`'s native binding to actually be built (pnpm's default
 * blocks postinstall scripts for security -- run
 * `pnpm approve-builds` once locally, or `pnpm rebuild argon2`, before
 * running this script for the first time).
 *
 * This file is executed directly (never imported) -- its pure exports
 * (SEEDED_*, toPythonArgon2ParamOrder) live in ./constants.ts instead, so
 * the Playwright spec and this logic's own unit test can import them
 * without pulling in `pg`/`argon2` or risking a real DB write as an
 * import-time side effect.
 */
import { randomUUID } from "node:crypto";
import { Client } from "pg";
import * as argon2 from "argon2";
import {
  SEEDED_PRODUCT_NAME,
  SEEDED_USER_EMAIL,
  SEEDED_USER_PASSWORD,
  toPythonArgon2ParamOrder,
} from "./constants";

const IDENTITY_DB_URL =
  process.env.E2E_IDENTITY_DB_URL ??
  "postgresql://identity_service:identity_service@localhost:5432/identity_service";
const CATALOG_DB_URL =
  process.env.E2E_CATALOG_DB_URL ??
  "postgresql://catalog_service:catalog_service@localhost:5435/catalog_service";

async function seedVerifiedUser(): Promise<void> {
  const client = new Client({ connectionString: IDENTITY_DB_URL });
  await client.connect();
  try {
    const passwordHash = toPythonArgon2ParamOrder(
      await argon2.hash(SEEDED_USER_PASSWORD, { type: argon2.argon2id }),
    );
    await client.query(
      `INSERT INTO users (id, email, password_hash, status, roles, failed_login_attempts,
                          last_login_at, password_changed_at, created_at, known_device_fingerprints)
       VALUES ($1, $2, $3, 'ACTIVE', ARRAY['USER'], 0, NULL, NULL, now(), '[]'::jsonb)
       ON CONFLICT (email) DO UPDATE SET
         password_hash = EXCLUDED.password_hash,
         status = 'ACTIVE',
         failed_login_attempts = 0`,
      [randomUUID(), SEEDED_USER_EMAIL, passwordHash],
    );
  } finally {
    await client.end();
  }
}

// Fixed, deterministic id -- re-running this script re-seeds the SAME
// row (ON CONFLICT below) instead of accumulating a new duplicate product
// on every run. REAL bug found via repeated local E2E iteration: an
// earlier version used `randomUUID()` here, and re-running the seed
// script between test runs (a completely normal local dev workflow) kept
// inserting new rows with the same name, until the E2E spec's product
// search started matching 9+ duplicates and failed with a Playwright
// strict-mode violation on what was meant to be a single, unique result.
const SEEDED_PRODUCT_ID = "00000000-0000-4000-8000-000000000001";

async function seedProduct(): Promise<string> {
  const client = new Client({ connectionString: CATALOG_DB_URL });
  await client.connect();
  try {
    const productId = SEEDED_PRODUCT_ID;
    await client.query(
      `INSERT INTO products (product_id, barcode, name, brand, category, nutrient_panel,
                             dietary_tags, allergen_tags, package_size, price, sources,
                             catalogued_at, updated_at)
       VALUES ($1, NULL, $2, 'E2E Fixtures', 'dairy', $3::jsonb,
               ARRAY['vegetarian'], ARRAY['milk'], $4::jsonb, $5::jsonb, ARRAY['open_food_facts'],
               now(), now())
       ON CONFLICT (product_id) DO UPDATE SET
         name = EXCLUDED.name,
         nutrient_panel = EXCLUDED.nutrient_panel,
         updated_at = now()`,
      [
        productId,
        SEEDED_PRODUCT_NAME,
        JSON.stringify({
          energy_kcal: 61,
          protein_g: 3.5,
          carbohydrates_g: 4.7,
          fat_g: 3.3,
          sugars_g: 4.7,
          fiber_g: 0,
          saturated_fat_g: 2.1,
          sodium_mg: 46,
          salt_g: 0.11,
          calcium_mg: 121,
          iron_mg: 0.05,
          vitamin_c_mg: 0.5,
        }),
        JSON.stringify({ value: 500, unit: "g" }),
        JSON.stringify({ amount: 1.99, currency: "USD" }),
      ],
    );
    return productId;
  } finally {
    await client.end();
  }
}

async function main() {
  await seedVerifiedUser();
  const productId = await seedProduct();
  console.log(
    JSON.stringify({ email: SEEDED_USER_EMAIL, password: SEEDED_USER_PASSWORD, productId }),
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
