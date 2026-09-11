// @vitest-environment node
//
// Route Handlers are plain server functions (no rendering) -- and the
// journey 2 multipart cases below hang under jsdom (its File/Blob/
// FormData implementation doesn't round-trip cleanly through undici's
// multipart encoder when read back via request.formData() -- discovered
// empirically, every case touching a File timed out at exactly 5000ms).
// Node's native, undici-backed File/Blob/FormData/fetch is both the fix
// and the more correct environment for testing a server-only function.
import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { POST as loginRoute } from "@/app/api/auth/login/route";
import { POST as refreshRoute } from "@/app/api/auth/refresh/route";
import { POST as foodEntriesRoute } from "@/app/api/diary/food-entries/route";
import {
  POST as analyzePhotoRoute,
  MAX_UPLOAD_BYTES,
} from "@/app/api/food-recognition/photos/analyze/route";
import { POST as checkoutSessionsRoute } from "@/app/api/billing/checkout-sessions/route";
import { POST as createRecipeRoute, GET as listOwnRecipesRoute } from "@/app/api/recipes/route";
import {
  GET as getRecipeRoute,
  PATCH as updateRecipeRoute,
  DELETE as deleteRecipeRoute,
} from "@/app/api/recipes/[recipeId]/route";
import { POST as publishRecipeRoute } from "@/app/api/recipes/[recipeId]/publish/route";
import { POST as unpublishRecipeRoute } from "@/app/api/recipes/[recipeId]/unpublish/route";
import { GET as searchRecipesRoute } from "@/app/api/recipes/search/route";
import { loginResponseFixture } from "../fixtures/identity.fixtures";
import { foodEntryResponseFixture } from "../fixtures/diary.fixtures";
import {
  analyzePhotoDetectedFixture,
  analyzePhotoUnavailableFixture,
} from "../fixtures/food-recognition.fixtures";
import { checkoutSessionResponseFixture } from "../fixtures/billing.fixtures";
import {
  draftRecipeFixture,
  publishedRecipeFixture,
  notEntitledErrorFixture,
} from "../fixtures/recipe.fixtures";
import { REFRESH_TOKEN_COOKIE } from "@/lib/server/backend-config";

/**
 * Route Handlers are the resolution-1 proxy boundary (implementation plan
 * section 4/5) -- invoked directly here (no full Next server needed; a
 * Route Handler is a plain async function taking a (Next)Request) against
 * a mocked identity-service backend, proving the httpOnly-cookie contract
 * end-to-end without a live backend.
 */
describe("app/api/auth/login route handler", () => {
  it("sets an httpOnly refresh-token cookie and returns ONLY the access token", async () => {
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/login", () =>
        HttpResponse.json(loginResponseFixture),
      ),
    );
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.com", password: "x" }),
    });
    const response = await loginRoute(request);
    const body = await response.json();

    expect(body).toEqual({ access_token: loginResponseFixture.access_token, token_type: "bearer" });
    expect(body.refresh_token).toBeUndefined();

    const setCookie = response.cookies.get(REFRESH_TOKEN_COOKIE);
    expect(setCookie?.value).toBe(loginResponseFixture.refresh_token);
    expect(setCookie?.httpOnly).toBe(true);
    // Safe-by-default: Secure unless COOKIE_SECURE=false is set explicitly
    // (regression test for a real bug found via a live Playwright run --
    // see lib/server/backend-config.ts's COOKIE_SECURE doc comment).
    expect(setCookie?.secure).toBe(true);
  });

  it("forwards X-Forwarded-For to identity-service when the incoming request carries one", async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/login", ({ request }) => {
        capturedHeader = request.headers.get("x-forwarded-for");
        return HttpResponse.json(loginResponseFixture);
      }),
    );
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      headers: { "x-forwarded-for": "203.0.113.9" },
      body: JSON.stringify({ email: "a@example.com", password: "x" }),
    });
    await loginRoute(request);
    expect(capturedHeader).toBe("203.0.113.9");
  });

  it("relays the backend's real error code/status on failure", async () => {
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/login", () =>
        HttpResponse.json(
          { error: "Invalid email or password.", code: "INVALID_CREDENTIALS" },
          { status: 401 },
        ),
      ),
    );
    const request = new NextRequest("http://localhost/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@example.com", password: "wrong" }),
    });
    const response = await loginRoute(request);
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({
      error: "Invalid email or password.",
      code: "INVALID_CREDENTIALS",
    });
  });
});

