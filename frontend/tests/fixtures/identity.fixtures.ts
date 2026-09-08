/**
 * Fixtures shaped from services/identity-service/infrastructure/http/schemas/auth_schemas.py
 * (read verbatim during /implementation-plan's research, not hand-invented).
 * Test-plan section 4/8.
 */

// auth_schemas.py: RegisterResponse
export const registerResponseFixture = {
  user_id: "11111111-1111-4111-8111-111111111111",
};

// auth_schemas.py: VerifyEmailResponse
export const verifyEmailResponseFixture = {
  user_id: "11111111-1111-4111-8111-111111111111",
};

// auth_schemas.py: LoginResponse
export const loginResponseFixture = {
  access_token: "fixture-access-token",
  refresh_token: "fixture-refresh-token",
  token_type: "bearer",
};

// THIS APP'S OWN app/api/auth/login/route.ts response shape -- NOT
// identity-service's LoginResponse. Deliberately omits refresh_token
// (stripped server-side, set as an httpOnly cookie instead -- see
// schemas/identity.ts's BrowserLoginResultSchema doc for the real bug a
// fixture mismatch here previously masked: using `loginResponseFixture`
// -- the BACKEND shape, refresh_token included -- to mock this endpoint
// hid a real client-side Zod validation failure on every actual login).
export const browserLoginResultFixture = {
  access_token: "fixture-access-token",
  token_type: "bearer",
};

// auth_schemas.py: RefreshResponse
export const refreshResponseFixture = {
  access_token: "fixture-refreshed-access-token",
  token_type: "bearer",
};

// auth_schemas.py: ErrorResponse -- identity-service's generic, deliberately
// non-distinguishing login failure (application/commands/login.py lines 107-112).
export const invalidCredentialsErrorFixture = {
  error: "Invalid email or password.",
  code: "INVALID_CREDENTIALS",
};

// diary-service's 422-style validation error, same {error, code} shape
// (api-conventions SKILL.md) -- used to prove ErrorResponseSchema parses
// both identity-service's and diary-service's errors identically.
export const validationErrorFixture = {
  error: "quantity must be greater than 0.",
  code: "VALIDATION_ERROR",
};
