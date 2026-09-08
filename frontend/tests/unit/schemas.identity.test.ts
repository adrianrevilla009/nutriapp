import { describe, expect, it } from "vitest";
import {
  BrowserLoginResultSchema,
  ErrorResponseSchema,
  LoginResponseSchema,
  RegisterRequestSchema,
  RegisterResponseSchema,
  VerifyEmailRequestSchema,
  VerifyEmailResponseSchema,
} from "@/schemas/identity";
import {
  browserLoginResultFixture,
  invalidCredentialsErrorFixture,
  loginResponseFixture,
  registerResponseFixture,
  validationErrorFixture,
  verifyEmailResponseFixture,
} from "../fixtures/identity.fixtures";

describe("RegisterRequestSchema", () => {
  it("rejects a malformed email", () => {
    const result = RegisterRequestSchema.safeParse({ email: "not-an-email", password: "x" });
    expect(result.success).toBe(false);
  });

  it("rejects an empty password", () => {
    const result = RegisterRequestSchema.safeParse({ email: "a@example.com", password: "" });
    expect(result.success).toBe(false);
  });

  it("accepts a valid email/password pair", () => {
    const result = RegisterRequestSchema.safeParse({ email: "a@example.com", password: "x" });
    expect(result.success).toBe(true);
  });
});

describe("RegisterResponseSchema", () => {
  it("parses the real backend shape", () => {
    expect(RegisterResponseSchema.parse(registerResponseFixture)).toEqual(registerResponseFixture);
  });

  it("requires a UUID user_id", () => {
    expect(RegisterResponseSchema.safeParse({ user_id: "not-a-uuid" }).success).toBe(false);
  });
});

describe("VerifyEmailRequestSchema", () => {
  it("rejects a missing reference_id", () => {
    expect(VerifyEmailRequestSchema.safeParse({ secret: "s" }).success).toBe(false);
  });

  it("rejects a missing secret", () => {
    expect(VerifyEmailRequestSchema.safeParse({ reference_id: "r" }).success).toBe(false);
  });
});

describe("VerifyEmailResponseSchema", () => {
  it("parses the real backend shape", () => {
    expect(VerifyEmailResponseSchema.parse(verifyEmailResponseFixture)).toEqual(
      verifyEmailResponseFixture,
    );
  });
});

describe("LoginResponseSchema", () => {
  it("parses the real backend shape, defaulting token_type", () => {
    expect(LoginResponseSchema.parse(loginResponseFixture)).toEqual(loginResponseFixture);
  });

  it("rejects a response missing access_token rather than coercing to undefined", () => {
    const malformed = { refresh_token: "r", token_type: "bearer" };
    expect(LoginResponseSchema.safeParse(malformed).success).toBe(false);
  });

  it("defaults token_type to bearer when omitted", () => {
    const parsed = LoginResponseSchema.parse({
      access_token: "a",
      refresh_token: "r",
    });
    expect(parsed.token_type).toBe("bearer");
  });
});

describe("BrowserLoginResultSchema", () => {
  // Regression coverage for a real bug (found via a live Playwright run,
  // not by any mocked test until this schema/fixture split existed):
  // this app's own login Route Handler's response NEVER carries
  // refresh_token (stripped server-side into an httpOnly cookie), a
  // genuinely different shape than identity-service's own LoginResponse.
  it("parses the app's own proxy response shape (no refresh_token) successfully", () => {
    expect(BrowserLoginResultSchema.parse(browserLoginResultFixture)).toEqual(
      browserLoginResultFixture,
    );
  });

  it("still requires access_token", () => {
    expect(BrowserLoginResultSchema.safeParse({ token_type: "bearer" }).success).toBe(false);
  });
});

describe("ErrorResponseSchema", () => {
  it("parses identity-service's generic invalid-credentials shape", () => {
    expect(ErrorResponseSchema.parse(invalidCredentialsErrorFixture)).toMatchObject(
      invalidCredentialsErrorFixture,
    );
  });

  it("parses diary-service's validation-error shape identically", () => {
    expect(ErrorResponseSchema.parse(validationErrorFixture)).toMatchObject(validationErrorFixture);
  });

  it("tolerates an unknown extra field (passthrough, not strict)", () => {
    const withExtra = { ...invalidCredentialsErrorFixture, details: { field: "email" } };
    expect(() => ErrorResponseSchema.parse(withExtra)).not.toThrow();
  });
});