describe("app/api/auth/refresh route handler", () => {
  it("returns 401 with no upstream call when no refresh-token cookie is present", async () => {
    let called = false;
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/refresh", () => {
        called = true;
        return HttpResponse.json({ access_token: "x", token_type: "bearer" });
      }),
    );
    const request = new NextRequest("http://localhost/api/auth/refresh", { method: "POST" });
    const response = await refreshRoute(request);
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("forwards the cookie's refresh token to identity-service when present", async () => {
    server.use(
      http.post("http://identity-service:8000/api/v1/auth/refresh", async ({ request }) => {
        const body = (await request.json()) as { refresh_token: string };
        expect(body.refresh_token).toBe("cookie-refresh-token");
        return HttpResponse.json({ access_token: "new-access-token", token_type: "bearer" });
      }),
    );
    const request = new NextRequest("http://localhost/api/auth/refresh", {
      method: "POST",
      headers: { cookie: `${REFRESH_TOKEN_COOKIE}=cookie-refresh-token` },
    });
    const response = await refreshRoute(request);
    expect(await response.json()).toEqual({
      access_token: "new-access-token",
      token_type: "bearer",
    });
  });
});

describe("app/api/diary/food-entries route handler -- journey 2 correlation-id forwarding", () => {
  const validBody = {
    source: {
      source_type: "ai_detected",
      source_reference_id: "55555555-5555-4555-8555-555555555555",
      snapshot: {
        name: "Plain Yogurt",
        brand: "Acme Dairy",
        quantity: 150,
        unit: "g",
        macros_per_unit: { calories_kcal: 61, protein_g: 3.5, carbs_g: 4.7, fat_g: 3.3 },
      },
    },
    meal_slot: "breakfast",
    occurred_at: "2026-09-10T08:00:00+00:00",
  };

  it("forwards X-Correlation-Id to diary-service when the incoming request carries one", async () => {
    let capturedHeader: string | null = null;
    server.use(
      http.post("http://diary-service:8000/api/v1/diary/food-entries", ({ request }) => {
        capturedHeader = request.headers.get("X-Correlation-Id");
        return HttpResponse.json(foodEntryResponseFixture);
      }),
    );
    const request = new NextRequest("http://localhost/api/diary/food-entries", {
      method: "POST",
      headers: {
        Authorization: "Bearer fixture-token",
        "X-Correlation-Id": "55555555-5555-4555-8555-555555555555",
      },
      body: JSON.stringify(validBody),
    });
    await foodEntriesRoute(request);
    expect(capturedHeader).toBe("55555555-5555-4555-8555-555555555555");
  });

  it("omits X-Correlation-Id downstream when the incoming request doesn't carry one", async () => {
    let capturedHeader: string | null | undefined = "not-set";
    server.use(
      http.post("http://diary-service:8000/api/v1/diary/food-entries", ({ request }) => {
        capturedHeader = request.headers.get("X-Correlation-Id");
        return HttpResponse.json(foodEntryResponseFixture);
      }),
    );
    const request = new NextRequest("http://localhost/api/diary/food-entries", {
      method: "POST",
      headers: { Authorization: "Bearer fixture-token" },
      body: JSON.stringify(validBody),
    });
    await foodEntriesRoute(request);
    expect(capturedHeader).toBeNull();
  });
});

