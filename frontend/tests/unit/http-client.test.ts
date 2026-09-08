import { afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../msw-server";
import { apiFetch, AppError, TimeoutError } from "@/lib/api/http-client";

describe("apiFetch", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("attaches Authorization only when a token is supplied", async () => {
    let capturedAuth: string | null | undefined;
    server.use(
      http.get("http://test.local/with-token", ({ request }) => {
        capturedAuth = request.headers.get("Authorization");
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiFetch("http://test.local/with-token", { accessToken: "abc123" });
    expect(capturedAuth).toBe("Bearer abc123");
  });

  it("never sends a literal 'Bearer undefined'/'Bearer null' header", async () => {
    let capturedAuth: string | null | undefined = "not-set";
    server.use(
      http.get("http://test.local/no-token", ({ request }) => {
        capturedAuth = request.headers.get("Authorization");
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiFetch("http://test.local/no-token", {});
    expect(capturedAuth).toBeNull();
  });

  it("parses a {error, code} error body into a typed AppError, preserving status", async () => {
    server.use(
      http.post("http://test.local/fails", () =>
        HttpResponse.json({ error: "Bad input.", code: "BAD_INPUT" }, { status: 422 }),
      ),
    );
    await expect(apiFetch("http://test.local/fails", { method: "POST" })).rejects.toMatchObject({
      message: "Bad input.",
      code: "BAD_INPUT",
      status: 422,
    });
  });

  it("falls back to a generic AppError for a non-JSON error body, never an unhandled parse exception", async () => {
    server.use(
      http.get(
        "http://test.local/html-error",
        () => new HttpResponse("<html>502 Bad Gateway</html>", { status: 502 }),
      ),
    );
    const error = await apiFetch("http://test.local/html-error").catch((e) => e);
    expect(error).toBeInstanceOf(AppError);
    expect((error as AppError).code).toBe("UNKNOWN_ERROR");
  });

  it("aborts and throws TimeoutError when the request exceeds the configured timeout", async () => {
    server.use(
      http.get("http://test.local/slow", async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return HttpResponse.json({ ok: true });
      }),
    );
    await expect(apiFetch("http://test.local/slow", { timeoutMs: 5 })).rejects.toBeInstanceOf(
      TimeoutError,
    );
  });
});
