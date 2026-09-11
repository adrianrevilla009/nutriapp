/**
 * Pure constants + pure helper shared between seed.ts (which has real DB
 * side effects and must only run when executed directly via
 * `pnpm test:e2e:seed`) and anything that just needs to reference the
 * seeded fixture values (the Playwright spec, and the unit test for
 * `toPythonArgon2ParamOrder`) -- split into its own side-effect-free
 * module so importing it never risks a CJS/ESM interop issue or an
 * accidental real DB write (Playwright's default TS transform doesn't
 * reliably support `import.meta`-based entry-point guards, discovered
 * empirically while wiring this up against a real Playwright run).
 */
export const SEEDED_USER_EMAIL = "e2e-seed-user@example.com";
// NOSONAR(typescript:S2068) -- a fixed, throwaway credential for a
// test-only seeded user in a local docker-compose stack, never a real
// secret. Committing it is the point: the Playwright spec and the seed
// script must agree on the same literal value.
export const SEEDED_USER_PASSWORD = "correct-horse-battery-staple"; // NOSONAR
export const SEEDED_PRODUCT_NAME = "E2E Seed Yogurt";

/**
 * journey 3 (upgrade to Pro -> publish a recipe -> another user finds it):
 * THREE distinct seeded identities, deliberately separate from
 * SEEDED_USER_EMAIL above (journeys 1-2's own seeded user) so this
 * journey's Pro-entitlement state never bleeds into another journey's
 * assumptions.
 *
 * journey-3 implementation-plan resolution 1: no real Stripe checkout is
 * possible in this environment (docker-compose.yml's Stripe keys are
 * placeholders) -- publisher/finder are seeded directly into an ACTIVE
 * state via a billing-db subscription row insert (seed.ts's
 * seedActiveSubscription), bypassing Stripe/the webhook path entirely,
 * mirroring journey 1's "seed a pre-verified user" precedent applied one
 * level deeper. nonPro is deliberately left WITHOUT a subscription row, to
 * exercise the real (non-mocked) 402/NOT_ENTITLED path against the live
 * stack.
 */
export const SEEDED_PUBLISHER_EMAIL = "e2e-recipe-publisher@example.com";
export const SEEDED_PUBLISHER_PASSWORD = "correct-horse-battery-staple-publisher"; // NOSONAR
export const SEEDED_PUBLISHER_USER_ID = "00000000-0000-4000-8000-0000000000a1";

export const SEEDED_FINDER_EMAIL = "e2e-recipe-finder@example.com";
export const SEEDED_FINDER_PASSWORD = "correct-horse-battery-staple-finder"; // NOSONAR
export const SEEDED_FINDER_USER_ID = "00000000-0000-4000-8000-0000000000a2";

export const SEEDED_NON_PRO_EMAIL = "e2e-non-pro-searcher@example.com";
export const SEEDED_NON_PRO_PASSWORD = "correct-horse-battery-staple-nonpro"; // NOSONAR
export const SEEDED_NON_PRO_USER_ID = "00000000-0000-4000-8000-0000000000a3";

/**
 * node-argon2 encodes the PHC parameter segment as `m=..,p=..,t=..`;
 * Python's argon2-cffi (identity-service's actual verifier,
 * infrastructure/security/argon2_password_hasher.py) decodes strictly in
 * `m=..,t=..,p=..` order and otherwise fails with "Decoding failed" even
 * though the hash itself is byte-identical and standards-compliant --
 * discovered empirically while validating this script end-to-end against
 * a real identity-service container (not a hypothetical concern).
 * Reordered here so the seeded hash verifies under identity-service's
 * actual verifier, not just under node-argon2's own.
 */
export function toPythonArgon2ParamOrder(encodedHash: string): string {
  return encodedHash.replace(
    /m=(\d+),p=(\d+),t=(\d+)/,
    (_match, m: string, p: string, t: string) => `m=${m},t=${t},p=${p}`,
  );
}
