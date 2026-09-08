import { describe, expect, it } from "vitest";
import { toPythonArgon2ParamOrder } from "../e2e/seed/constants";

/**
 * Regression test for a REAL cross-library incompatibility discovered
 * while validating tests/e2e/seed/seed.ts end-to-end against a live
 * identity-service container: node-argon2 encodes the PHC parameter
 * segment as `m=..,p=..,t=..`, but identity-service's actual verifier
 * (Python's argon2-cffi, infrastructure/security/argon2_password_hasher.py)
 * decodes strictly in `m=..,t=..,p=..` order and rejects the other order
 * with "Decoding failed" even though the underlying hash is byte-identical
 * and standards-compliant. Without this reordering, every seeded user's
 * password would silently fail to verify against the real backend --
 * this was NOT caught by any mocked/unit-level test, only by running the
 * seed script against a real container.
 */
describe("toPythonArgon2ParamOrder", () => {
  it("reorders m,p,t to m,t,p in the PHC parameter segment", () => {
    const nodeArgon2Style =
      "$argon2id$v=19$m=65536,p=4,t=3$WVxfEsiA3/lTHltEZtGveA$fJwo8XvZwGt0pLXLZSXs1jF8U7o9MLso+dtBLZFD/lA";
    expect(toPythonArgon2ParamOrder(nodeArgon2Style)).toBe(
      "$argon2id$v=19$m=65536,t=3,p=4$WVxfEsiA3/lTHltEZtGveA$fJwo8XvZwGt0pLXLZSXs1jF8U7o9MLso+dtBLZFD/lA",
    );
  });

  it("leaves the salt/hash segments and every other character untouched", () => {
    const input = "$argon2id$v=19$m=19456,p=1,t=2$c29tZXNhbHQ$c29tZWhhc2h2YWx1ZXRoYXRpc2xvbmc";
    const result = toPythonArgon2ParamOrder(input);
    expect(result).toContain("$c29tZXNhbHQ$c29tZWhhc2h2YWx1ZXRoYXRpc2xvbmc");
    expect(result.startsWith("$argon2id$v=19$")).toBe(true);
  });

  it("is a no-op on a string already in m,t,p order", () => {
    const alreadyOrdered = "$argon2id$v=19$m=65536,t=3,p=4$salt$hash";
    expect(toPythonArgon2ParamOrder(alreadyOrdered)).toBe(alreadyOrdered);
  });
});