describe("app/api/food-recognition/photos/analyze route handler", () => {
  function multipartRequest(opts: {
    file?: Blob | null;
    auth?: string | null;
    fieldName?: string;
  }) {
    const formData = new FormData();
    if (opts.file !== null) {
      formData.append(
        opts.fieldName ?? "file",
        opts.file ?? new File(["abc"], "x.jpg", { type: "image/jpeg" }),
      );
    }
    return new NextRequest("http://localhost/api/food-recognition/photos/analyze", {
      method: "POST",
      headers:
        opts.auth === undefined
          ? { Authorization: "Bearer fixture-token" }
          : opts.auth
            ? { Authorization: opts.auth }
            : {},
      body: formData,
    });
  }

  it("returns 401 with no downstream call when Authorization is missing", async () => {
    let called = false;
    server.use(
      http.post("http://food-recognition-service:8000/api/v1/recognition/photos/analyze", () => {
        called = true;
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    const request = multipartRequest({ auth: null });
    const response = await analyzePhotoRoute(request);
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("returns 422 with no downstream call when no file field is present", async () => {
    let called = false;
    server.use(
      http.post("http://food-recognition-service:8000/api/v1/recognition/photos/analyze", () => {
        called = true;
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    const request = multipartRequest({ file: null });
    const response = await analyzePhotoRoute(request);
    expect(response.status).toBe(422);
    expect(called).toBe(false);
  });

  it("returns 413 with no downstream call when the file exceeds the size cap", async () => {
    let called = false;
    server.use(
      http.post("http://food-recognition-service:8000/api/v1/recognition/photos/analyze", () => {
        called = true;
        return HttpResponse.json(analyzePhotoDetectedFixture);
      }),
    );
    const oversized = new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], "big.jpg", {
      type: "image/jpeg",
    });
    const request = multipartRequest({ file: oversized });
    const response = await analyzePhotoRoute(request);
    const body = await response.json();
    expect(response.status).toBe(413);
    expect(body.code).toBe("PHOTO_TOO_LARGE");
    expect(called).toBe(false);
  });

  it("forwards a valid upload and relays a 'detected' response verbatim", async () => {
    let capturedAuth: string | null = null;
    server.use(
      http.post(
        "http://food-recognition-service:8000/api/v1/recognition/photos/analyze",
        ({ request }) => {
          capturedAuth = request.headers.get("Authorization");
          return HttpResponse.json(analyzePhotoDetectedFixture);
        },
      ),
    );
    const request = multipartRequest({});
    const response = await analyzePhotoRoute(request);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(analyzePhotoDetectedFixture);
    expect(capturedAuth).toBe("Bearer fixture-token");
  });

  it("relays a 200 'unavailable' response as a normal success, not an error", async () => {
    server.use(
      http.post("http://food-recognition-service:8000/api/v1/recognition/photos/analyze", () =>
        HttpResponse.json(analyzePhotoUnavailableFixture),
      ),
    );
    const request = multipartRequest({});
    const response = await analyzePhotoRoute(request);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(analyzePhotoUnavailableFixture);
  });

  it("relays a genuine backend 5xx as a 502-class typed error", async () => {
    server.use(
      http.post("http://food-recognition-service:8000/api/v1/recognition/photos/analyze", () =>
        HttpResponse.json({ error: "boom", code: "INTERNAL_ERROR" }, { status: 500 }),
      ),
    );
    const request = multipartRequest({});
    const response = await analyzePhotoRoute(request);
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: "boom", code: "INTERNAL_ERROR" });
  });
});

describe("app/api/billing/checkout-sessions route handler", () => {
  it("returns 401 with no downstream call when Authorization is missing", async () => {
    let called = false;
    server.use(
      http.post("http://billing-service:8000/api/v1/billing/checkout-sessions", () => {
        called = true;
        return HttpResponse.json(checkoutSessionResponseFixture, { status: 201 });
      }),
    );
    const request = new NextRequest("http://localhost/api/billing/checkout-sessions", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const response = await checkoutSessionsRoute(request);
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("builds absolute success_url/cancel_url from this app's own base URL, ignoring whatever the client body sent", async () => {
    let capturedBody: { success_url?: string; cancel_url?: string } = {};
    server.use(
      http.post(
        "http://billing-service:8000/api/v1/billing/checkout-sessions",
        async ({ request }) => {
          capturedBody = (await request.json()) as typeof capturedBody;
          return HttpResponse.json(checkoutSessionResponseFixture, { status: 201 });
        },
      ),
    );
    const request = new NextRequest("http://localhost/api/billing/checkout-sessions", {
      method: "POST",
      headers: { Authorization: "Bearer fixture-token" },
      body: JSON.stringify({
        success_url: "http://attacker.example/anything",
        cancel_url: "http://attacker.example/anything",
      }),
    });
    await checkoutSessionsRoute(request);
    expect(capturedBody.success_url).toMatch(/\/pro\/success$/);
    expect(capturedBody.cancel_url).toMatch(/\/pro\/cancel$/);
    expect(capturedBody.success_url).not.toContain("attacker.example");
  });

  it("relays a 409 SUBSCRIPTION_ALREADY_ACTIVE verbatim", async () => {
    server.use(
      http.post("http://billing-service:8000/api/v1/billing/checkout-sessions", () =>
        HttpResponse.json(
          {
            error: "User already has an active subscription.",
            code: "SUBSCRIPTION_ALREADY_ACTIVE",
          },
          { status: 409 },
        ),
      ),
    );
    const request = new NextRequest("http://localhost/api/billing/checkout-sessions", {
      method: "POST",
      headers: { Authorization: "Bearer fixture-token" },
      body: JSON.stringify({}),
    });
    const response = await checkoutSessionsRoute(request);
    expect(response.status).toBe(409);
    expect((await response.json()).code).toBe("SUBSCRIPTION_ALREADY_ACTIVE");
  });
});

describe("app/api/recipes route handlers", () => {
  it("POST /api/recipes returns 401 with no downstream call when Authorization is missing", async () => {
    let called = false;
    server.use(
      http.post("http://recipe-service:8000/api/v1/recipes", () => {
        called = true;
        return HttpResponse.json(draftRecipeFixture, { status: 201 });
      }),
    );
    const request = new NextRequest("http://localhost/api/recipes", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const response = await createRecipeRoute(request);
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("POST /api/recipes forwards the body and Authorization verbatim", async () => {
    let capturedAuth: string | null = null;
    let capturedBody: unknown;
    server.use(
      http.post("http://recipe-service:8000/api/v1/recipes", async ({ request }) => {
        capturedAuth = request.headers.get("Authorization");
        capturedBody = await request.json();
        return HttpResponse.json(draftRecipeFixture, { status: 201 });
      }),
    );
    const body = { title: "x", instructions: "y", servings: 1, ingredients: [] };
    const request = new NextRequest("http://localhost/api/recipes", {
      method: "POST",
      headers: { Authorization: "Bearer fixture-token" },
      body: JSON.stringify(body),
    });
    await createRecipeRoute(request);
    expect(capturedAuth).toBe("Bearer fixture-token");
    expect(capturedBody).toEqual(body);
  });

  it("GET /api/recipes always forwards mine=true, ignoring any other query", async () => {
    let capturedUrl = "";
    server.use(
      http.get("http://recipe-service:8000/api/v1/recipes", ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ items: [] });
      }),
    );
    const request = new NextRequest("http://localhost/api/recipes?mine=false", {
      headers: { Authorization: "Bearer fixture-token" },
    });
    await listOwnRecipesRoute(request);
    expect(capturedUrl).toContain("mine=true");
  });

  it("GET /api/recipes/{id} returns 401 with no downstream call when Authorization is missing", async () => {
    let called = false;
    server.use(
      http.get(`http://recipe-service:8000/api/v1/recipes/${draftRecipeFixture.recipe_id}`, () => {
        called = true;
        return HttpResponse.json(draftRecipeFixture);
      }),
    );
    const request = new NextRequest(`http://localhost/api/recipes/${draftRecipeFixture.recipe_id}`);
    const response = await getRecipeRoute(request, {
      params: Promise.resolve({ recipeId: draftRecipeFixture.recipe_id }),
    });
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("PATCH /api/recipes/{id} forwards the body", async () => {
    let capturedBody: unknown;
    server.use(
      http.patch(
        `http://recipe-service:8000/api/v1/recipes/${draftRecipeFixture.recipe_id}`,
        async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json(draftRecipeFixture);
        },
      ),
    );
    const body = { title: "z", instructions: "y", servings: 2, ingredients: [] };
    const request = new NextRequest(
      `http://localhost/api/recipes/${draftRecipeFixture.recipe_id}`,
      {
        method: "PATCH",
        headers: { Authorization: "Bearer fixture-token" },
        body: JSON.stringify(body),
      },
    );
    await updateRecipeRoute(request, {
      params: Promise.resolve({ recipeId: draftRecipeFixture.recipe_id }),
    });
    expect(capturedBody).toEqual(body);
  });

  it("DELETE /api/recipes/{id} returns 401 with no downstream call when Authorization is missing", async () => {
    let called = false;
    server.use(
      http.delete(
        `http://recipe-service:8000/api/v1/recipes/${draftRecipeFixture.recipe_id}`,
        () => {
          called = true;
          return new HttpResponse(null, { status: 204 });
        },
      ),
    );
    const request = new NextRequest(
      `http://localhost/api/recipes/${draftRecipeFixture.recipe_id}`,
      { method: "DELETE" },
    );
    const response = await deleteRecipeRoute(request, {
      params: Promise.resolve({ recipeId: draftRecipeFixture.recipe_id }),
    });
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("POST /api/recipes/{id}/publish relays a 402 NOT_ENTITLED verbatim", async () => {
    server.use(
      http.post(
        `http://recipe-service:8000/api/v1/recipes/${draftRecipeFixture.recipe_id}/publish`,
        () => HttpResponse.json(notEntitledErrorFixture, { status: 402 }),
      ),
    );
    const request = new NextRequest(
      `http://localhost/api/recipes/${draftRecipeFixture.recipe_id}/publish`,
      { method: "POST", headers: { Authorization: "Bearer fixture-token" } },
    );
    const response = await publishRecipeRoute(request, {
      params: Promise.resolve({ recipeId: draftRecipeFixture.recipe_id }),
    });
    expect(response.status).toBe(402);
    expect((await response.json()).code).toBe("NOT_ENTITLED");
  });

  it("POST /api/recipes/{id}/unpublish returns 401 with no downstream call when Authorization is missing", async () => {
    let called = false;
    server.use(
      http.post(
        `http://recipe-service:8000/api/v1/recipes/${publishedRecipeFixture.recipe_id}/unpublish`,
        () => {
          called = true;
          return HttpResponse.json(draftRecipeFixture);
        },
      ),
    );
    const request = new NextRequest(
      `http://localhost/api/recipes/${publishedRecipeFixture.recipe_id}/unpublish`,
      { method: "POST" },
    );
    const response = await unpublishRecipeRoute(request, {
      params: Promise.resolve({ recipeId: publishedRecipeFixture.recipe_id }),
    });
    expect(response.status).toBe(401);
    expect(called).toBe(false);
  });

  it("GET /api/recipes/search blocks an empty q before any downstream call", async () => {
    let called = false;
    server.use(
      http.get("http://recipe-service:8000/api/v1/recipes/search", () => {
        called = true;
        return HttpResponse.json({ items: [] });
      }),
    );
    const request = new NextRequest("http://localhost/api/recipes/search?q=", {
      headers: { Authorization: "Bearer fixture-token" },
    });
    const response = await searchRecipesRoute(request);
    expect(response.status).toBe(422);
    expect(called).toBe(false);
  });

  it("GET /api/recipes/search forwards a real query and relays results", async () => {
    server.use(
      http.get("http://recipe-service:8000/api/v1/recipes/search", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("q")).toBe("yogurt");
        return HttpResponse.json({ items: [publishedRecipeFixture] });
      }),
    );
    const request = new NextRequest("http://localhost/api/recipes/search?q=yogurt", {
      headers: { Authorization: "Bearer fixture-token" },
    });
    const response = await searchRecipesRoute(request);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ items: [publishedRecipeFixture] });
  });
});
