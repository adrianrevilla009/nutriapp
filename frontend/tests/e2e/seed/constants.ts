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
export const SEEDED_USER_PASSWORD = "correct-horse-battery-staple";
export const SEEDED_PRODUCT_NAME = "E2E Seed Yogurt";

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
